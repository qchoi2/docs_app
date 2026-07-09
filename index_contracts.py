from __future__ import annotations

import argparse
import hashlib
import json
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


@dataclass
class ExtractedDocument:
    paragraphs: list[str]
    status: str = "ok"
    error_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def hash_text(text: str) -> str:
    return sha256_short(text.encode("utf-8"))


def iter_supported_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


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
          content_hash, dup_group, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def index_contracts(root: str | Path, out: str | Path) -> dict[str, object]:
    root_path = Path(root).resolve()
    out_dir = Path(out).resolve()

    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"root must be an existing directory: {root_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = initialize_catalog(out_dir / "catalog.sqlite")

    indexed = 0
    statuses: dict[str, int] = {}
    warnings: dict[str, int] = {}

    with closing(sqlite3.connect(db_path)) as conn:
        for path in iter_supported_files(root_path):
            file_bytes = path.read_bytes()
            file_key = sha256_short(file_bytes)
            extracted = extract_file(path)
            text_for_hash = "\n".join(extracted.paragraphs)
            content_hash = hash_text(text_for_hash)
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
            )

            indexed += 1
            statuses[extracted.status] = statuses.get(extracted.status, 0) + 1
            for warning in extracted.warnings:
                key = warning.split(":", 1)[0]
                warnings[key] = warnings.get(key, 0) + 1

        conn.commit()

    return {
        "root": str(root_path),
        "out": str(out_dir),
        "db": str(db_path),
        "indexed": indexed,
        "statuses": statuses,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index DOCX/PDF contracts.")
    parser.add_argument("--root", required=True, help="Root folder to scan.")
    parser.add_argument("--out", required=True, help="Output cs_index folder.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = index_contracts(args.root, args.out)
    except (CatalogError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
