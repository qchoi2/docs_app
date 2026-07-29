#!/usr/bin/env python3
"""Contract version-role classification (체결본/초안/mark-up + 당사자).

계약서는 같은 거래(project)에 대해 여러 버전(체결본·매수인/매도인 초안·mark-up)이
존재한다. 이 도구는 파일명에서 version_role을 분류해 `files.version_role`에 저장하고
(검색 버전 필터의 기반), 재추출·정독 우선순위를 project 단위로 dedup(체결본 우선,
최종적으로는 전 버전 정독)하여 산출한다.

version_role 값:
  execution        체결본/최종본 (execution·signed·최종본·final·definitive)
  buyer_draft      매수인 초안
  seller_draft     매도인 초안
  buyer_markup     매수인 mark-up (mark-up·redline·수정·코멘트)
  seller_markup    매도인 mark-up
  draft_unknown    당사자 미상 초안
  markup_unknown   당사자 미상 mark-up
  buyer_ver / seller_ver  당사자만 식별, 단계 미상
  unknown          판별 불가

검색 표시용 한글 라벨은 VERSION_LABELS 참조.

Usage:
  python classify_version.py --out cs_index --apply          # DB에 version_role 부여(백업)
  python classify_version.py --out cs_index --priority OUT.json  # 재추출 우선순위(체결본 우선 dedup)
"""
import argparse
import collections
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

VERSION_LABELS = {
    "execution": "체결본",
    "bidding": "입찰제출본(매수인)",
    "buyer_draft": "매수인 초안",
    "seller_draft": "매도인 초안",
    "buyer_markup": "매수인 mark-up",
    "seller_markup": "매도인 mark-up",
    "draft_unknown": "초안(당사자 미상)",
    "markup_unknown": "mark-up(당사자 미상)",
    "buyer_ver": "매수인측 버전",
    "seller_ver": "매도인측 버전",
    "unknown": "버전 미상",
}

# 정독 우선순위: 낮을수록 먼저. 체결본이 최우선, 그 다음 초안, mark-up/bidding 순.
VERSION_RANK = {
    "execution": 0,
    "seller_draft": 2, "buyer_draft": 2, "draft_unknown": 2,
    "seller_markup": 3, "buyer_markup": 3, "markup_unknown": 3, "bidding": 3,
    "buyer_ver": 4, "seller_ver": 4,
    "unknown": 5,
}

_EXEC = ("체결", "execution", "signed", "signing", "exec_", "_exec",
         "최종본", "final", "fnl", "definitive")
_BIDDING = ("bidding", "제출본")
# mark-up 라운드: 초안 작성측의 상대방이 수정. "1st/2nd/3rd"(라운드 표기)도 mark-up이다.
_MARKUP = ("markup", "mark-up", "mark up", "redline", "수정", "코멘트", "comment",
           "1st", "2nd", "3rd")
_DRAFT = ("draft", "초안", "_v1", "내부", "안)")


def classify_version(filename: str) -> str:
    s = (filename or "").lower()
    if any(k in s for k in _EXEC):
        return "execution"
    if any(k in s for k in _BIDDING):
        return "bidding"          # 매수인 입찰제출본 — 별도 분류
    party = ("buyer" if any(k in s for k in ("buyer", "매수인"))
             else "seller" if any(k in s for k in ("seller", "매도인")) else None)
    # mark-up 라운드 판정을 draft보다 먼저 (예: "buyer 1st markup" → markup)
    stage = ("markup" if any(k in s for k in _MARKUP)
             else "draft" if any(k in s for k in _DRAFT) else None)
    if party and stage:
        return f"{party}_{stage}"
    if party:
        return f"{party}_ver"
    if stage:
        return f"{stage}_unknown"
    return "unknown"


def _markup_round(filename: str):
    """파일명의 mark-up 라운드 번호(1st/2nd/3rd → 1/2/3). 없으면 None."""
    m = re.search(r"(\d+)\s*(?:st|nd|rd|th)\b", (filename or "").lower())
    return int(m.group(1)) if m else None


