"""Select a deterministic, stratified T3 v3 quality pilot.

The planner is read-only with respect to catalog.sqlite.  It can optionally
write versioned agent-input JSON files, but never writes doc_meta.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict, deque
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from enrich_contracts import Candidate, build_agent_input, write_agent_input
from lib.console import configure_utf8_stdio
from search_contracts import connect_search_db
from t3_schema import V3_SCHEMA_VERSION, required_clause_tags


DEFAULT_LIMIT = 60
CONFIDENCE_ORDER = {"low": 0, "med": 1, "high": 2, None: 3, "": 3}
TYPE_ORDER = (
    "SPA",
    "SHA",
    "SSA",
    "MOU",
    "ATA/BTA",
    "JVA",
    "공동투자",
    "CB인수",
    "BW인수",
    "EB인수",
    "주식교환",
    "분할합병",
)


@dataclass
class PilotCandidate:
    candidate: Candidate
    prior_confidence: Optional[str]
    is_draft: Optional[int]
    version_hint: Optional[str]


def _type_order(ctype: str) -> Tuple[int, str]:
    try:
        return TYPE_ORDER.index(ctype), ctype
    except ValueError:
        return len(TYPE_ORDER), ctype


def load_candidates(out: Path) -> List[PilotCandidate]:
    db_path = Path(out).resolve() / "catalog.sqlite"
    if not db_path.exists():
        raise FileNotFoundError("catalog.sqlite not found: %s" % db_path)
    with closing(connect_search_db(db_path, read_only=True)) as conn:
        rows = conn.execute(
            """
            SELECT f.file_key, f.path, f.ctype, f.lang, f.content_hash,
                   f.txt_path, COALESCE(f.char_count, 0),
                   dm.confidence, f.is_draft, f.version_hint
            FROM files f
            LEFT JOIN doc_meta dm ON dm.file_key=f.file_key
            WHERE f.status='ok'
              AND COALESCE(f.dup_group, f.file_key)=f.file_key
            ORDER BY f.ctype, f.path, f.file_key
            """
        ).fetchall()
    return [
        PilotCandidate(
            candidate=Candidate(
                file_key=str(row[0]),
                path=str(row[1]),
                ctype=str(row[2]),
                lang=str(row[3]),
                content_hash=str(row[4] or ""),
                txt_path=str(row[5] or ""),
                char_count=int(row[6] or 0),
            ),
            prior_confidence=str(row[7]) if row[7] is not None else None,
            is_draft=int(row[8]) if row[8] is not None else None,
            version_hint=str(row[9]) if row[9] is not None else None,
        )
        for row in rows
    ]


def _bucket_key(item: PilotCandidate) -> Tuple[int, str, int]:
    return (
        CONFIDENCE_ORDER.get(item.prior_confidence, 3),
        item.candidate.lang,
        0 if item.is_draft == 1 else 1 if item.is_draft == 0 else 2,
    )


def _diverse_group(items: Sequence[PilotCandidate]) -> Deque[PilotCandidate]:
    buckets: Dict[Tuple[int, str, int], Deque[PilotCandidate]] = defaultdict(deque)
    for item in sorted(items, key=lambda value: (value.candidate.path, value.candidate.file_key)):
        buckets[_bucket_key(item)].append(item)
    ordered_keys = sorted(buckets)
    result: Deque[PilotCandidate] = deque()
    while ordered_keys:
        next_keys = []
        for key in ordered_keys:
            bucket = buckets[key]
            if bucket:
                result.append(bucket.popleft())
            if bucket:
                next_keys.append(key)
        ordered_keys = next_keys
    return result


def select_pilot(candidates: Sequence[PilotCandidate], limit: int = DEFAULT_LIMIT) -> List[PilotCandidate]:
    if limit < 1:
        raise ValueError("limit must be positive")
    groups: Dict[str, List[PilotCandidate]] = defaultdict(list)
    for item in candidates:
        groups[item.candidate.ctype].append(item)
    queues = {ctype: _diverse_group(items) for ctype, items in groups.items()}
    ctypes = sorted(queues, key=_type_order)
    selected: List[PilotCandidate] = []

    # First give every represented contract type two slots where possible.
    for _round in range(2):
        for ctype in ctypes:
            if len(selected) >= limit:
                return selected
            if queues[ctype]:
                selected.append(queues[ctype].popleft())

    # Then use a weighted round-robin so high-value types get more coverage.
    weights = {
        "SPA": 3,
        "SHA": 3,
        "SSA": 2,
        "MOU": 2,
        "ATA/BTA": 2,
    }
    while len(selected) < limit and any(queues[ctype] for ctype in ctypes):
        progressed = False
        for ctype in ctypes:
            for _slot in range(weights.get(ctype, 1)):
                if len(selected) >= limit:
                    break
                if queues[ctype]:
                    selected.append(queues[ctype].popleft())
                    progressed = True
        if not progressed:
            break
    return selected


def build_manifest(out: Path, selected: Sequence[PilotCandidate]) -> Dict[str, object]:
    by_type = Counter(item.candidate.ctype for item in selected)
    by_lang = Counter(item.candidate.lang for item in selected)
    by_conf = Counter(item.prior_confidence or "missing" for item in selected)
    by_draft = Counter(
        "draft" if item.is_draft == 1 else "not_draft" if item.is_draft == 0 else "unknown"
        for item in selected
    )
    return {
        "meta_schema_version": V3_SCHEMA_VERSION,
        "source": str(Path(out).resolve() / "catalog.sqlite"),
        "count": len(selected),
        "distribution": {
            "ctype": dict(sorted(by_type.items(), key=lambda pair: _type_order(pair[0]))),
            "lang": dict(sorted(by_lang.items())),
            "prior_confidence": dict(sorted(by_conf.items())),
            "draft_state": dict(sorted(by_draft.items())),
        },
        "review_policy": {
            "low": "전수 검수",
            "med": "유형별 표본 검수",
            "high": "위치·수치 표본 검수",
            "approval": "사람 승인 전 전량 v3 저장 금지",
        },
        "items": [
            {
                "file_key": item.candidate.file_key,
                "path": item.candidate.path,
                "ctype": item.candidate.ctype,
                "lang": item.candidate.lang,
                "is_draft": item.is_draft,
                "version_hint": item.version_hint,
                "prior_confidence": item.prior_confidence,
                "char_count": item.candidate.char_count,
                "required_clause_tags": required_clause_tags(item.candidate.ctype),
                "selection_reason": "T3 v3 층화 표본: 유형·언어·Draft·기존 신뢰도 균형",
            }
            for item in selected
        ],
    }


def write_manifest(path: Path, manifest: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_review_markdown(path: Path, manifest: Dict[str, object]) -> None:
    lines = [
        "# T3 v3 파일럿 검수표",
        "",
        "- 대상: %s건" % manifest["count"],
        "- 원칙: low 전수, med 유형별 표본, high 위치·수치 표본 검수",
        "- 승인 전 전량 v3 저장 금지",
        "",
        "| file_key | 유형 | 언어 | Draft | 기존 신뢰도 | 당사자 | 대금 | 조항 위치 | 수치 | 검수 결과 |",
        "|---|---|---|---:|---|---|---|---|---|---|",
    ]
    for item in manifest["items"]:
        lines.append(
            "| `{file_key}` | {ctype} | {lang} | {draft} | {confidence} | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |".format(
                file_key=item["file_key"],
                ctype=item["ctype"],
                lang=item["lang"],
                draft="예" if item["is_draft"] == 1 else "아니오" if item["is_draft"] == 0 else "미상",
                confidence=item["prior_confidence"] or "없음",
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plan_pilot(
    out: Path,
    *,
    limit: int = DEFAULT_LIMIT,
    manifest_path: Optional[Path] = None,
    review_path: Optional[Path] = None,
    write_inputs: bool = False,
    input_dir: Optional[Path] = None,
) -> Dict[str, object]:
    out = Path(out).resolve()
    selected = select_pilot(load_candidates(out), limit)
    manifest = build_manifest(out, selected)
    manifest_path = manifest_path or out / "t3_v3_pilot_manifest.json"
    review_path = review_path or out / "t3_v3_pilot_review.md"
    write_manifest(manifest_path, manifest)
    write_review_markdown(review_path, manifest)
    written_inputs: List[str] = []
    if write_inputs:
        destination = input_dir or out / "enrich_inputs_v3"
        for item in selected:
            payload = build_agent_input(out, item.candidate, V3_SCHEMA_VERSION)
            written_inputs.append(str(write_agent_input(destination, payload)))
    manifest["manifest_path"] = str(manifest_path)
    manifest["review_path"] = str(review_path)
    manifest["written_inputs"] = written_inputs
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a stratified T3 v3 quality pilot.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--write-inputs", action="store_true")
    parser.add_argument("--input-dir", type=Path)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        result = plan_pilot(
            args.out,
            limit=args.limit,
            manifest_path=args.manifest,
            review_path=args.review,
            write_inputs=args.write_inputs,
            input_dir=args.input_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        print("ERROR: %s" % exc)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
