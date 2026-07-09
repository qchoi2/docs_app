from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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

from lib.catalog import CatalogError, initialize_catalog
from lib.normalize import normalize


SUPPORTED_EXTENSIONS = {".docx", ".pdf"}
MISC_EXCLUDE_PATTERNS = ("99_MnA_계약_외", "Sample_Docs")


@dataclass
class ExtractedDocument:
    paragraphs: list[str]
    status: str = "ok"
    error_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExistingRecord:
    file_key: str
    path: str
    size: int | None
    mtime: float | None
    status: str
    content_hash: str | None
    txt_path: str | None


@dataclass
class IndexOptions:
    include_misc: bool = False
    full: bool = False
    batch_label: str | None = None
    file_list: Path | None = None
    sample: int | None = None
    sample_seed: int = 0
    dry_run: bool = False


@dataclass
class ChangeReport:
    new: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    content_changed: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def hash_text(text: str) -> str:
    return sha256_short(text.encode("utf-8"))


def is_misc_path(path: Path) -> bool:
    path_text = path.as_posix()
    return any(pattern in path_text for pattern in MISC_EXCLUDE_PATTERNS)


def is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def iter_supported_files(root: Path, include_misc: bool = False) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if is_supported_file(path)
        and (include_misc or not is_misc_path(path.relative_to(root)))
    )


def read_file_list(root: Path, file_list: Path, include_misc: bool) -> list[Path]:
    paths: list[Path] = []
    for raw_line in file_list.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        path = (root / line).resolve()
        try:
            rel_path = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"file-list entry escapes root: {line}") from exc
        if not path.exists() or not path.is_file():
            raise ValueError(f"file-list entry is not an existing file: {line}")
        if not is_supported_file(path):
            continue
        if include_misc or not is_misc_path(rel_path):
            paths.append(path)
    return sorted(set(paths))


def choose_candidates(root: Path, options: IndexOptions) -> tuple[list[Path], bool]:
    if options.file_list and options.sample is not None:
        raise ValueError("--file-list and --sample cannot be used together")

    if options.file_list:
        return read_file_list(root, options.file_list, options.include_misc), False

    files = iter_supported_files(root, options.include_misc)
    if options.sample is not None:
        if options.sample < 0:
            raise ValueError("--sample must be >= 0")
        rng = random.Random(options.sample_seed)
        selected = rng.sample(files, min(options.sample, len(files)))
        return sorted(selected), False

    return files, True


def iter_docx_body_blocks(document: DocumentObject):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def normalize_paragraphs(paragraphs: list[str]) -> list[str]:
    normalized: list[str] = []
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

    paragraphs: list[str] = []
    warnings: list[str] = []

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


def write_txt_cache(out_dir: Path, file_key: str, paragraphs: list[str]) -> Path:
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
    batch_label: str | None = None,
) -> None:
    stat = path.stat()
    rel_path = path.relative_to(root).as_posix()
    text_for_hash = "\n".join(extracted.paragraphs)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO files (
          file_key, path, folder, filename, ext, size, mtime,
          txt_path, char_count, status, error_reason,
          content_hash, dup_group, batch_label, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_key,
            rel_path,
            Path(rel_path).parent.as_posix() if Path(rel_path).parent.as_posix() != "." else "",
            path.name,
            path.suffix.lower(),
            stat.st_size,
            stat.st_mtime,
            txt_path.relative_to(out_dir).as_posix(),
            len(text_for_hash),
            extracted.status,
            extracted.error_reason,
            content_hash,
            file_key,
            batch_label,
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


def load_existing_records(conn: sqlite3.Connection) -> list[ExistingRecord]:
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
    groups: dict[str, list[str]] = {}
    for file_key, content_hash in rows:
        groups.setdefault(content_hash, []).append(file_key)
    for keys in groups.values():
        dup_group = min(keys)
        conn.executemany(
            "UPDATE files SET dup_group = ? WHERE file_key = ?",
            [(dup_group, key) for key in keys],
        )


def summarize_db(conn: sqlite3.Connection) -> dict[str, object]:
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
    return {
        "statuses": status_counts,
        "batch_labels": batch_counts,
        "errors": error_counts,
        "duplicate_groups": duplicate_groups,
        "stale_doc_meta": stale_doc_meta,
    }


def write_report(
    out_dir: Path,
    result: dict[str, object],
    changes: ChangeReport,
    db_summary: dict[str, object] | None,
) -> Path:
    report_path = out_dir / f"report_{datetime.now().strftime('%Y%m%d')}.md"
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
        lines.append(f"- status counts: `{db_summary['statuses']}`")
        lines.append(f"- error counts: `{db_summary['errors']}`")
        lines.append(f"- batch label counts: `{db_summary['batch_labels']}`")
        lines.append(f"- duplicate groups size>=2: `{db_summary['duplicate_groups']}`")
        lines.append(f"- stale doc_meta: `{db_summary['stale_doc_meta']}`")
    lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def index_contracts(
    root: str | Path,
    out: str | Path,
    options: IndexOptions | None = None,
) -> dict[str, object]:
    options = options or IndexOptions()
    root_path = Path(root).resolve()
    out_dir = Path(out).resolve()

    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"root must be an existing directory: {root_path}")

    candidates, is_full_scan = choose_candidates(root_path, options)
    db_path = out_dir / "catalog.sqlite"
    if not options.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        db_path = initialize_catalog(db_path)

    indexed = 0
    skipped = 0
    statuses: dict[str, int] = {}
    warnings: dict[str, int] = {}
    changes = ChangeReport()
    db_summary: dict[str, object] | None = None

    if options.dry_run and not db_path.exists():
        existing_records: list[ExistingRecord] = []
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
        seen_paths: set[str] = set()
        seen_keys: set[str] = set()

        for path in candidates:
            rel_path = path.relative_to(root_path).as_posix()
            seen_paths.add(rel_path)
            stat = path.stat()
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

            file_bytes = path.read_bytes()
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


def main(argv: list[str] | None = None) -> int:
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