def _resolve_markup_parties(base: dict, groups: dict) -> None:
    """당사자 미상 mark-up(markup_unknown)의 당사자를, 같은 거래(project)의 초안
    작성자와 라운드 패리티로 추론한다. 초안 작성자의 상대방이 1st mark-up을 하고,
    작성자 본인이 2nd mark-up(재수정)을 한다 → 홀수 라운드=상대방, 짝수=작성자.
    파일명에 당사자가 명시된 건 그대로 두고, 미상 + 라운드번호 있는 것만 보정한다.
    초안 작성자를 특정할 수 없는 거래는 markup_unknown으로 남긴다."""
    for members in groups.values():
        authors = set()
        for fk in members:
            vr = base[fk][0]
            if vr == "seller_draft":
                authors.add("seller")
            elif vr == "buyer_draft":
                authors.add("buyer")
        if len(authors) != 1:
            continue                       # 초안 작성자 불명확 → 보정 안 함
        author = next(iter(authors))
        opponent = "buyer" if author == "seller" else "seller"
        for fk in members:
            vr, rnd, _ = base[fk]
            if vr == "markup_unknown" and rnd:
                who = opponent if rnd % 2 == 1 else author
                base[fk][0] = f"{who}_markup"


def apply_to_db(out: Path) -> dict:
    db = out / "catalog.sqlite"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = out / f".backups/catalog.pre_version_role_{stamp}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as s, closing(sqlite3.connect(backup)) as d:
        s.backup(d)
    counts = {}
    with closing(sqlite3.connect(db)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(files)")}
        if "version_role" not in cols:
            conn.execute("ALTER TABLE files ADD COLUMN version_role TEXT")
        base = {}                          # file_key -> [role, round, filename]
        groups = collections.defaultdict(list)
        for fk, fn, path, ctype, lang in conn.execute(
            "SELECT file_key, filename, path, ctype, lang FROM files"
        ).fetchall():
            base[fk] = [classify_version(fn), _markup_round(fn), fn]
            groups[(ctype, lang, _project_key(path or ""))].append(fk)
        _resolve_markup_parties(base, groups)   # 라운드 패리티로 당사자 보정
        for fk, (vr, _, _) in base.items():
            conn.execute("UPDATE files SET version_role=? WHERE file_key=?", (vr, fk))
            counts[vr] = counts.get(vr, 0) + 1
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"backup": backup.name, "counts": counts, "integrity": integrity}


def _project_key(path: str) -> str:
    from review_v4_scope_sample import _project_key as pk
    return pk(path)


def build_priority(out: Path, manifest: Path) -> list:
    """재추출 대상을 거래(project)로 묶어 체결본 우선 대표를 뽑고, 나머지 버전은
    2차(최종 전부 정독) 큐로 둔다. 각 항목에 version_role·project·tier(1=체결본대표/
    1초안대표, 2=중복버전)를 붙인다."""
    db = out / "catalog.sqlite"
    man = json.loads(manifest.read_text(encoding="utf-8"))
    import collections
    groups = collections.defaultdict(list)
    with closing(sqlite3.connect(db)) as conn:
        for d in man:
            fk = d["file_key"]
            r = conn.execute(
                "SELECT path, filename, ctype, lang FROM files WHERE file_key=?", (fk,)
            ).fetchone()
            if not r:
                continue
            vr = classify_version(r[1])
            groups[(r[2], r[3], _project_key(r[0]))].append(
                {"file_key": fk, "ctype": r[2], "lang": r[3],
                 "version_role": vr, "rank": VERSION_RANK.get(vr, 5)}
            )
    out_rows = []
    for (ctype, lang, pk), members in groups.items():
        members.sort(key=lambda m: m["rank"])
        rep = members[0]
        for i, m in enumerate(members):
            m["project"] = pk
            m["reextract_tier"] = 1 if i == 0 else 2   # 1=대표(체결본 우선), 2=중복버전(2차)
            m["rep_is_execution"] = rep["version_role"] == "execution"
            out_rows.append(m)
    out_rows.sort(key=lambda m: (m["reextract_tier"], m["rank"]))
    return out_rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("cs_index"))
    p.add_argument("--apply", action="store_true", help="files.version_role 부여(백업 후)")
    p.add_argument("--priority", type=Path, help="재추출 우선순위 JSON 경로")
    p.add_argument("--manifest", type=Path, default=Path("cs_index/rw_reextraction_manifest.json"))
    args = p.parse_args(argv)
    if args.apply:
        res = apply_to_db(args.out)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    if args.priority:
        rows = build_priority(args.out, args.manifest)
        args.priority.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        t1 = sum(1 for r in rows if r["reextract_tier"] == 1)
        print(json.dumps({"total": len(rows), "tier1_representatives": t1,
                          "tier2_duplicate_versions": len(rows) - t1,
                          "written": str(args.priority)}, ensure_ascii=False, indent=1))
    if not args.apply and not args.priority:
        p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
