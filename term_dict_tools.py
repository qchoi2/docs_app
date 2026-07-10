"""term_dict.yaml maintenance tools — validate, suggest, zero-hit check.

Follows the maintenance pipeline documented in the term_dict.yaml header:
suggestions are written to <out>/pending_terms.yaml for OWNER approval and
are never merged into data/term_dict.yaml automatically. No paid API calls.
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
from typing import Dict, List, Optional

import yaml

from lib.console import configure_utf8_stdio
from lib.normalize import normalize
from search_contracts import (
    TERM_DICT_PATHS,
    escape_fts_phrase,
    find_term_dict,
    is_short_term,
    like_pattern,
    load_term_dict,
)

VALID_STRENGTHS = {"strict", "normal", "broad"}


def load_raw_dict(dict_path: Optional[Path]):
    path = dict_path or find_term_dict()
    if path is None:
        raise FileNotFoundError("term_dict.yaml not found (data/ or .docs/)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}, path


def validate(dict_path: Optional[Path]) -> int:
    try:
        data, path = load_raw_dict(dict_path)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    terms = data.get("terms")
    if not isinstance(terms, list) or not terms:
        print("ERROR: 'terms' must be a non-empty list", file=sys.stderr)
        return 2

    errors: List[str] = []
    warnings: List[str] = []
    seen_canonical: Counter = Counter()
    variant_owner: Dict[str, List[str]] = {}

    for index, item in enumerate(terms):
        label = f"terms[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: entry must be a mapping")
            continue
        canonical = str(item.get("canonical") or "").strip()
        if not canonical:
            errors.append(f"{label}: canonical is required")
            continue
        seen_canonical[canonical] += 1
        strength = item.get("expansion_strength")
        if strength is not None and str(strength) not in VALID_STRENGTHS:
            errors.append(f"{canonical}: invalid expansion_strength {strength!r}")
        canonical_key = normalize(canonical).casefold()
        listed_variants = []
        for field in ("ko", "en"):
            values = item.get(field)
            if values is None:
                continue
            if not isinstance(values, list):
                errors.append(f"{canonical}: {field} must be a list")
                continue
            listed_variants.extend(str(value) for value in values)
        own_normalized = {canonical_key}
        seen_listed = set()
        for variant in listed_variants:
            key = normalize(variant).casefold()
            if not key:
                warnings.append(f"{canonical}: empty variant")
                continue
            # canonical이 ko/en에 반복되는 것은 사전의 의도된 스타일 — 경고 제외
            if key in seen_listed:
                warnings.append(f"{canonical}: duplicate variant '{variant}' within entry")
            seen_listed.add(key)
            own_normalized.add(key)
            variant_owner.setdefault(key, [])
            if canonical not in variant_owner[key]:
                variant_owner[key].append(canonical)
        for avoided in item.get("avoid_expanding_to") or []:
            if normalize(str(avoided)).casefold() in own_normalized:
                warnings.append(f"{canonical}: avoid_expanding_to lists its own variant '{avoided}'")

    for canonical, count in seen_canonical.items():
        if count > 1:
            errors.append(f"duplicate canonical: {canonical} x{count}")
    for key, owners in variant_owner.items():
        if len(owners) > 1:
            warnings.append(f"variant '{key}' shared by: {', '.join(owners)}")

    print(f"dict: {path}")
    print(f"terms: {len(terms)}, errors: {len(errors)}, warnings: {len(warnings)}")
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARN: {message}")
    return 2 if errors else 0


def suggest(out: Path, dict_path: Optional[Path], min_seen: int) -> int:
    log_path = out / "query_log.jsonl"
    if not log_path.exists():
        print(f"ERROR: query log not found: {log_path}", file=sys.stderr)
        return 2
    entries = load_term_dict(dict_path.parent if dict_path else None) or []
    known = set()
    for entry in entries:
        for variant, _strength in entry.variants:
            known.add(normalize(variant).casefold())

    unknown: Counter = Counter()
    result_counts: Dict[str, List[int]] = {}
    zero_result: Counter = Counter()
    records = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        records += 1
        query = record.get("query") or {}
        keywords = query.get("kw") or []
        count = record.get("result_count")
        for keyword in keywords:
            key = normalize(str(keyword))
            fold = key.casefold()
            if not fold:
                continue
            if fold not in known:
                unknown[key] += 1
                if isinstance(count, int):
                    result_counts.setdefault(key, []).append(count)
            elif count == 0:
                zero_result[key] += 1

    candidates = []
    for term, seen in unknown.most_common():
        if seen < min_seen:
            continue
        related = [
            entry.canonical
            for entry in entries
            if entry.canonical and any(
                normalize(variant).casefold() in term.casefold()
                or term.casefold() in normalize(variant).casefold()
                for variant, _strength in entry.variants
            )
        ]
        candidates.append(
            {
                "term": term,
                "seen": seen,
                "result_counts": result_counts.get(term, [])[:10],
                "reason": "term_dict 미수록 — 동의어 확장이 적용되지 않음",
                "related_canonical": related[:3],
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"query_log.jsonl ({records} records)",
        "note": "사람이 승인한 항목만 data/term_dict.yaml에 병합하고 dict_version을 올릴 것.",
        "candidates": candidates,
        "zero_result_known_terms": [
            {"term": term, "seen": seen} for term, seen in zero_result.most_common(20)
        ],
    }
    pending_path = out / "pending_terms.yaml"
    pending_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"pending: {pending_path}")
    print(f"candidates: {len(candidates)}, zero-result known terms: {len(payload['zero_result_known_terms'])}")
    return 0


def zero_hits(out: Path, dict_path: Optional[Path]) -> int:
    db_path = out / "catalog.sqlite"
    if not db_path.exists():
        print(f"ERROR: catalog.sqlite not found: {db_path}", file=sys.stderr)
        return 2
    entries = load_term_dict(dict_path.parent if dict_path else None) or []
    zero: List[str] = []
    with closing(sqlite3.connect(db_path)) as conn:
        for entry in entries:
            for variant, _strength in entry.variants:
                term = normalize(variant)
                if not term:
                    continue
                if is_short_term(term):
                    row = conn.execute(
                        "SELECT COUNT(*) FROM fts WHERE content LIKE ? ESCAPE '\\'",
                        (like_pattern(term),),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM fts WHERE fts MATCH ?",
                        (escape_fts_phrase(term),),
                    ).fetchone()
                if row[0] == 0:
                    zero.append(f"{entry.canonical}: '{variant}'")
    print(f"zero-hit variants: {len(zero)} (현재 코퍼스 기준 — 오타/불필요 후보이나 코퍼스 확장 시 재확인)")
    for line in zero:
        print(f"  {line}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and extend term_dict.yaml safely.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true")
    group.add_argument("--suggest", action="store_true")
    group.add_argument("--zero-hits", action="store_true")
    parser.add_argument("--out", type=Path, help="cs_index folder (--suggest/--zero-hits)")
    parser.add_argument("--dict", type=Path, help="explicit term_dict.yaml path")
    parser.add_argument("--min-seen", type=int, default=1, help="--suggest: minimum query frequency")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        if args.validate:
            return validate(args.dict)
        if not args.out:
            print("ERROR: --out is required for --suggest/--zero-hits", file=sys.stderr)
            return 2
        if args.suggest:
            return suggest(args.out, args.dict, args.min_seen)
        return zero_hits(args.out, args.dict)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
