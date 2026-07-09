from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from zipfile import BadZipFile

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.opc.exceptions import PackageNotFoundError
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFEncryptionError
from pdfminer.pdfparser import PDFSyntaxError
import yaml

from lib.catalog import CatalogError, initialize_catalog
from lib.normalize import normalize


SUPPORTED_EXTENSIONS = {".docx", ".pdf"}
ZIP_EXTENSIONS = {".zip"}
TYPE_RULE_PATHS = (Path("data/type_rules.yaml"), Path(".docs/type_rules.yaml"))


@dataclass
class ExtractedDocument:
    paragraphs: List[str]
    status: str = "ok"
    error_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExistingRecord:
    file_key: str
    path: str
    size: Optional[int]
    mtime: Optional[float]
    status: str
    content_hash: Optional[str]
    txt_path: Optional[str]


@dataclass
class IndexOptions:
    include_misc: bool = False
    full: bool = False
    batch_label: Optional[str] = None
    file_list: Optional[Path] = None
    sample: Optional[int] = None
    sample_seed: int = 0
    dry_run: bool = False


@dataclass
class ChangeReport:
    new: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    moved: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    restored: List[str] = field(default_factory=list)
    content_changed: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class TypeRule:
    value: str
    patterns: List[str]
    flag: Optional[str] = None


@dataclass
class TypeRules:
    ctype_rules: List[TypeRule] = field(default_factory=list)
    lang_rules: List[TypeRule] = field(default_factory=list)
    draft_patterns: List[str] = field(default_factory=list)
    executed_patterns: List[str] = field(default_factory=list)
    version_capture: List[str] = field(default_factory=list)


def sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def hash_text(text: str) -> str:
    return sha256_short(text.encode("utf-8"))


def load_type_rules(start: Optional[Path] = None) -> TypeRules:
    base = start or Path.cwd()
    selected = None
    for candidate in TYPE_RULE_PATHS:
        path = base / candidate
        if path.exists():
            selected = path
            break
    if selected is None:
        return TypeRules()

    data = yaml.safe_load(selected.read_text(encoding="utf-8")) or {}
    ctype_rules = [
        TypeRule(
            value=str(item.get("ctype", "")),
            patterns=[str(pattern) for pattern in item.get("patterns", [])],
            flag=item.get("flag"),
        )
        for item in data.get("ctype_rules", [])
    ]
    lang_rules = [
        TypeRule(
            value=str(item.get("lang", "")),
            patterns=[str(pattern) for pattern in item.get("patterns", [])],
            flag=item.get("flag"),
        )
        for item in data.get("lang_rules", [])
    ]
    version_rules = data.get("version_rules", {}) or {}
    return TypeRules(
        ctype_rules=ctype_rules,
        lang_rules=lang_rules,
        draft_patterns=[str(pattern) for pattern in version_rules.get("draft_patterns", [])],
        executed_patterns=[str(pattern) for pattern in version_rules.get("executed_patterns", [])],
        version_capture=[str(pattern) for pattern in version_rules.get("version_capture", [])],
    )


