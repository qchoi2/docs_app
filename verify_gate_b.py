"""Owner-friendly verification helper for the pooled independent Gate B.

Two steps, no exhaustive labelling:

  1) cards  — build a Markdown worksheet listing each pooled document with
              evidence (V4's claim + the contract's own text near the clause),
              and a blank ``- verdict:`` line to fill in.
  2) ingest — read the filled worksheet and write owner verdicts to a JSON
              file that ``eval_v4_gate.py --pooled --verdicts`` merges in.

The seed YAML (query definitions + comments) is never rewritten; verdicts
live in a separate file so the human-authored seed stays intact.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from lib.console import configure_utf8_stdio
from eval_v4_gate import aliases, evaluate_pooled
from v4_search import (
    connect_v4_ro,
    resolve_taxonomy,
    search_clause_absence,
    taxonomy_descendants,
)

VERDICT_MAP = {
    "correct": "correct", "o": "correct", "맞음": "correct", "yes": "correct", "y": "correct",
    "incorrect": "incorrect", "x": "incorrect", "아님": "incorrect", "no": "incorrect", "n": "incorrect",
    "unknown": "unknown", "?": "unknown", "모름": "unknown",
}


def _file_meta(conn: sqlite3.Connection) -> dict:
    return {
        str(r["file_key"]): dict(r)
        for r in conn.execute(
            "SELECT file_key,txt_path,filename,ctype,lang,dup_group FROM files"
        )
    }


def _read_paras(out: Path, txt_path) -> list:
    if not txt_path:
        return []
    p = out / str(txt_path)
    if not p.exists():
        return []
    paras = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[¶(\d+)\]\t(.*)", line)
        if m:
            paras.append((int(m.group(1)), m.group(2)))
    return paras


def _raw_match(paras: list, terms: list):
    """Return (matched, snippet). matched=True if a topic term appears in text."""
    low_terms = [t.lower() for t in terms if len(t) >= 2]
    for no, text in paras:
        low = text.lower()
        if any(t in low for t in low_terms):
            body = text if len(text) <= 90 else text[:90] + "…"
            return True, f'¶{no}: "{body}"'
    return False, "(원문에서 관련 표현 미검출)"


def _auto_verdict(mode: str, matched: bool):
    """Conservative, bias-safe provisional verdict from raw text only.

    Only fills a verdict when the contract's own text *clearly shows* the
    clause; otherwise leaves it blank for the owner. Never auto-confirms an
    absence from mere keyword miss (shared blind spot risk).
    """
    if mode == "absent":
        # Text clearly shows the clause -> V4's absence claim is wrong.
        return ("incorrect", "원문에 조항 있음 → 부재판정 오류") if matched else (None, None)
    # existence / compare: text confirms the clause is present.
    return ("correct", "원문에 조항 확인") if matched else (None, None)


def _v4_evidence(conn: sqlite3.Connection, subtree: list, file_key: str) -> str:
    rows = conn.execute(
        "SELECT verbatim,loc_start FROM v4_clause_item "
        "WHERE file_key=? AND review_status='approved' AND taxonomy_id IN (%s) LIMIT 2"
        % ",".join("?" for _ in subtree),
        [file_key, *subtree],
    ).fetchall()
    if not rows:
        return "해당 조항 item 없음"
    parts = []
    for verbatim, loc in rows:
        v = str(verbatim)
        v = v if len(v) <= 80 else v[:80] + "…"
        parts.append(f'"{v}" ¶{loc}')
    return " / ".join(parts)


_HINT = {
    "existence": "그 계약에 해당 조항이 실제로 있으면 correct, 없으면 incorrect",
    "absence": "그 계약에 해당 조항이 정말 없으면 correct, 있으면 incorrect, 못 정하면 unknown",
    "comparison": "제시 근거가 원문과 맞으면 correct, 아니면 incorrect",
}


def build_cards(
    out: Path,
    seed_path: Path,
    depth: int,
    only: str | None,
    auto: bool = False,
    types: set | None = None,
    review_only: bool = False,
) -> str:
    """Build the worksheet. review_only keeps only items still needing a human
    decision (blank + V4-error candidates); auto-confirmed 'correct' items are
    omitted (capture them separately via `apply-auto`)."""
    report = evaluate_pooled(out, seed_path, pool_depth=depth)
    seed_by_id = {
        q["id"]: q
        for q in __import__("yaml").safe_load(seed_path.read_text(encoding="utf-8"))["queries"]
    }
    lines = [
        f"# Gate B 검증 워크시트 (생성 {datetime.now(timezone.utc).isoformat(timespec='seconds')})",
        "#",
        "# 각 `- verdict:` 뒤에 하나를 적으세요: correct(맞음/o) · incorrect(아님/x) · unknown(모름/?)",
        "# 빈 칸은 미검증으로 건너뜁니다. 일부만 채워도 됩니다.",
        "# 완료 후: python verify_gate_b.py ingest --seed <seed> --worksheet <이 파일>",
        "",
    ]
    with closing(connect_v4_ro(out)) as conn:
        meta = _file_meta(conn)
        for detail in report["details"]:
            qid = detail["id"]
            if only and qid != only:
                continue
            if detail.get("status") in ("unbound", "unresolved_taxonomy"):
                continue
            items = detail.get("unjudged", [])
            if not items:
                continue
            q = seed_by_id.get(qid, {})
            intent = q.get("intent", "")
            node = resolve_taxonomy(conn, str(detail["taxonomy"]))
            subtree = taxonomy_descendants(conn, str(node["taxonomy_id"]), True)
            terms = aliases(conn, str(node["taxonomy_id"]))
            note = ""
            if detail.get("mode") == "absent":
                # Only V4's *confirmed* absences need checking for precision;
                # needs_review items are already flagged uncertain by V4.
                absent = search_clause_absence(
                    out, str(detail["taxonomy"]), show_duplicates=True, limit=depth
                )
                confirmed = {str(r["file_key"]) for r in absent["confirmed_absent"]}
                items = [fk for fk in items if fk in confirmed]
                note = " (V4 confirmed_absent만 — needs_review 제외)"
                if not items:
                    continue
            item_lines = []
            seen_groups = set()
            for fk in items:
                m = meta.get(fk, {})
                if types and str(m.get("ctype", "")) not in types:
                    continue
                group = str(m.get("dup_group") or fk)
                if group in seen_groups:  # one representative per duplicate group
                    continue
                seen_groups.add(group)
                paras = _read_paras(out, m.get("txt_path"))
                matched, snippet = _raw_match(paras, terms)
                verdict, basis = _auto_verdict(detail.get("mode"), matched) if auto else (None, None)
                if review_only and verdict == "correct":
                    continue  # trusted auto-confirmation; owner need not see it
                item_lines.append(
                    f"### {m.get('filename') or fk}   [{m.get('ctype','?')} {m.get('lang','?')}]"
                )
                item_lines.append(f"- 파일키: {fk}")
                item_lines.append(f"- V4 판단: {_v4_evidence(conn, subtree, fk)}")
                item_lines.append(f"- 원문 근처: {snippet}")
                if verdict:
                    item_lines.append(f"- verdict: {verdict}   # auto(확인要): {basis}")
                else:
                    item_lines.append("- verdict: ")
                item_lines.append("")
            if not item_lines:
                continue
            lines.append(
                f"## {qid} — {q.get('query','')}  [mode: {detail.get('mode')}]{note}"
            )
            lines.append(f"검증법: {_HINT.get(intent, '')}")
            lines.append("")
            lines.extend(item_lines)
    return "\n".join(lines) + "\n"


def parse_worksheet(text: str) -> dict:
    verdicts: dict = {}
    qid = None
    fk = None
    for line in text.splitlines():
        s = line.strip()
        mq = re.match(r"##\s+(\S+)\s+—", s)
        if mq:
            qid = mq.group(1)
            verdicts.setdefault(qid, {"correct": [], "incorrect": [], "unknown": []})
            fk = None
            continue
        mk = re.match(r"-\s*파일키:\s*(\S+)", s)
        if mk:
            fk = mk.group(1)
            continue
        mv = re.match(r"-\s*verdict:\s*(.*)", s)
        if mv and qid and fk:
            raw = mv.group(1).split("#", 1)[0].strip().lower()  # drop "# auto:" note
            v = VERDICT_MAP.get(raw)
            if v:
                verdicts[qid][v].append(fk)
            fk = None
    # drop empty queries
    return {q: b for q, b in verdicts.items() if any(b.values())}


def _merge_query(old: dict, new: dict) -> dict:
    """Merge verdicts at file_key granularity; a new judgment overrides an old
    one for the same file_key (idempotent, incremental re-ingest)."""
    base = {b: list((old or {}).get(b, [])) for b in ("correct", "incorrect", "unknown")}
    changed = {fk for b in new.values() for fk in b}
    for b in base:
        base[b] = [fk for fk in base[b] if fk not in changed]
    for b, fks in new.items():
        base[b].extend(fks)
    for b in base:
        base[b] = list(dict.fromkeys(base[b]))
    return base


def ingest(seed_path: Path, worksheet: Path, verdicts_path: Path) -> dict:
    parsed = parse_worksheet(worksheet.read_text(encoding="utf-8"))
    existing = {}
    if verdicts_path.exists():
        existing = json.loads(verdicts_path.read_text(encoding="utf-8"))
    for qid, block in parsed.items():
        existing[qid] = _merge_query(existing.get(qid), block)  # per-file_key merge
    verdicts_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "queries_ingested": sorted(parsed),
        "verdicts_file": str(verdicts_path),
        "totals": {
            q: {k: len(v) for k, v in b.items()} for q, b in parsed.items()
        },
    }


def main(argv=None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cards", help="build the verification worksheet")
    c.add_argument("--out", type=Path, default=Path("cs_index"))
    c.add_argument(
        "--seed", type=Path, default=Path("data/golden_queries_v4_independent.seed.yaml")
    )
    c.add_argument("--pool-depth", type=int, default=25)
    c.add_argument("--query", help="only this query id (e.g. V4A07)")
    c.add_argument(
        "--auto",
        action="store_true",
        help="Pre-fill a conservative provisional verdict when the contract text "
        "clearly shows the clause (existence->correct, absence->incorrect). "
        "Bias-safe: never auto-confirms an absence from a keyword miss.",
    )
    c.add_argument(
        "--types",
        help="Comma-separated ctypes to keep (e.g. SPA,SSA,SHA,ATA/BTA). "
        "Drops off-scope docs (MOU/LOI) to cut volume without judging.",
    )
    c.add_argument(
        "--review-only",
        action="store_true",
        help="Only items still needing a human decision (blank + V4-error "
        "candidates). Omits auto-confirmed 'correct'; capture those with apply-auto.",
    )
    c.add_argument(
        "--worksheet", type=Path, default=Path("cs_index/gate_b_worksheet.md")
    )

    a = sub.add_parser(
        "apply-auto",
        help="Write trusted auto verdicts (text-confirmed existence->correct) "
        "straight to the verdicts json, so the owner only reviews the rest.",
    )
    a.add_argument("--out", type=Path, default=Path("cs_index"))
    a.add_argument(
        "--seed", type=Path, default=Path("data/golden_queries_v4_independent.seed.yaml")
    )
    a.add_argument("--pool-depth", type=int, default=25)
    a.add_argument("--types")
    a.add_argument(
        "--verdicts", type=Path, default=Path("data/v4_gate_b_verdicts.json")
    )

    s = sub.add_parser("set", help="record verdicts for specific file_keys (merged)")
    s.add_argument("--query", required=True)
    s.add_argument("--correct", default="")
    s.add_argument("--incorrect", default="")
    s.add_argument("--unknown", default="")
    s.add_argument(
        "--verdicts", type=Path, default=Path("data/v4_gate_b_verdicts.json")
    )

    g = sub.add_parser("ingest", help="read filled worksheet -> verdicts json")
    g.add_argument(
        "--seed", type=Path, default=Path("data/golden_queries_v4_independent.seed.yaml")
    )
    g.add_argument(
        "--worksheet", type=Path, default=Path("cs_index/gate_b_worksheet.md")
    )
    g.add_argument(
        "--verdicts", type=Path, default=Path("data/v4_gate_b_verdicts.json")
    )

    args = parser.parse_args(argv)
    if args.cmd == "cards":
        types = (
            {t.strip() for t in args.types.split(",") if t.strip()}
            if args.types
            else None
        )
        text = build_cards(
            args.out, args.seed, args.pool_depth, args.query,
            auto=args.auto, types=types, review_only=args.review_only,
        )
        args.worksheet.parent.mkdir(parents=True, exist_ok=True)
        args.worksheet.write_text(text, encoding="utf-8")
        print(f"wrote {args.worksheet}  (items: {text.count(chr(10) + '### ')})")
    elif args.cmd == "apply-auto":
        types = (
            {t.strip() for t in args.types.split(",") if t.strip()}
            if args.types
            else None
        )
        full = build_cards(
            args.out, args.seed, args.pool_depth, None, auto=True, types=types
        )
        parsed = parse_worksheet(full)
        # keep only the trusted, text-confirmed 'correct' verdicts
        trusted = {
            qid: {"correct": b["correct"], "incorrect": [], "unknown": []}
            for qid, b in parsed.items()
            if b["correct"]
        }
        existing = {}
        if args.verdicts.exists():
            existing = json.loads(args.verdicts.read_text(encoding="utf-8"))
        for qid, block in trusted.items():
            existing[qid] = _merge_query(existing.get(qid), block)
        args.verdicts.parent.mkdir(parents=True, exist_ok=True)
        args.verdicts.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        n = sum(len(b["correct"]) for b in trusted.values())
        print(f"applied {n} text-confirmed 'correct' verdicts to {args.verdicts}")
    elif args.cmd == "set":
        def _split(v):
            return [x.strip() for x in v.split(",") if x.strip()]
        block = {
            "correct": _split(args.correct),
            "incorrect": _split(args.incorrect),
            "unknown": _split(args.unknown),
        }
        existing = {}
        if args.verdicts.exists():
            existing = json.loads(args.verdicts.read_text(encoding="utf-8"))
        existing[args.query] = _merge_query(existing.get(args.query), block)
        args.verdicts.parent.mkdir(parents=True, exist_ok=True)
        args.verdicts.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({args.query: {k: len(v) for k, v in block.items()}}, ensure_ascii=False))
    else:
        summary = ingest(args.seed, args.worksheet, args.verdicts)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
