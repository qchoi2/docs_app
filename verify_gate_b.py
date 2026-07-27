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
from v4_search import connect_v4_ro, resolve_taxonomy, taxonomy_descendants

VERDICT_MAP = {
    "correct": "correct", "o": "correct", "맞음": "correct", "yes": "correct", "y": "correct",
    "incorrect": "incorrect", "x": "incorrect", "아님": "incorrect", "no": "incorrect", "n": "incorrect",
    "unknown": "unknown", "?": "unknown", "모름": "unknown",
}


def _file_meta(conn: sqlite3.Connection) -> dict:
    return {
        str(r["file_key"]): dict(r)
        for r in conn.execute(
            "SELECT file_key,txt_path,filename,ctype,lang FROM files"
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


def _raw_snippet(paras: list, terms: list) -> str:
    low_terms = [t.lower() for t in terms if len(t) >= 2]
    for no, text in paras:
        low = text.lower()
        if any(t in low for t in low_terms):
            body = text if len(text) <= 90 else text[:90] + "…"
            return f'¶{no}: "{body}"'
    return "(원문에서 관련 표현 미검출)"


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


def build_cards(out: Path, seed_path: Path, depth: int, only: str | None) -> str:
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
            lines.append(
                f"## {qid} — {q.get('query','')}  [mode: {detail.get('mode')}]"
            )
            lines.append(f"검증법: {_HINT.get(intent, '')}")
            lines.append("")
            for fk in items:
                m = meta.get(fk, {})
                paras = _read_paras(out, m.get("txt_path"))
                lines.append(
                    f"### {fk}  [{m.get('ctype','?')} {m.get('lang','?')}]  {m.get('filename','')}"
                )
                lines.append(f"- V4 판단: {_v4_evidence(conn, subtree, fk)}")
                lines.append(f"- 원문 근처: {_raw_snippet(paras, terms)}")
                lines.append("- verdict: ")
                lines.append("")
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
        mf = re.match(r"###\s+(\S+)", s)
        if mf:
            fk = mf.group(1)
            continue
        mv = re.match(r"-\s*verdict:\s*(.*)", s)
        if mv and qid and fk:
            raw = mv.group(1).strip().lower()
            v = VERDICT_MAP.get(raw)
            if v:
                verdicts[qid][v].append(fk)
            fk = None
    # drop empty queries
    return {q: b for q, b in verdicts.items() if any(b.values())}


def ingest(seed_path: Path, worksheet: Path, verdicts_path: Path) -> dict:
    parsed = parse_worksheet(worksheet.read_text(encoding="utf-8"))
    existing = {}
    if verdicts_path.exists():
        existing = json.loads(verdicts_path.read_text(encoding="utf-8"))
    existing.update(parsed)  # re-ingest overwrites a query's verdicts
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
        "--worksheet", type=Path, default=Path("cs_index/gate_b_worksheet.md")
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
        text = build_cards(args.out, args.seed, args.pool_depth, args.query)
        args.worksheet.parent.mkdir(parents=True, exist_ok=True)
        args.worksheet.write_text(text, encoding="utf-8")
        print(f"wrote {args.worksheet}")
    else:
        summary = ingest(args.seed, args.worksheet, args.verdicts)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