def matches_any(text: str, patterns: List[str]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def classify_path(rel_path: str, text: str, rules: TypeRules) -> Tuple[str, str, Optional[int], Optional[str], str]:
    haystack = f"{rel_path} {text}"
    ctype = "미분류"
    lang = "미상"
    source_signals = {}

    for rule in rules.ctype_rules:
        if matches_any(haystack, rule.patterns):
            ctype = rule.value
            source_signals["ctype"] = {"value": ctype, "patterns": rule.patterns}
            break

    for rule in rules.lang_rules:
        if matches_any(haystack, rule.patterns):
            lang = rule.value
            source_signals["lang"] = {"value": lang, "patterns": rule.patterns}
            break

    if lang == "미상" and text:
        korean_chars = len(re.findall(r"[가-힣]", text))
        ascii_letters = len(re.findall(r"[A-Za-z]", text))
        total = max(korean_chars + ascii_letters, 1)
        korean_ratio = korean_chars / total
        if korean_ratio > 0.30:
            lang = "국문"
        elif korean_ratio < 0.05 and ascii_letters:
            lang = "영문"
        else:
            lang = "국영문"
        source_signals["lang_heuristic"] = {"korean_ratio": round(korean_ratio, 3)}

    name = Path(rel_path).name
    is_draft = None
    if matches_any(name, rules.draft_patterns):
        is_draft = 1
    elif matches_any(name, rules.executed_patterns):
        is_draft = 0

    version_hint = None
    for pattern in rules.version_capture:
        try:
            match = re.search(pattern, name, re.IGNORECASE)
        except re.error:
            continue
        if match:
            version_hint = match.group(0)
            break

    return ctype, lang, is_draft, version_hint, json.dumps(source_signals, ensure_ascii=False)


def is_misc_path(path: Path, rules: TypeRules) -> bool:
    path_text = path.as_posix()
    return any(
        rule.flag == "exclude_by_default" and matches_any(path_text, rule.patterns)
        for rule in rules.ctype_rules
    )


def is_supported_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_indexable_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def iter_indexable_files(root: Path, include_misc: bool, rules: TypeRules) -> List[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if is_indexable_file(path)
        and (include_misc or not is_misc_path(path.relative_to(root), rules))
    )


def read_file_list(root: Path, file_list: Path, include_misc: bool, rules: TypeRules) -> List[Path]:
    paths: List[Path] = []
    for raw_line in file_list.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        path = (root / line).resolve()
        try:
            rel_path = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"file-list entry escapes root: {line}") from exc
        if not path.exists() or not path.is_file() or path.is_symlink():
            raise ValueError(f"file-list entry is not an existing file: {line}")
        if not is_indexable_file(path):
            continue
        if include_misc or not is_misc_path(rel_path, rules):
            paths.append(path)
    return sorted(set(paths))


def choose_candidates(root: Path, options: IndexOptions, rules: Optional[TypeRules] = None) -> Tuple[List[Path], bool]:
    rules = rules or load_type_rules()
    if options.file_list and options.sample is not None:
        raise ValueError("--file-list and --sample cannot be used together")

    if options.file_list:
        return read_file_list(root, options.file_list, options.include_misc, rules), False

    files = iter_indexable_files(root, options.include_misc, rules)
    if options.sample is not None:
        if options.sample < 0:
            raise ValueError("--sample must be >= 0")
        rng = random.Random(options.sample_seed)
        sample_pool = [path for path in files if path.suffix.lower() in SUPPORTED_EXTENSIONS]
        selected = rng.sample(sample_pool, min(options.sample, len(sample_pool)))
        return sorted(selected), False

    return files, True


def iter_docx_body_blocks(document: DocumentObject):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def normalize_paragraphs(paragraphs: List[str]) -> List[str]:
    normalized: List[str] = []
    for paragraph in paragraphs:
        text = normalize(paragraph)
        if text:
            normalized.append(text)
    return normalized


def extract_docx(path: Path) -> ExtractedDocument:
    try:
        document = Document(path)
    except (BadZipFile, PackageNotFoundError) as exc:
        return ExtractedDocument([], "error", "corrupt_docx", [str(exc)])
    except Exception as exc:
        return ExtractedDocument([], "error", "docx_extract_failed", [str(exc)])

    paragraphs: List[str] = []
    warnings: List[str] = []

    try:
        for block in iter_docx_body_blocks(document):
            if isinstance(block, Paragraph):
                paragraphs.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    cell_text = [normalize(cell.text) for cell in row.cells]
                    paragraphs.append(" | ".join(text for text in cell_text if text))
    except Exception as exc:
        return ExtractedDocument([], "error", "docx_extract_failed", [str(exc)])

    try:
        for section in document.sections:
            for paragraph in section.header.paragraphs:
                if normalize(paragraph.text):
                    paragraphs.append(f"[머리글] {paragraph.text}")
            for paragraph in section.footer.paragraphs:
                if normalize(paragraph.text):
                    paragraphs.append(f"[바닥글] {paragraph.text}")
    except Exception as exc:
        warnings.append(f"header_footer_extract_skipped: {exc}")

    warnings.append("footnote_extract_skipped")
    normalized = normalize_paragraphs(paragraphs)
    if not normalized:
        return ExtractedDocument([], "empty", "empty_text", warnings)
    return ExtractedDocument(normalized, "ok", None, warnings)


