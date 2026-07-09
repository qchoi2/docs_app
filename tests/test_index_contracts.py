import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

from docx import Document

from index_contracts import index_contracts


def short_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def write_pdf(path: Path, text: str | None) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    ]

    if text is None:
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << >> >>"
        )
    else:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        b"trailer\n"
        + f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + str(xref_at).encode("ascii")
        + b"\n%%EOF\n"
    )
    path.write_bytes(bytes(pdf))


def read_rows(db_path: Path, query: str):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(query).fetchall()


def test_indexes_synthetic_docx_paragraphs(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()

    docx_path = root / "simple.docx"
    document = Document()
    document.add_paragraph("First paragraph")
    document.add_paragraph("Second paragraph")
    document.save(docx_path)

    result = index_contracts(root, out)

    file_key = short_sha256(docx_path.read_bytes())
    txt_path = out / "txt" / f"{file_key}.txt"
    assert result["statuses"] == {"ok": 1}
    assert txt_path.read_text(encoding="utf-8").splitlines() == [
        "[¶1]\tFirst paragraph",
        "[¶2]\tSecond paragraph",
    ]

    rows = read_rows(out / "catalog.sqlite", "SELECT status, path FROM files")
    assert rows == [("ok", "simple.docx")]
    fts_rows = read_rows(
        out / "catalog.sqlite", "SELECT content, para FROM fts ORDER BY para"
    )
    assert fts_rows == [("First paragraph", 1), ("Second paragraph", 2)]


def test_docx_tables_keep_document_order_and_row_paragraphs(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()

    docx_path = root / "table.docx"
    document = Document()
    document.add_paragraph("Before table")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "A1"
    table.cell(0, 1).text = "B1"
    table.cell(1, 0).text = "A2"
    table.cell(1, 1).text = "B2"
    document.add_paragraph("After table")
    document.save(docx_path)

    index_contracts(root, out)

    file_key = short_sha256(docx_path.read_bytes())
    txt_lines = (out / "txt" / f"{file_key}.txt").read_text(encoding="utf-8").splitlines()
    assert txt_lines == [
        "[¶1]\tBefore table",
        "[¶2]\tA1 | B1",
        "[¶3]\tA2 | B2",
        "[¶4]\tAfter table",
    ]


def test_indexes_text_pdf(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()

    pdf_path = root / "text.pdf"
    write_pdf(pdf_path, "PDF text fixture")

    index_contracts(root, out)

    file_key = short_sha256(pdf_path.read_bytes())
    txt_text = (out / "txt" / f"{file_key}.txt").read_text(encoding="utf-8")
    assert "[¶1]\tPDF text fixture" in txt_text
    rows = read_rows(out / "catalog.sqlite", "SELECT status FROM files")
    assert rows == [("ok",)]
    fts_rows = read_rows(out / "catalog.sqlite", "SELECT file_key FROM fts")
    assert fts_rows == [(file_key,)]


def test_empty_pdf_is_recorded_without_fts_rows(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()

    pdf_path = root / "blank.pdf"
    write_pdf(pdf_path, None)

    index_contracts(root, out)

    file_key = short_sha256(pdf_path.read_bytes())
    assert (out / "txt" / f"{file_key}.txt").read_text(encoding="utf-8") == ""
    file_rows = read_rows(
        out / "catalog.sqlite", "SELECT status, error_reason FROM files"
    )
    assert file_rows == [("empty", "pdf_text_empty")]
    fts_rows = read_rows(out / "catalog.sqlite", "SELECT file_key FROM fts")
    assert fts_rows == []
