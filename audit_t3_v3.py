"""Audit T3 v3 pilot outputs without writing to catalog.sqlite."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from enrich_contracts import Candidate, EnrichError, validate_result
from lib.console import configure_utf8_stdio
from lib.normalize import normalize
from t3_schema import V3_SCHEMA_VERSION


def _candidate(item: Dict[str, object], input_payload: Dict[str, object]) -> Candidate:
    return Candidate(
        file_key=str(item["file_key"]),
        path=str(item.get("path") or ""),
        ctype=str(item.get("ctype") or "미분류"),
        lang=str(item.get("lang") or "미상"),
        content_hash=str(input_payload.get("content_hash") or ""),
        txt_path="",
        char_count=int(item.get("char_count") or 0),
    )


def _paragraph_map(input_payload: Dict[str, object]) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for item in input_payload.get("paragraphs", []):
        if isinstance(item, dict) and isinstance(item.get("para"), int):
            result[item["para"]] = str(item.get("text") or "")
    return result


def _compact(value: object) -> str:
    return re.sub(r"\s+", "", normalize(str(value or ""))).casefold()


def _digit_evidence(evidence: str) -> str:
    """Compact evidence for numeric matching.

    Removes thousands separators (500,000,000 -> 500000000) and draft placeholder
    brackets ([1]년 -> 1년, [1억]원 -> 1억원) so unit conversions still match.
    """
    compact = re.sub(r"(?<=\d)[,，](?=\d)", "", _compact(evidence))
    return re.sub(r"[\[\]［］()（）]", "", compact)


def _number_representations(field: str, value: object) -> List[str]:
    """String forms of a numeric value that may legitimately appear in the source."""
    reps: List[str] = []
    if isinstance(value, bool):
        return reps
    if isinstance(value, float):
        reps.append(str(value).rstrip("0").rstrip("."))
    else:
        reps.append(str(value))
    if isinstance(value, int):
        if field.endswith("_months") and value % 12 == 0:
            reps.append("%d년" % (value // 12))
        if value and value % 10 ** 8 == 0:  # 억 단위 표기
            reps.append("%d억" % (value // 10 ** 8))
        elif value and value % 10 ** 7 == 0:  # 0.1억 단위 표기 (예: 0.5억)
            reps.append("%g억" % (value / 10 ** 8))
        if value and value % 10 ** 4 == 0:  # 만 단위 표기
            reps.append("%d만" % (value // 10 ** 4))
    return reps


def _normalized_number_is_supported(field: str, value: object, evidence: str) -> bool:
    ev = _digit_evidence(evidence)
    for rep in _number_representations(field, value):
        if rep and _compact(rep) in ev:
            return True
    return False


def _evidence_checks(data: Dict[str, object], paragraphs: Dict[int, str]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    clause_map = data.get("clause_map_json")
    if not isinstance(clause_map, dict):
        return issues
    for tag, clause in clause_map.items():
        if not isinstance(clause, dict) or clause.get("present") is not True:
            continue
        start = clause.get("loc_start")
        end = clause.get("loc_end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        missing = [str(number) for number in range(start, end + 1) if number not in paragraphs]
        if missing:
            issues.append({"tag": tag, "code": "location_missing", "detail": ",".join(missing[:10])})
            continue
        source = " ".join(paragraphs[number] for number in range(start, end + 1))
        verbatim = clause.get("verbatim")
        if verbatim and _compact(verbatim) not in _compact(source):
            issues.append({"tag": tag, "code": "verbatim_not_in_range", "detail": str(verbatim)[:120]})
        normalized_values = clause.get("normalized")
        if isinstance(normalized_values, dict):
            evidence = "%s %s" % (verbatim or "", source)
            for field, value in normalized_values.items():
                # 숫자형 값만 근거 검사(문자열: forum/law/currency 등은 제외)
                if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                if not _normalized_number_is_supported(field, value, evidence):
                    issues.append({
                        "tag": tag,
                        "code": "normalized_number_not_in_evidence",
                        "detail": "%s=%s" % (field, value),
                    })
    return issues


def audit_pilot(
    manifest_path: Path,
    *,
    input_dir: Optional[Path] = None,
    result_dir: Optional[Path] = None,
    report_path: Optional[Path] = None,
) -> Dict[str, object]:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ValueError("pilot manifest must contain an items array")
    out_dir = manifest_path.parent
    input_dir = input_dir or out_dir / "enrich_inputs_v3"
    result_dir = result_dir or out_dir / "enrich_results_v3"
    report_path = report_path or out_dir / "t3_v3_audit_report.json"

    rows: List[Dict[str, object]] = []
    counters = Counter()
    for item in manifest["items"]:
        file_key = str(item["file_key"])
        input_path = input_dir / (file_key + ".json")
        result_path = result_dir / (file_key + ".json")
        if not input_path.exists():
            rows.append({"file_key": file_key, "status": "error", "issues": [{"code": "input_missing"}]})
            counters["error"] += 1
            continue
        if not result_path.exists():
            rows.append({"file_key": file_key, "status": "pending", "issues": []})
            counters["pending"] += 1
            continue
        try:
            input_payload = json.loads(input_path.read_text(encoding="utf-8"))
            data = json.loads(result_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise EnrichError("result JSON must be an object")
            validate_result(data, _candidate(item, input_payload), V3_SCHEMA_VERSION)
            issues = _evidence_checks(data, _paragraph_map(input_payload))
            status = "review" if issues or data.get("confidence") == "low" else "pass"
            rows.append({
                "file_key": file_key,
                "status": status,
                "confidence": data.get("confidence"),
                "issues": issues,
            })
            counters[status] += 1
        except (OSError, ValueError, EnrichError) as exc:
            rows.append({"file_key": file_key, "status": "error", "issues": [{"code": "invalid_result", "detail": str(exc)}]})
            counters["error"] += 1

    payload = {
        "meta_schema_version": V3_SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "input_dir": str(input_dir),
        "result_dir": str(result_dir),
        "summary": {
            "total": len(rows),
            "pending": counters["pending"],
            "pass": counters["pass"],
            "review": counters["review"],
            "error": counters["error"],
            "ready_for_human_review": counters["pass"] + counters["review"],
        },
        "items": rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit T3 v3 pilot result JSON files.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        result = audit_pilot(
            args.manifest,
            input_dir=args.input_dir,
            result_dir=args.result_dir,
            report_path=args.report,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