def extract_pdf(path: Path) -> ExtractedDocument:
    try:
        text = extract_text(path)
    except PDFEncryptionError as exc:
        return ExtractedDocument([], "error", "encrypted_pdf", [str(exc)])
    except (PDFSyntaxError, Exception) as exc:
        return ExtractedDocument([], "error", "pdf_extract_failed", [str(exc)])

    paragraphs = normalize_paragraphs(text.split("\n\n"))
    if not paragraphs:
        return ExtractedDocument([], "empty", "pdf_text_empty")
    return ExtractedDocument(paragraphs)


def extract_file(path: Path) -> ExtractedDocument:
    ext = path.suffix.lower()
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pdf":
        return extract_pdf(path)
    return ExtractedDocument([], "unsupported", "unsupported_ext")


def error_reason_for_os_error(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "permission_denied"
    return "unknown_error"


def write_txt_cache(out_dir: Path, file_key: str, paragraphs: List[str]) -> Path:
    txt_dir = out_dir / "txt"
    txt_dir.mkdir(parents=True, exist_ok=True)
    txt_path = txt_dir / f"{file_key}.txt"
    lines = [f"[¶{index}]\t{text}" for index, text in enumerate(paragraphs, start=1)]
    txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return txt_path


def record_file(
    conn: sqlite3.Connection,
    *,
    root: Path,
    path: Path,
    out_dir: Path,
    file_key: str,
    content_hash: str,
    extracted: ExtractedDocument,
    txt_path: Path,
    batch_label: Optional[str] = None,
    ctype: str = "미분류",
    lang: str = "미상",
    source_signals: str = "{}",
    is_draft: Optional[int] = None,
    version_hint: Optional[str] = None,
) -> None:
    stat = path.stat()
    rel_path = path.relative_to(root).as_posix()
    text_for_hash = "\n".join(extracted.paragraphs)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO files (
          file_key, path, folder, filename, ctype, lang, ext, size, mtime,
          txt_path, char_count, status, error_reason,
          source_signals, batch_label, content_hash, dup_group, is_draft,
          version_hint, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_key,
            rel_path,
            Path(rel_path).parent.as_posix() if Path(rel_path).parent.as_posix() != "." else "",
            path.name,
            ctype,
            lang,
            path.suffix.lower(),
            stat.st_size,
            stat.st_mtime,
            txt_path.relative_to(out_dir).as_posix(),
            len(text_for_hash),
            extracted.status,
            extracted.error_reason,
            source_signals,
            batch_label,
            content_hash,
            file_key,
            is_draft,
            version_hint,
            now,
        ),
    )

    conn.execute("DELETE FROM fts WHERE file_key = ?", (file_key,))
    if extracted.status == "ok":
        conn.executemany(
            "INSERT INTO fts(content, file_key, para) VALUES (?, ?, ?)",
            [
                (paragraph, file_key, index)
                for index, paragraph in enumerate(extracted.paragraphs, start=1)
            ],
        )


def load_existing_records(conn: sqlite3.Connection) -> List[ExistingRecord]:
    rows = conn.execute(
        """
        SELECT file_key, path, size, mtime, status, content_hash, txt_path
        FROM files
        """
    ).fetchall()
    return [ExistingRecord(*row) for row in rows]


def mark_missing(conn: sqlite3.Connection, file_key: str) -> None:
    conn.execute(
        "UPDATE files SET status = 'missing', error_reason = NULL WHERE file_key = ?",
        (file_key,),
    )
    conn.execute("DELETE FROM fts WHERE file_key = ?", (file_key,))


