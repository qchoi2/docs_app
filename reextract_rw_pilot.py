"""RW re-extraction PILOT for 현대호텔 SPA [19cb2dd280ab0b15] (2026-07-28).

Demonstrates the root fix ② on one document that Gate B proved a false absence
(env representation present at ¶115 but V4 extracted only 3 RW items → absence
wrongly said "no environment rep"). Reads the seller-representation article
(제6조, ¶74–115), which contains ~19 representations, and ADDS the ~17 that V4
missed (labor, environment, insurance, assets, compliance, permits, contracts,
litigation, financial, capitalization, related-party, authority) as approved
RW items, then marks RW coverage genuinely complete.

Surgical & safe:
  * WAL-safe backup before any write.
  * ADD-only (does not delete the 3 existing RW items, which are linked to
    resolved taxonomy candidates) — inserts item_refs RWRX-01..17.
  * All taxonomy_ids verified to exist; schema fields match validate_v4_result.
  * Idempotent: re-running first clears prior RWRX-* rows.

Run under owner supervision:  python reextract_rw_pilot.py
Verify after:  python eval_v4_gate.py --pooled   (and inspect the doc's RW items)
Rollback:  restore cs_index/.backups/catalog.pre_rw_pilot_*.sqlite
"""

import sqlite3
import re
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

from lib.console import configure_utf8_stdio

FILE_KEY = "19cb2dd280ab0b15"
OUT = Path("cs_index")

# (loc ¶, taxonomy_id, proposition, statement_polarity, subject) — the reps V4 missed.
REPS = [
    (78, "RW.AUTHORITY", "매도인은 적법하게 설립되어 유효하게 존속한다.", "affirmative", "매도인"),
    (80, "RW.AUTHORITY", "매도인은 계약 체결·이행에 필요한 권한과 자격, 내부수권을 갖추었고 계약은 구속력이 있다.", "affirmative", "매도인"),
    (84, "RW.CAPITALIZATION", "매도인은 대상주식을 적법·유효하게 소유하며 제한부담이 없다.", "affirmative", "매도인"),
    (86, "RW.LITIGATION", "매도인에 대하여 본건 거래를 금지·제한하는 법적 절차가 존재하지 아니한다.", "none_exist", "매도인"),
    (89, "RW.AUTHORITY", "대상회사는 한국 법규에 따라 적법 설립·유효 존속하며 사업 수행 능력·자격을 가진다.", "affirmative", "대상회사"),
    (91, "RW.AUTHORITY", "본 계약 체결·이행에 필요한 정부승인이 없고 조직문서·법규·계약에 위반되지 아니한다.", "affirmative", "대상회사"),
    (93, "RW.CAPITALIZATION", "대상회사의 수권·발행주식 내역이 진술과 같고 대상주식은 적법·완납되었다.", "affirmative", "대상회사"),
    (95, "RW.FINANCIAL", "기준 재무제표는 K-IFRS에 따라 작성되어 재무상태·경영성과를 공정하게 표시한다.", "affirmative", "대상회사"),
    (97, "RW.LITIGATION", "대상회사·임원에 관하여 진행 중이거나 제기 우려 있는 법적 절차가 존재하지 아니한다.", "none_exist", "대상회사"),
    (101, "RW.PERMITS", "대상회사는 사업에 필요한 정부승인을 적법 취득·보유하고 조건을 준수한다.", "affirmative", "대상회사"),
    (103, "RW.CONTRACTS", "중요계약은 적법 체결되어 유효·구속력·집행가능하며 최신본이 제공되었다.", "affirmative", "대상회사"),
    (105, "RW.ASSETS", "대상회사는 사업용 자산에 적법·하자없는 소유·사용권을 가지며 제한부담이 없다.", "affirmative", "대상회사"),
    (107, "RW.COMPLIANCE", "대상회사는 관련 법령을 준수하며 위반·제재 사항이 존재하지 아니한다.", "affirmative", "대상회사"),
    (109, "RW.LABOR", "대상회사는 근로기준법 등 인사·노무 법률·내부규정·근로계약을 준수하고 임금·수당·퇴직금 등 지급의무를 이행한다.", "affirmative", "대상회사"),
    (111, "RW.RELATED_PARTY", "특수관계인·계열회사와의 거래는 제3자간 거래조건에 따라 이루어졌고 사본이 제공되었다.", "affirmative", "대상회사"),
    (113, "RW.INSURANCE", "대상회사의 모든 보험계약은 완전한 효력을 가지며 보험료가 완납되었고 해지 통지·사유가 없다.", "affirmative", "대상회사"),
    (115, "RW.ENVIRONMENT", "대상회사는 환경·안전·보건 정부승인을 취득하고 관련 법령·인허가 조건을 준수하며 위반 통지·제재가 없다.", "affirmative", "대상회사"),
]

