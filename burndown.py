"""V4 번다운 지표 — "얼마나 남았나 · 왜 막혔나"를 역산 없이 상시 산출한다.

.docs/PLAN_REVIEW_20260727.md 권고 5. 소유자가 매 세션 ad-hoc SQL로 다시 뽑던
숫자(대상유형 진행률, family별 coverage, 부재 질의 가능/차단, 후보 backlog,
RW 재추출 진척)를 하나의 read-only 도구로 고정한다.

원칙
- **읽기 전용.** catalog.sqlite는 `v4_search.connect_v4_ro`(mode=ro URI)로만 연다.
- **규칙을 재구현하지 않는다.** 부재 적격성은 `v4_search._bulk_coverage_states`
  ·`_blocking_pending_candidates`·`ABSENCE_UNVERIFIED_FAMILIES`를 그대로 호출한다.
  대시보드가 실제 검색 동작과 어긋날 수 없게 하기 위함이다. 대상유형 판정도
  `run_v4_expansion.expansion_contract_type`을 재사용한다.
- **모든 숫자는 추적 가능해야 한다.** JSON은 백분율이 아니라 분자/분모를 담는다.
- **산출 불가는 null + 사유.** 현재 데이터로 계산할 수 없는 지표는 값을 지어내지
  않고 `<name>` = null, `<name>_unavailable_reason` = 사유 문자열로 내보낸다.

사용:
    python burndown.py --out cs_index [--json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from lib.console import configure_utf8_stdio
from run_v4_expansion import (
    TYPE_PRIORITY,
    expansion_contract_type,
    is_primary_contract_path,
)
from v4_search import (
    ABSENCE_UNVERIFIED_FAMILIES,
    FAMILIES,
    V4SearchError,
    _blocking_pending_candidates,
    _bulk_coverage_states,
    connect_v4_ro,
)


# V4_PLAN 원계획 4유형 vs §6에서 편입 확정된 CB/BW/EB 계열.
# PLAN_REVIEW(2026-07-27)의 "대상유형 782/1,623"은 core 4유형 기준이다.
CORE_TYPES = ("SPA", "SSA", "SHA", "ATA/BTA")
SCOPE_ADDED_TYPES = tuple(t for t in TYPE_PRIORITY if t not in CORE_TYPES)
FAMILY_ORDER = ("RW", "CP", "COV", "DEF", "PAY", "REM")

# RW 재추출(store_rw_reextraction.py --mode replace)이 붙이는 item_ref 접두어와,
# 재추출 대상 표식(plan_rw_reextraction.py가 매니페스트를 뽑는 기준).
RW_REEXTRACT_ITEM_PREFIX = "RWRX-"
RW_AUDIT_PENDING_MARKER = "rw_subdomain_audit_pending"
RW_RESULT_DIRNAME = "rw_reextract_results"

assert set(FAMILY_ORDER) == FAMILIES, "FAMILY_ORDER must mirror v4_search.FAMILIES"


def _percent(numerator: int, denominator: int) -> Optional[float]:
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def _progress(evaluated: int, total: int) -> Dict[str, object]:
    return {
        "evaluated": evaluated,
        "total": total,
        "remaining": total - evaluated,
        "percent": _percent(evaluated, total),
    }


def _meta(conn: sqlite3.Connection) -> Dict[str, object]:
    rows = {str(row[0]): row[1] for row in conn.execute("SELECT key,value FROM v4_meta")}
    meta: Dict[str, object] = {}
    for key in ("taxonomy_version", "schema_version", "schema_revision"):
        value = rows.get(key)
        if value is None:
            meta[key] = None
            meta[f"{key}_unavailable_reason"] = f"v4_meta에 '{key}' 키가 없음"
        else:
            meta[key] = value
    return meta


def target_documents(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    """The V4 target population, one row per dup_group representative.

    Mirrors ``run_v4_expansion.select_expansion`` eligibility: status='ok',
    extracted text present, effective contract type in TYPE_PRIORITY, deduped by
    dup_group. The ancillary-path filter is recorded per row (``primary``)
    rather than applied, because PLAN_REVIEW's 1,623 denominator counts every
    typed document; the primary-only subtotal is reported alongside it.
    """
    evaluated = {
        str(row[0])
        for row in conn.execute("SELECT DISTINCT file_key FROM v4_document_coverage")
    }
    eligible = set(TYPE_PRIORITY)
    seen_groups: set[str] = set()
    docs: List[Dict[str, object]] = []
    for row in conn.execute(
        """
        SELECT f.file_key,f.path,f.ctype,f.lang,f.dup_group,f.content_hash
        FROM files f
        WHERE f.status='ok' AND f.txt_path IS NOT NULL
        ORDER BY f.ctype,f.lang,f.file_key
        """
    ):
        path = str(row["path"] or "")
        target_ctype = expansion_contract_type(str(row["ctype"] or ""), path)
        if target_ctype not in eligible:
            continue
        group = str(row["dup_group"] or row["file_key"])
        if group in seen_groups:
            continue
        seen_groups.add(group)
        file_key = str(row["file_key"])
        docs.append(
            {
                "file_key": file_key,
                "content_hash": row["content_hash"],
                "target_ctype": target_ctype,
                "lang": row["lang"],
                "primary": is_primary_contract_path(path),
                "evaluated": file_key in evaluated,
            }
        )
    return docs


def type_progress(docs: Sequence[Dict[str, object]]) -> Dict[str, object]:
    total = Counter()
    evaluated = Counter()
    primary_total = Counter()
    primary_evaluated = Counter()
    for doc in docs:
        ctype = str(doc["target_ctype"])
        total[ctype] += 1
        if doc["evaluated"]:
            evaluated[ctype] += 1
        if doc["primary"]:
            primary_total[ctype] += 1
            if doc["evaluated"]:
                primary_evaluated[ctype] += 1

    def group(names: Sequence[str]) -> Dict[str, object]:
        summary = _progress(
            sum(evaluated[name] for name in names),
            sum(total[name] for name in names),
        )
        summary["primary_only"] = _progress(
            sum(primary_evaluated[name] for name in names),
            sum(primary_total[name] for name in names),
        )
        return summary

    by_type = []
    for ctype in TYPE_PRIORITY:
        row = {"ctype": ctype}
        row.update(group([ctype]))
        by_type.append(row)
    return {
        "definition": (
            "files.status='ok' AND txt_path IS NOT NULL, "
            "run_v4_expansion.expansion_contract_type in TYPE_PRIORITY, "
            "dup_group 대표 1건; evaluated = v4_document_coverage 행 존재"
        ),
        "overall": group(TYPE_PRIORITY),
        "core_planned": group(CORE_TYPES),
        "scope_added": group(SCOPE_ADDED_TYPES),
        "by_type": by_type,
    }


def family_coverage(
    conn: sqlite3.Connection, docs: Sequence[Dict[str, object]]
) -> Dict[str, object]:
    """Body/annex coverage status counts per family (§2 requires both)."""
    target_keys = {str(doc["file_key"]) for doc in docs}
    families: Dict[str, object] = {}
    for family in FAMILY_ORDER:
        body: Counter = Counter()
        annex: Counter = Counter()
        target_body: Counter = Counter()
        target_annex: Counter = Counter()
        rows = 0
        target_rows = 0
        for row in conn.execute(
            "SELECT file_key,body_status,annex_status FROM v4_document_coverage "
            "WHERE family=?",
            (family,),
        ):
            rows += 1
            body_status = str(row["body_status"])
            annex_status = str(row["annex_status"])
            body[body_status] += 1
            annex[annex_status] += 1
            if str(row["file_key"]) in target_keys:
                target_rows += 1
                target_body[body_status] += 1
                target_annex[annex_status] += 1
        families[family] = {
            "documents_with_coverage_row": rows,
            "body": dict(sorted(body.items())),
            "annex": dict(sorted(annex.items())),
            "target_scope": {
                "target_documents": len(docs),
                "with_coverage_row": target_rows,
                # 행 자체가 없는 문서는 present=false가 아니라 "미평가"다.
                "no_coverage_row_not_evaluated": len(docs) - target_rows,
                "body": dict(sorted(target_body.items())),
                "annex": dict(sorted(target_annex.items())),
            },
        }
    return {
        "note": (
            "coverage 행이 없는 문서는 '미평가'이며 present=false와 구분한다. "
            "annex_status='no_annex'는 별지가 없어 complete와 동등하게 취급된다."
        ),
        "families": families,
    }


def absence_eligibility(
    conn: sqlite3.Connection, docs: Sequence[Dict[str, object]]
) -> Dict[str, object]:
    """(문서, family) 쌍의 부재 질의 가능/차단과 차단 사유 히스토그램.

    판정은 재구현하지 않고 v4_search.search_clause_absence와 동일한 경로를 탄다:
    _bulk_coverage_states(내부에서 _blocking_pending_candidates 호출) +
    ABSENCE_UNVERIFIED_FAMILIES family 게이트.
    """
    file_rows = [
        {"file_key": doc["file_key"], "content_hash": doc["content_hash"]}
        for doc in docs
    ]
    overall_reasons: Counter = Counter()
    eligible_total = 0
    blocked_total = 0
    families: Dict[str, object] = {}
    for family in FAMILY_ORDER:
        states = _bulk_coverage_states(conn, file_rows, family)
        gated = family in ABSENCE_UNVERIFIED_FAMILIES
        reasons: Counter = Counter()
        eligible = 0
        blocked = 0
        for state in states.values():
            complete = state.get("state") == "complete"
            if complete and not gated:
                eligible += 1
                continue
            blocked += 1
            row_reasons = list(state.get("reasons") or [])
            if complete and gated:
                # search_clause_absence가 붙이는 것과 같은 사유 라벨.
                row_reasons.append("rw_coverage_unverified")
            for reason in row_reasons:
                # 'pending_taxonomy_candidates:3' → 'pending_taxonomy_candidates'
                key = str(reason).split(":", 1)[0]
                reasons[key] += 1
                overall_reasons[key] += 1
        eligible_total += eligible
        blocked_total += blocked
        families[family] = {
            "documents": len(states),
            "absence_eligible": eligible,
            "absence_blocked": blocked,
            "family_gated": gated,
            "blocking_reasons": dict(
                sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
        }
    return {
        "definition": (
            "v4_search._bulk_coverage_states + ABSENCE_UNVERIFIED_FAMILIES 재사용; "
            "대상 문서 × 6 family 쌍 기준. 한 문서가 사유를 여러 개 가질 수 있어 "
            "blocking_reasons 합은 absence_blocked보다 클 수 있다."
        ),
        "family_gated_families": sorted(ABSENCE_UNVERIFIED_FAMILIES),
        "pairs_total": eligible_total + blocked_total,
        "absence_eligible": eligible_total,
        "absence_blocked": blocked_total,
        "blocking_reasons": dict(
            sorted(overall_reasons.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "families": families,
    }


def taxonomy_backlog(conn: sqlite3.Connection) -> Dict[str, object]:
    """후보 backlog — 그리고 그중 실제로 부재를 막는 건 몇 개인가.

    raw pending 수(29,807 등)만으로는 오해를 부른다. V4_PLAN §9.2 T-D 디커플
    규칙(commit 1ec2d6c) 아래에서 blocking vs non-blocking을 나누는 것이 핵심이다.
    """
    status_counts = {
        str(row[0]): int(row[1])
        for row in conn.execute(
            "SELECT COALESCE(status,''),COUNT(*) FROM v4_taxonomy_candidate GROUP BY 1"
        )
    }
    pending_total = status_counts.get("pending", 0)
    distinct_pending_names = int(
        conn.execute(
            "SELECT COUNT(DISTINCT proposed_ko) FROM v4_taxonomy_candidate "
            "WHERE status='pending'"
        ).fetchone()[0]
    )
    pending_in_known_families = int(
        conn.execute(
            "SELECT COUNT(*) FROM v4_taxonomy_candidate WHERE status='pending' "
            "AND family IN (%s)" % ",".join("?" for _ in FAMILY_ORDER),
            list(FAMILY_ORDER),
        ).fetchone()[0]
    )
    blocking_by_family: Dict[str, object] = {}
    blocking_total = 0
    blocked_docs: set[str] = set()
    for family in FAMILY_ORDER:
        counts = _blocking_pending_candidates(conn, family)
        family_total = sum(counts.values())
        blocking_total += family_total
        blocked_docs.update(counts)
        blocking_by_family[family] = {
            "blocking_candidates": family_total,
            "documents_blocked": len(counts),
        }
    return {
        "definition": (
            "blocking = v4_search._blocking_pending_candidates (V4_PLAN §9.2 T-D "
            "디커플 규칙: 특정 하위노드 추천 · document_count>1 · 교차문서 재발 중 "
            "하나라도 해당). 나머지 pending은 문서-특정 일회성이라 부재를 막지 않는다."
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "pending_total": pending_total,
        "pending_distinct_names": distinct_pending_names,
        "pending_blocking": blocking_total,
        "pending_non_blocking": pending_total - blocking_total,
        "pending_outside_known_families": pending_total - pending_in_known_families,
        "documents_blocked_by_pending": len(blocked_docs),
        "by_family": blocking_by_family,
    }


def rw_reextraction(conn: sqlite3.Connection, out: Path) -> Dict[str, object]:
    """RW 재추출 진척 — 저장된 RWRX 문서 vs 재추출 대상.

    대상 규모는 하드코딩하지 않고 DB에서 유도한다:
    저장 완료(RWRX item 보유 문서) + 잔여(coverage.reason에 재추출 표식이 남은 문서).
    """
    stored = int(
        conn.execute(
            "SELECT COUNT(DISTINCT file_key) FROM v4_clause_item "
            "WHERE family='RW' AND item_ref LIKE ?",
            (RW_REEXTRACT_ITEM_PREFIX + "%",),
        ).fetchone()[0]
    )
    remaining = int(
        conn.execute(
            "SELECT COUNT(*) FROM v4_document_coverage "
            "WHERE family='RW' AND reason LIKE ?",
            ("%" + RW_AUDIT_PENDING_MARKER + "%",),
        ).fetchone()[0]
    )
    result: Dict[str, object] = {
        "definition": (
            "stored = v4_clause_item(family='RW', item_ref LIKE 'RWRX-%')의 문서 수; "
            "remaining = v4_document_coverage(family='RW')의 reason에 "
            f"'{RW_AUDIT_PENDING_MARKER}'가 남은 문서 수; target = stored + remaining"
        ),
        "stored_documents": stored,
        "remaining_audit_pending": remaining,
    }
    if stored == 0 and remaining == 0:
        result["target_documents"] = None
        result["target_documents_unavailable_reason"] = (
            "RW 재추출 흔적이 없음 (RWRX item 0건, "
            f"'{RW_AUDIT_PENDING_MARKER}' coverage 0건) — 목표치 산출 불가"
        )
        result["percent"] = None
        result["percent_unavailable_reason"] = "target_documents 미산출"
    else:
        target = stored + remaining
        result["target_documents"] = target
        result["percent"] = _percent(stored, target)

    result_dir = Path(out) / RW_RESULT_DIRNAME
    if result_dir.is_dir():
        result["result_files"] = sum(1 for _ in result_dir.glob("*.json"))
        result["result_files_dir"] = str(result_dir)
    else:
        result["result_files"] = None
        result["result_files_unavailable_reason"] = (
            f"{result_dir} 디렉터리가 없음 — 결과 파일 수 산출 불가"
        )
    return result


def build_burndown(out: Path) -> Dict[str, object]:
    out = Path(out)
    with closing(connect_v4_ro(out)) as conn:
        docs = target_documents(conn)
        return {
            "generated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "out": str(out),
            "index": _meta(conn),
            "type_progress": type_progress(docs),
            "family_coverage": family_coverage(conn, docs),
            "absence_eligibility": absence_eligibility(conn, docs),
            "taxonomy_backlog": taxonomy_backlog(conn),
            "rw_reextraction": rw_reextraction(conn, out),
        }


# ---------------- text rendering ----------------

def _bar(percent: Optional[float], width: int = 20) -> str:
    if percent is None:
        return "-" * width
    filled = int(round(width * max(0.0, min(100.0, percent)) / 100.0))
    return "#" * filled + "." * (width - filled)


def _progress_line(label: str, block: Dict[str, object]) -> str:
    percent = block.get("percent")
    shown = "-" if percent is None else f"{percent:.1f}%"
    return (
        f"{label:<12} {_bar(percent)} {block['evaluated']:>5}/{block['total']:<5} "
        f"{shown:>6}  (remaining {block['remaining']})"
    )


def print_text(result: Dict[str, object]) -> None:
    index = result["index"]
    print(f"generated_at: {result['generated_at']}   out: {result['out']}")
    print(
        "taxonomy v{}  schema v{} rev {}".format(
            index.get("taxonomy_version"),
            index.get("schema_version"),
            index.get("schema_revision"),
        )
    )

    progress = result["type_progress"]
    print("\n== 대상유형 진행률 (evaluated/total) ==")
    print(_progress_line("전체", progress["overall"]))
    print(_progress_line("core 4유형", progress["core_planned"]))
    print(_progress_line("CB/BW/EB", progress["scope_added"]))
    for row in progress["by_type"]:
        print(_progress_line("  " + str(row["ctype"]), row))

    print("\n== family별 coverage (대상 문서 기준) ==")
    print("family\tbody_complete\tbody_partial\tbody_not_eval\tannex_complete"
          "\tannex_no_annex\tannex_partial\tannex_not_eval\t미평가(행없음)")
    for family in FAMILY_ORDER:
        scope = result["family_coverage"]["families"][family]["target_scope"]
        body = scope["body"]
        annex = scope["annex"]
        print(
            "\t".join(
                str(value)
                for value in (
                    family,
                    body.get("complete", 0),
                    body.get("partial", 0),
                    body.get("not_evaluated", 0),
                    annex.get("complete", 0),
                    annex.get("no_annex", 0),
                    annex.get("partial", 0),
                    annex.get("not_evaluated", 0),
                    scope["no_coverage_row_not_evaluated"],
                )
            )
        )

    absence = result["absence_eligibility"]
    print(
        "\n== 부재 질의 가능 vs 차단 ==  가능 {}/{} · 차단 {}".format(
            absence["absence_eligible"], absence["pairs_total"], absence["absence_blocked"]
        )
    )
    print("family\t가능\t차단\tfamily_gated")
    for family in FAMILY_ORDER:
        row = absence["families"][family]
        print(
            f"{family}\t{row['absence_eligible']}\t{row['absence_blocked']}"
            f"\t{'Y' if row['family_gated'] else ''}"
        )
    print("차단 사유 히스토그램:")
    for reason, count in absence["blocking_reasons"].items():
        print(f"  {reason}\t{count}")

    backlog = result["taxonomy_backlog"]
    print("\n== taxonomy 후보 backlog ==")
    for status, count in backlog["status_counts"].items():
        print(f"  {status or '(none)'}\t{count}")
    print(
        "  pending {} 중 blocking {} · non-blocking {} (이름 {}종, 차단 문서 {}건)".format(
            backlog["pending_total"],
            backlog["pending_blocking"],
            backlog["pending_non_blocking"],
            backlog["pending_distinct_names"],
            backlog["documents_blocked_by_pending"],
        )
    )

    rw = result["rw_reextraction"]
    print("\n== RW 재추출 진척 ==")
    if rw.get("target_documents") is None:
        print("  미산출: " + str(rw.get("target_documents_unavailable_reason")))
    else:
        print(
            "  stored {}/{} ({}%) · 잔여 {}".format(
                rw["stored_documents"],
                rw["target_documents"],
                rw["percent"],
                rw["remaining_audit_pending"],
            )
        )
    if rw.get("result_files") is None:
        print("  result_files 미산출: " + str(rw.get("result_files_unavailable_reason")))
    else:
        print(f"  result_files {rw['result_files']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V4 번다운 지표 (read-only). PLAN_REVIEW 권고 5."
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        result = build_burndown(args.out)
    except V4SearchError as exc:
        print(f"ERROR: {exc} ({exc.code})", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
