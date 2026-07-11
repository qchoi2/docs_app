"""Golden-query evaluation harness for the contract search backend.

Loads ``golden_queries.yaml``, runs the requested tier queries, and applies
partial scoring:

- precision   : fraction of returned results satisfying ``expected_filter``
- recall      : fraction of ``expected_files`` present in the results
                (only when ``expected_files`` is non-empty)
- count       : whether the corpus can supply ``expected_count`` results
                (``actual_count >= expected_count``; the agent obeys the
                requested count downstream)

Queries whose ``expected_files`` is empty are scored in "partial(filter-only)"
mode. Queries with no applicable check (empty filter, no files, no count) are
reported as ``unscored`` rather than a silent pass. Each run is appended to
``<out>/eval_history.jsonl`` for regression tracking.

The search itself is driven by ``expected_filter`` (ctype / lang / is_draft).
Natural-language keyword extraction is intentionally out of scope: without
gold ``expected_files`` the eval can only score the metadata filter, which is
exactly the "부분채점(필터만)" mode described in the implementation brief.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from lib.console import configure_utf8_stdio
from search_contracts import search_contracts


GOLDEN_PATHS = (Path("data/golden_queries.yaml"), Path(".docs/golden_queries.yaml"))
DEFAULT_TIERS = ("T1", "T2")
T3_NUMERIC_FILTER_KEYS = {
    "cap_lte",
    "cap_gte",
    "cap_eq",
    "cap_percent_lte",
    "cap_percent_gte",
    "survival_months_lte",
    "survival_months_gte",
}
T3_SUPPORTED_FILTER_KEYS = {
    "ctype",
    "lang",
    "is_draft",
    "clause",
    "present",
    "clause_present",
    "absent",
} | T3_NUMERIC_FILTER_KEYS


def resolve_golden(path: Optional[Path], base: Optional[Path] = None) -> Path:
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"golden queries not found: {path}")
        return path
    bases = [base] if base is not None else [Path.cwd(), Path(__file__).resolve().parent]
    for base_dir in bases:
        for candidate in GOLDEN_PATHS:
            full = base_dir / candidate
            if full.exists():
                return full
    raise FileNotFoundError("golden_queries.yaml not found in data/ or .docs/")


def load_queries(path: Path, tiers: Sequence[str]) -> List[Dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tier_set = set(tiers)
    return [item for item in (data.get("queries") or []) if str(item.get("tier", "")) in tier_set]


def split_filter(expected_filter: Optional[Dict[str, object]]) -> Tuple[Dict[str, object], List[str]]:
    """Split expected_filter into keys the eval can score vs. keys it cannot.

    Scoreable keys are ctype / lang / is_draft. Everything else (clause, ext,
    party_role, ...) is T3-level metadata not available in this phase and is
    surfaced as ``unscored_filter_keys`` instead of being silently ignored.
    """
    scoreable: Dict[str, object] = {}
    unscored: List[str] = []
    for key, value in (expected_filter or {}).items():
        if key == "ctype" and isinstance(value, str) and "/" not in value:
            scoreable["ctype"] = value
        elif key == "lang" and isinstance(value, str):
            scoreable["lang"] = value
        elif key == "is_draft":
            scoreable["is_draft"] = bool(value)
        else:
            unscored.append(key)
    return scoreable, unscored


def result_matches_filter(item: Dict[str, object], scoreable: Dict[str, object]) -> bool:
    if "ctype" in scoreable and item.get("ctype") != scoreable["ctype"]:
        return False
    if "lang" in scoreable and item.get("lang") != scoreable["lang"]:
        return False
    if "is_draft" in scoreable:
        is_draft = item.get("is_draft") == 1
        if scoreable["is_draft"] is False and is_draft:
            return False
        if scoreable["is_draft"] is True and not is_draft:
            return False
    return True


def expected_clause_present(expected_filter: Dict[str, object]) -> bool:
    if "present" in expected_filter:
        return bool(expected_filter["present"])
    if "clause_present" in expected_filter:
        return bool(expected_filter["clause_present"])
    if "absent" in expected_filter:
        return not bool(expected_filter["absent"])
    return True


def t3_unsupported_filter_keys(expected_filter: Dict[str, object]) -> List[str]:
    return [key for key in expected_filter if key not in T3_SUPPORTED_FILTER_KEYS]


def result_matches_t3_clause(item: Dict[str, object], scoreable: Dict[str, object], expected_present: bool) -> bool:
    if not result_matches_filter(item, scoreable):
        return False
    clause = item.get("clause")
    if not isinstance(clause, dict):
        return False
    if clause.get("present") is not expected_present:
        return False
    if not expected_present and clause.get("confidence") == "low":
        return False
    return True


def skipped_query(item: Dict[str, object], reason: str, unscored: Optional[List[str]] = None) -> Dict[str, object]:
    return {
        "id": item.get("id"),
        "tier": item.get("tier"),
        "intent": item.get("intent"),
        "kw": [str(value) for value in (item.get("kw") or []) if str(value).strip()],
        "mode": "skipped",
        "scored_filter": {},
        "unscored_filter_keys": unscored or [],
        "precision": None,
        "recall": None,
        "expected_count": item.get("expected_count"),
        "actual_count": None,
        "count_ok": None,
        "returned": 0,
        "status": "skipped",
        "skip_reason": reason,
    }


def evaluate_t3_query(out: Path, item: Dict[str, object], limit: int) -> Dict[str, object]:
    expected_filter = item.get("expected_filter") or {}
    if not isinstance(expected_filter, dict):
        return skipped_query(item, "expected_filter_not_object")

    clause = expected_filter.get("clause")
    if not clause:
        return skipped_query(item, "t3_clause_filter_missing", sorted(expected_filter.keys()))

    scoreable, base_unscored = split_filter(expected_filter)
    unsupported = t3_unsupported_filter_keys(expected_filter)
    numeric_filters = [key for key in expected_filter if key in T3_NUMERIC_FILTER_KEYS]
    unscored = sorted(
        set([key for key in base_unscored if key not in T3_SUPPORTED_FILTER_KEYS] + unsupported + numeric_filters)
    )
    expected_present = expected_clause_present(expected_filter)
    expected_files = [str(value) for value in (item.get("expected_files") or [])]
    expected_count = item.get("expected_count")

    keywords = [str(value) for value in (item.get("kw") or []) if str(value).strip()]
    result, _ = search_contracts(
        out,
        ctype=scoreable.get("ctype"),
        lang=scoreable.get("lang"),
        keywords=keywords,
        exclude_drafts=scoreable.get("is_draft") is False,
        limit=limit,
        clause=str(clause),
        clause_present=expected_present,
        clause_absent=not expected_present,
    )
    results = result["results"]
    returned_keys = [row["file_key"] for row in results]

    checks: Dict[str, bool] = {}
    precision: Optional[float] = None
    if results:
        matched = sum(1 for row in results if result_matches_t3_clause(row, scoreable, expected_present))
        precision = matched / len(results)
        checks["precision"] = precision >= 1.0

    recall: Optional[float] = None
    if expected_files:
        present = sum(1 for key in expected_files if key in returned_keys)
        recall = present / len(expected_files)
        checks["recall"] = recall >= 1.0

    actual_count = result["total"]
    count_ok: Optional[bool] = None
    if expected_count is not None:
        count_ok = actual_count >= int(expected_count)
        checks["count"] = count_ok

    if not checks and unscored:
        status = "skipped"
    elif not checks:
        status = "unscored"
    elif all(checks.values()):
        status = "pass"
    else:
        status = "fail"

    mode = "full" if expected_files else "partial(t3-clause)"
    return {
        "id": item.get("id"),
        "tier": item.get("tier"),
        "intent": item.get("intent"),
        "kw": keywords,
        "mode": mode,
        "scored_filter": dict(scoreable, clause=str(clause), present=expected_present),
        "unscored_filter_keys": unscored,
        "precision": precision,
        "recall": recall,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "count_ok": count_ok,
        "returned": len(results),
        "status": status,
        "clause_needs_review": (result.get("query", {}).get("clause") or {}).get("needs_review", []),
    }


def evaluate_query(out: Path, item: Dict[str, object], limit: int) -> Dict[str, object]:
    if str(item.get("tier")) == "T3":
        return evaluate_t3_query(out, item, limit)

    scoreable, unscored = split_filter(item.get("expected_filter"))
    expected_files = [str(value) for value in (item.get("expected_files") or [])]
    expected_count = item.get("expected_count")

    keywords = [str(value) for value in (item.get("kw") or []) if str(value).strip()]
    result, _ = search_contracts(
        out,
        ctype=scoreable.get("ctype"),
        lang=scoreable.get("lang"),
        keywords=keywords,
        exclude_drafts=scoreable.get("is_draft") is False,
        limit=limit,
    )
    results = result["results"]
    returned_keys = [row["file_key"] for row in results]

    checks: Dict[str, bool] = {}

    precision: Optional[float] = None
    if scoreable and results:
        matched = sum(1 for row in results if result_matches_filter(row, scoreable))
        precision = matched / len(results)
        checks["precision"] = precision >= 1.0

    recall: Optional[float] = None
    if expected_files:
        present = sum(1 for key in expected_files if key in returned_keys)
        recall = present / len(expected_files)
        checks["recall"] = recall >= 1.0

    actual_count = result["total"]
    count_ok: Optional[bool] = None
    if expected_count is not None:
        count_ok = actual_count >= int(expected_count)
        checks["count"] = count_ok

    if not checks:
        status = "unscored"
    elif all(checks.values()):
        status = "pass"
    else:
        status = "fail"

    return {
        "id": item.get("id"),
        "tier": item.get("tier"),
        "intent": item.get("intent"),
        "kw": keywords,
        "mode": "full" if expected_files else "partial(filter-only)",
        "scored_filter": scoreable,
        "unscored_filter_keys": unscored,
        "precision": precision,
        "recall": recall,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "count_ok": count_ok,
        "returned": len(results),
        "status": status,
    }


def summarize(per_query: Sequence[Dict[str, object]]) -> Dict[str, int]:
    counts = {"total": len(per_query), "pass": 0, "fail": 0, "unscored": 0, "skipped": 0, "partial": 0}
    for query in per_query:
        status = str(query["status"])
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
        if str(query["mode"]).startswith("partial"):
            counts["partial"] += 1
    return counts


def append_history(out: Path, record: Dict[str, object]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "eval_history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_eval(
    out: Path,
    golden_path: Optional[Path] = None,
    tiers: Sequence[str] = DEFAULT_TIERS,
    limit: int = 50,
    base: Optional[Path] = None,
) -> Dict[str, object]:
    path = resolve_golden(golden_path, base)
    queries = load_queries(path, tiers)
    per_query = [evaluate_query(out, item, limit) for item in queries]
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "golden": str(path),
        "tiers": list(tiers),
        "summary": summarize(per_query),
        "queries": per_query,
    }
    append_history(out, record)
    return record


def print_report(record: Dict[str, object]) -> None:
    print(f"golden: {record['golden']}")
    print(f"tiers: {', '.join(record['tiers'])}")
    header = ["id", "tier", "mode", "precision", "recall", "count(exp/act)", "status"]
    print("\t".join(header))
    for query in record["queries"]:
        precision = "—" if query["precision"] is None else f"{query['precision']:.2f}"
        recall = "—" if query["recall"] is None else f"{query['recall']:.2f}"
        if query["expected_count"] is None:
            count = "—"
        elif query["actual_count"] is None:
            count = f"{query['expected_count']}/—"
        else:
            count = f"{query['expected_count']}/{query['actual_count']}"
        print("\t".join([
            str(query["id"]),
            str(query["tier"]),
            str(query["mode"]),
            precision,
            recall,
            count,
            str(query["status"]),
        ]))
    summary = record["summary"]
    print(
        f"\nsummary: total={summary['total']} pass={summary['pass']} "
        f"fail={summary['fail']} unscored={summary['unscored']} "
        f"skipped={summary['skipped']} partial={summary['partial']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run golden-query evaluation for contract search.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--golden", type=Path, help="path to golden_queries.yaml (default: data/ then .docs/)")
    parser.add_argument("--tiers", default="T1,T2", help="comma-separated tiers to run (default: T1,T2)")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    tiers = [tier.strip() for tier in args.tiers.split(",") if tier.strip()]
    try:
        record = run_eval(args.out, golden_path=args.golden, tiers=tiers, limit=args.limit)
    except Exception as exc:  # noqa: BLE001 - surface as CLI error, no silent failure
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_report(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