COLS = [
    "file_key", "item_ref", "family", "taxonomy_id", "proposition", "statement_polarity",
    "subject_role", "counterparty_role", "action", "object_type", "effective_time",
    "source_kind", "source_id", "source_name", "source_ref", "parent_clause_ref",
    "related_item_ref", "qualifier_json", "verbatim", "loc_start", "loc_end",
    "normalized_json", "confidence", "txt_hash", "taxonomy_version",
    "extractor_version", "prompt_version", "review_status", "created_at", "updated_at",
]


def main() -> int:
    configure_utf8_stdio()
    db = OUT / "catalog.sqlite"

    # 1. WAL-safe backup
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = OUT / f".backups/catalog.pre_rw_pilot_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
        s.backup(d)
    print(f"backup: {backup.name}")

    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    txt_path = ro.execute("SELECT txt_path FROM files WHERE file_key=?", (FILE_KEY,)).fetchone()[0]
    content_hash = ro.execute("SELECT content_hash FROM files WHERE file_key=?", (FILE_KEY,)).fetchone()[0]
    tax_version = ro.execute("SELECT MAX(taxonomy_version) FROM v4_clause_item").fetchone()[0] or 19
    known = {r[0] for r in ro.execute("SELECT taxonomy_id FROM v4_taxonomy_node")}
    for _, tid, *_ in REPS:
        assert tid in known, f"unknown taxonomy_id: {tid}"

    paras = {}
    for line in (OUT / txt_path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[¶(\d+)\]\t(.*)", line)
        if m:
            paras[int(m.group(1))] = m.group(2)

    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "DELETE FROM v4_clause_item WHERE file_key=? AND item_ref LIKE 'RWRX-%'",
            (FILE_KEY,),
        )
        for i, (loc, tid, prop, pol, subj) in enumerate(REPS, 1):
            row = {
                "file_key": FILE_KEY, "item_ref": f"RWRX-{i:02d}", "family": "RW",
                "taxonomy_id": tid, "proposition": prop, "statement_polarity": pol,
                "subject_role": subj, "counterparty_role": "매수인", "action": "진술 및 보장",
                "object_type": None, "effective_time": "본 계약 체결일 및 거래종결일",
                "source_kind": "body", "source_id": None, "source_name": None,
                "source_ref": None, "parent_clause_ref": "제6조", "related_item_ref": None,
                "qualifier_json": "{}", "verbatim": paras.get(loc, prop)[:1000],
                "loc_start": loc, "loc_end": loc, "normalized_json": "{}",
                "confidence": "high", "txt_hash": content_hash, "taxonomy_version": tax_version,
                "extractor_version": "claude-rw-reextract-pilot-20260728",
                "prompt_version": "extract_prompt_v4_rw_addendum",
                "review_status": "approved", "created_at": now, "updated_at": now,
            }
            conn.execute(
                f"INSERT INTO v4_clause_item({','.join(COLS)}) "
                f"VALUES ({','.join('?' for _ in COLS)})",
                [row[c] for c in COLS],
            )
        conn.execute(
            "UPDATE v4_document_coverage SET body_status='complete', "
            "reason='RW 하위영역 전수 재추출 (pilot 2026-07-28)' "
            "WHERE file_key=? AND family='RW'",
            (FILE_KEY,),
        )
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM v4_clause_item WHERE file_key=? AND family='RW'",
            (FILE_KEY,),
        ).fetchone()[0]
        doms = sorted({
            r[0].split(".")[1]
            for r in conn.execute(
                "SELECT taxonomy_id FROM v4_clause_item WHERE file_key=? AND family='RW'",
                (FILE_KEY,),
            )
        })
        print(f"RW items now: {n}  domains: {doms}")
        print("integrity:", conn.execute("PRAGMA integrity_check").fetchone()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
