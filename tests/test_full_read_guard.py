import sqlite3
from contextlib import closing

from lib.full_read_guard import (
    explicit_rw_headings,
    full_read_heading_omissions,
    owner_not_rw_subdomains,
)
from tests.test_v4_search import make_index


def _write(out, letter, paragraphs):
    path = out / "txt" / f"{letter}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f"[¶{n}]\t{text}" for n, text in paragraphs),
        encoding="utf-8",
    )


def test_explicit_heading_detector_ignores_long_prose(tmp_path):
    out = make_index(tmp_path)
    _write(
        out,
        "b",
        [
            (1, "Section 4.14 Tax Matters 27"),
            (2, "Environmental and Health and Safety Matters"),
            (3, "The Company is in compliance with all Environmental Laws."),
            (
                4,
                "The parties considered the economic and political environment "
                "when negotiating this agreement, but this is ordinary prose " * 3,
            ),
        ],
    )
    found = explicit_rw_headings(out, "b" * 16, "txt/b.txt")
    assert "RW.TAX" in found
    assert "RW.ENVIRONMENT" in found
    assert [x["para"] for x in found["RW.ENVIRONMENT"]] == [2]


def test_heading_omission_disappears_when_subdomain_item_exists(tmp_path):
    out = make_index(tmp_path)
    _write(
        out,
        "a",
        [
            (1, "Labor and Employment Matters"),
            (2, "Tax Matters"),
            (3, "The Company has filed all Tax Returns and paid all Taxes."),
        ],
    )
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        omissions = full_read_heading_omissions(conn, out, "a" * 16)
    assert "RW.TAX" in omissions
    assert "RW.LABOR" not in omissions


def test_owner_not_rw_verdict_suppresses_reviewed_false_positive(tmp_path):
    out = make_index(tmp_path)
    _write(
        out,
        "a",
        [
            (1, "Section 3 Covenants of the Company"),
            (2, "3.3 Insurance"),
            (3, "The Company shall obtain and maintain insurance."),
        ],
    )
    data_dir = out.parent / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "full_read_heading_owner_verdicts.json").write_text(
        '{"aaaaaaaaaaaaaaaa":{"RW.INSURANCE":{"verdict":"not_rw"}}}',
        encoding="utf-8",
    )
    with closing(sqlite3.connect(out / "catalog.sqlite")) as conn:
        omissions = full_read_heading_omissions(conn, out, "a" * 16)
    assert owner_not_rw_subdomains(out, "a" * 16) == {"RW.INSURANCE"}
    assert omissions == {}