def rebuild_dup_groups(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT file_key, content_hash
        FROM files
        WHERE content_hash IS NOT NULL AND content_hash != ''
        ORDER BY file_key
        """
    ).fetchall()
    groups: Dict[str, List[str]] = {}
    for file_key, content_hash in rows:
        groups.setdefault(content_hash, []).append(file_key)
    for keys in groups.values():
        dup_group = min(keys)
        conn.executemany(
            "UPDATE files SET dup_group = ? WHERE file_key = ?",
            [(dup_group, key) for key in keys],
        )


def summarize_db(conn: sqlite3.Connection) -> Dict[str, object]:
    status_counts = dict(
        conn.execute("SELECT status, COUNT(*) FROM files GROUP BY status").fetchall()
    )
    batch_counts = dict(
        conn.execute(
            "SELECT COALESCE(batch_label, ''), COUNT(*) FROM files GROUP BY batch_label"
        ).fetchall()
    )
    error_counts = dict(
        conn.execute(
            """
            SELECT error_reason, COUNT(*)
            FROM files
            WHERE error_reason IS NOT NULL
            GROUP BY error_reason
            """
        ).fetchall()
    )
    duplicate_groups = conn.execute(
        """
        SELECT dup_group, COUNT(*)
        FROM files
        WHERE dup_group IS NOT NULL AND status != 'missing'
        GROUP BY dup_group
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC, dup_group
        """
    ).fetchall()
    stale_doc_meta = conn.execute(
        """
        SELECT COUNT(*)
        FROM doc_meta dm
        JOIN files f ON f.file_key = dm.file_key
        WHERE dm.txt_hash IS NOT NULL
          AND f.content_hash IS NOT NULL
          AND dm.txt_hash != f.content_hash
        """
    ).fetchone()[0]
    type_lang = conn.execute(
        """
        SELECT ctype, lang, COUNT(*)
        FROM files
        WHERE status != 'missing'
        GROUP BY ctype, lang
        ORDER BY ctype, lang
        """
    ).fetchall()
    unclassified_folders = conn.execute(
        """
        SELECT COALESCE(NULLIF(folder, ''), '.'), COUNT(*)
        FROM files
        WHERE ctype = '미분류' AND status != 'missing'
        GROUP BY COALESCE(NULLIF(folder, ''), '.')
        ORDER BY COUNT(*) DESC, 1
        """
    ).fetchall()
    return {
        "statuses": status_counts,
        "batch_labels": batch_counts,
        "errors": error_counts,
        "duplicate_groups": duplicate_groups,
        "stale_doc_meta": stale_doc_meta,
        "type_lang": type_lang,
        "unclassified_folders": unclassified_folders,
    }


def write_report(
    out_dir: Path,
    result: Dict[str, object],
    changes: ChangeReport,
    db_summary: Optional[Dict[str, object]],
) -> Path:
    report_path = unique_report_path(out_dir)
    lines = [
        "# Index Report",
        "",
        "## Run",
        "",
        f"- root: `{result['root']}`",
        f"- out: `{result['out']}`",
        f"- dry_run: `{result['dry_run']}`",
        f"- full: `{result['full']}`",
        f"- batch_label: `{result.get('batch_label') or ''}`",
        "",
        "## Changes",
        "",
        f"- new: {len(changes.new)}",
        f"- skipped: {len(changes.skipped)}",
        f"- moved: {len(changes.moved)}",
        f"- missing: {len(changes.missing)}",
        f"- restored: {len(changes.restored)}",
        f"- content_changed: {len(changes.content_changed)}",
        f"- excluded: {len(changes.excluded)}",
        f"- unsupported: {len(changes.unsupported)}",
        f"- errors: {len(changes.errors)}",
        "",
    ]
    for title, items in [
        ("New", changes.new),
        ("Moved", changes.moved),
        ("Missing", changes.missing),
        ("Restored", changes.restored),
        ("Content Changed", changes.content_changed),
        ("Excluded", changes.excluded),
        ("Unsupported", changes.unsupported),
        ("Errors", changes.errors),
    ]:
        lines.extend([f"## {title}", ""])
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- none")
        lines.append("")

    lines.extend(["## Database Summary", ""])
    if db_summary is None:
        lines.append("- dry-run: database not modified")
    else:
        lines.extend(["### Type x Language", ""])
        type_lang = db_summary["type_lang"]
        if type_lang:
            lines.extend(f"- {ctype} / {lang}: {count}" for ctype, lang, count in type_lang)
        else:
            lines.append("- none")
        lines.extend(["", "### Unclassified Folders", ""])
        unclassified = db_summary["unclassified_folders"]
        if unclassified:
            lines.extend(f"- {folder}: {count}" for folder, count in unclassified)
        else:
            lines.append("- none")
        lines.append("")
        lines.append(f"- status counts: `{db_summary['statuses']}`")
        lines.append(f"- error counts: `{db_summary['errors']}`")
        lines.append(f"- batch label counts: `{db_summary['batch_labels']}`")
        lines.append(f"- duplicate groups size>=2: `{db_summary['duplicate_groups']}`")
        lines.append(f"- stale doc_meta: `{db_summary['stale_doc_meta']}`")
    lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def unique_report_path(out_dir: Path) -> Path:
    stem = f"report_{datetime.now().strftime('%Y%m%d')}"
    first = out_dir / f"{stem}.md"
    if not first.exists():
        return first
    suffix = 2
    while True:
        candidate = out_dir / f"{stem}-{suffix}.md"
        if not candidate.exists():
            return candidate
        suffix += 1


def index_contracts(
    root: Union[str, Path],
    out: Union[str, Path],
    options: Optional[IndexOptions] = None,
) -> Dict[str, object]:
    options = options or IndexOptions()
    root_path = Path(root).resolve()
    out_dir = Path(out).resolve()

    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"root must be an existing directory: {root_path}")

    rules = load_type_rules(Path.cwd())
    candidates, is_full_scan = choose_candidates(root_path, options, rules)
    db_path = out_dir / "catalog.sqlite"
    if not options.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        db_path = initialize_catalog(db_path)

    indexed = 0
    skipped = 0
    statuses: Dict[str, int] = {}
    warnings: Dict[str, int] = {}
    changes = ChangeReport()
    db_summary: Optional[Dict[str, object]] = None

    if options.dry_run and not db_path.exists():
        existing_records: List[ExistingRecord] = []
        conn = None
    else:
        if options.dry_run:
            conn = sqlite3.connect(db_path)
        else:
            conn = sqlite3.connect(db_path)

    try:
        if conn is not None and options.full and not options.dry_run:
            conn.execute("DELETE FROM fts")
            conn.execute("DELETE FROM files")
            conn.commit()

        existing_records = load_existing_records(conn) if conn is not None else []
        by_path = {record.path: record for record in existing_records}
        by_key = {record.file_key: record for record in existing_records}
        seen_paths = set()
        seen_keys = set()

        for path in candidates:
            rel_path = path.relative_to(root_path).as_posix()
            if path.suffix.lower() in ZIP_EXTENSIONS:
                changes.excluded.append(rel_path)
                continue

            seen_paths.add(rel_path)
            try:
                stat = path.stat()
            except OSError as exc:
                changes.errors.append(f"{rel_path}: {error_reason_for_os_error(exc)}")
                continue

            existing_at_path = by_path.get(rel_path)
            if (
                existing_at_path
                and existing_at_path.status != "missing"
                and existing_at_path.size == stat.st_size
                and existing_at_path.mtime == stat.st_mtime
                and not options.full
            ):
                skipped += 1
                changes.skipped.append(rel_path)
                seen_keys.add(existing_at_path.file_key)
                continue

            try:
                file_bytes = path.read_bytes()
            except OSError as exc:
                reason = error_reason_for_os_error(exc)
                file_key = sha256_short(f"unreadable:{rel_path}".encode("utf-8"))
                extracted = ExtractedDocument([], "error", reason, [str(exc)])
                content_hash = hash_text("")
                txt_path = out_dir / "txt" / f"{file_key}.txt"
                if conn is not None and not options.dry_run:
                    txt_path = write_txt_cache(out_dir, file_key, [])
                    ctype, lang, is_draft, version_hint, source_signals = classify_path(
                        rel_path, "", rules
                    )
                    record_file(
                        conn,
                        root=root_path,
                        path=path,
                        out_dir=out_dir,
                        file_key=file_key,
                        content_hash=content_hash,
                        extracted=extracted,
                        txt_path=txt_path,
                        batch_label=options.batch_label,
                        ctype=ctype,
                        lang=lang,
                        source_signals=source_signals,
                        is_draft=is_draft,
                        version_hint=version_hint,
                    )
                indexed += 1
                statuses[extracted.status] = statuses.get(extracted.status, 0) + 1
                changes.errors.append(f"{rel_path}: {reason}")
                continue

            file_key = sha256_short(file_bytes)
            seen_keys.add(file_key)
            existing_same_key = by_key.get(file_key)

            if (
                existing_at_path
                and existing_at_path.file_key != file_key
                and existing_at_path.status != "missing"
            ):
                changes.content_changed.append(
                    f"{rel_path}: {existing_at_path.file_key}->{file_key}"
                )
                if conn is not None and not options.dry_run:
                    mark_missing(conn, existing_at_path.file_key)
            elif existing_same_key and existing_same_key.path != rel_path:
                changes.moved.append(f"{existing_same_key.path}->{rel_path}")
            elif (
                (existing_at_path and existing_at_path.status == "missing")
                or (existing_same_key and existing_same_key.status == "missing")
            ):
                changes.restored.append(rel_path)
            elif not existing_at_path and not existing_same_key:
                changes.new.append(rel_path)

            extracted = extract_file(path)
            text_for_hash = "\n".join(extracted.paragraphs)
            content_hash = hash_text(text_for_hash)
            txt_path = out_dir / "txt" / f"{file_key}.txt"
            ctype, lang, is_draft, version_hint, source_signals = classify_path(
                rel_path, text_for_hash, rules
            )
            if extracted.status == "unsupported":
                changes.unsupported.append(rel_path)

            if conn is not None and not options.dry_run:
                txt_path = write_txt_cache(out_dir, file_key, extracted.paragraphs)
                record_file(
                    conn,
                    root=root_path,
                    path=path,
                    out_dir=out_dir,
                    file_key=file_key,
                    content_hash=content_hash,
                    extracted=extracted,
                    txt_path=txt_path,
                    batch_label=options.batch_label,
                    ctype=ctype,
                    lang=lang,
                    source_signals=source_signals,
                    is_draft=is_draft,
                    version_hint=version_hint,
                )

            indexed += 1
            statuses[extracted.status] = statuses.get(extracted.status, 0) + 1
            for warning in extracted.warnings:
                key = warning.split(":", 1)[0]
                warnings[key] = warnings.get(key, 0) + 1

        if is_full_scan:
            current_supported_paths = set(seen_paths)
            for record in existing_records:
                if (
                    record.status != "missing"
                    and record.path not in current_supported_paths
                    and record.file_key not in seen_keys
                ):
                    changes.missing.append(record.path)
                    if conn is not None and not options.dry_run:
                        mark_missing(conn, record.file_key)

        if conn is not None and not options.dry_run:
            rebuild_dup_groups(conn)
            conn.commit()
            db_summary = summarize_db(conn)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        elif conn is not None:
            db_summary = summarize_db(conn)
    finally:
        if conn is not None:
            conn.close()

    result = {
        "root": str(root_path),
        "out": str(out_dir),
        "db": str(db_path),
        "indexed": indexed,
        "skipped": skipped,
        "dry_run": options.dry_run,
        "full": options.full,
        "batch_label": options.batch_label,
        "statuses": statuses,
        "warnings": warnings,
        "changes": {
            "new": len(changes.new),
            "skipped": len(changes.skipped),
            "moved": len(changes.moved),
            "missing": len(changes.missing),
            "restored": len(changes.restored),
            "content_changed": len(changes.content_changed),
            "excluded": len(changes.excluded),
            "unsupported": len(changes.unsupported),
            "errors": len(changes.errors),
        },
    }
    report_path = write_report(out_dir, result, changes, db_summary)
    result["report"] = str(report_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index DOCX/PDF contracts.")
    parser.add_argument("--root", required=True, help="Root folder to scan.")
    parser.add_argument("--out", required=True, help="Output cs_index folder.")
    parser.add_argument("--include-misc", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--batch-label")
    parser.add_argument("--file-list", type=Path)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--sample-seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = index_contracts(
            args.root,
            args.out,
            IndexOptions(
                include_misc=args.include_misc,
                full=args.full,
                batch_label=args.batch_label,
                file_list=args.file_list,
                sample=args.sample,
                sample_seed=args.sample_seed,
                dry_run=args.dry_run,
            ),
        )
    except (CatalogError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
