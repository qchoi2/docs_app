"""catalog 스냅샷 보존 정책 도구 (retention for DB safety snapshots).

여러 쓰기 경로가 작업 전 catalog 스냅샷을 만들지만(``store_rw_reextraction.py``,
``store_pay_reextraction.py``, ``classify_version.py --apply``,
``audit_rw_coverage.py --reclassify``, ``reextract_rw_pilot.py``,
``backup_index.py``, 그리고 수동 ``catalog.pre_*.sqlite`` 복사), **아무도 지우지
않는다.** 스냅샷 하나가 0.6~1.7 GB이므로 방치하면 수십 GB가 쌓인다.

이 도구는 스냅샷을 나열하고 보존 정책을 적용한다. 기본은 **dry-run**이며,
실제 삭제는 ``--delete``를 명시해야 한다.

정책(둘 중 **하나라도** 만족하면 보존) — 소유자 결정 2026-07-29:
**최근 2개 + 30일, 손상본(incident)은 보존.**
  * 그룹 내 최신 ``--keep-latest N`` 개 안에 든다 (기본 2)
  * ``--keep-days D`` 일 이내다 (기본 30)

30일 기준에서는 최근 배치 스냅샷이 한동안 남는다. 즉시 디스크를 회수해야 하면
``--keep-days``를 낮춰 dry-run으로 확인한 뒤 소유자에게 확인받고 삭제한다.

분류:
  * ``snapshot`` — 일상 스냅샷. 정책 대상.
  * ``incident`` — 사고 증거(2026-07-12 손상 포렌식: ``*.malformed_*``,
    ``*.corrupt_*``). **기본적으로 절대 지우지 않는다.** ``--include-incident``
    로만 정책 대상이 된다.
  * ``active``  — 살아 있는 DB(catalog/ui_state/jobs.sqlite와 -wal/-shm). 대상 아님.
  * ``orphan``  — 본체 없이 남은 ``-wal``/``-shm``/``-journal`` 찌꺼기. 나이와
    무관하게 삭제 대상(``--keep-orphans``로 보존).
  * ``other``   — 알 수 없는 항목. 보고만 하고 절대 지우지 않는다.

사용:
    python prune_backups.py --out cs_index                 # dry-run (기본)
    python prune_backups.py --out cs_index --keep-latest 1 --keep-days 1
    python prune_backups.py --out cs_index --delete        # 실제 삭제
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from lib.console import configure_utf8_stdio

# 소유자 결정 (2026-07-29): "최근 2개 + 30일, 손상본은 보존".
# 30일은 짧은 기간보다 회수량이 적지만, 스냅샷은 되돌릴 수 없는 DB 쓰기 직전의
# 유일한 롤백 지점이라 소유자가 디스크보다 복구 여지를 택했다. 이 기본값을
# 바꾸려면 소유자 재확인이 필요하다.
DEFAULT_KEEP_LATEST = 2
DEFAULT_KEEP_DAYS = 30.0

# 살아 있는 DB — 어떤 경우에도 후보가 되지 않는다.
ACTIVE_NAMES = {"catalog.sqlite", "ui_state.sqlite", "jobs.sqlite"}
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
# 사고 포렌식 증거. 일상 스냅샷과 절대 섞지 않는다 (RECOVERY_20260712.md).
INCIDENT_MARKERS = ("malformed", "corrupt")

# _20260724 / _20260729T070531 / _20260724_130731 / _20260727_1645
_STAMP_RE = re.compile(r"(?:[_.]\d{8}(?:T\d{6}|_\d{4,6})?)+$")
_VERSION_TAIL_RE = re.compile(r"_v\d+$")

# origin -> 그 스냅샷을 만드는 코드 경로 (보고용)
ORIGIN_CREATORS = {
    "rw_reextract": "store_rw_reextraction.py",
    "pay_reextract": "store_pay_reextraction.py",
    "rw_audit": "audit_rw_coverage.py --reclassify",
    "rw_pilot": "reextract_rw_pilot.py",
    "version_role": "classify_version.py --apply",
    "cs_index_backup": "backup_index.py",
    "taxonomy": "taxonomy_admin.py 작업 전 수동 스냅샷",
}


class PruneError(RuntimeError):
    """Raised for an unusable --path / --out argument."""


@dataclass
class Entry:
    path: Path
    root: Path
    kind: str
    origin: str
    mtime: float
    size: int
    sidecars: List[Path] = field(default_factory=list)
    keep: bool = True
    reason: str = ""

    @property
    def age_days(self) -> float:
        return max(0.0, (time.time() - self.mtime) / 86400.0)

    @property
    def group_location(self) -> str:
        return str(self.root)

    def targets(self) -> List[Path]:
        """Every path removed when this entry is pruned (body + sidecars)."""
        return [self.path, *self.sidecars]

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "root": str(self.root),
            "kind": self.kind,
            "origin": self.origin,
            "creator": ORIGIN_CREATORS.get(self.origin, "unknown (수동/일회성)"),
            "age_days": round(self.age_days, 2),
            "size_bytes": self.size,
            "size_h": human_size(self.size),
            "sidecars": [str(p) for p in self.sidecars],
            "keep": self.keep,
            "reason": self.reason,
        }


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0 or unit == "TB":
            return f"{num:,.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def dir_size_mtime(path: Path) -> tuple:
    """Recursive (size, newest mtime) for a directory entry."""
    total = 0
    newest = path.stat().st_mtime
    for child in path.rglob("*"):
        try:
            stat = child.stat()
        except OSError:
            continue
        if child.is_file():
            total += stat.st_size
        newest = max(newest, stat.st_mtime)
    return total, newest


def strip_stamp(name: str) -> str:
    """Drop trailing date/time stamps and _v<N> so siblings share an origin."""
    prev = None
    while prev != name:
        prev = name
        name = _STAMP_RE.sub("", name)
        name = _VERSION_TAIL_RE.sub("", name)
    return name


def classify(path: Path, in_backup_dir: bool) -> str:
    name = path.name
    lowered = name.lower()
    if any(marker in lowered for marker in INCIDENT_MARKERS):
        return "incident"
    if path.is_dir():
        return "snapshot" if in_backup_dir else "other"
    if not in_backup_dir and name in ACTIVE_NAMES:
        return "active"
    # Only DB-shaped files are snapshots — a stray note left in .backups/ is
    # "other" and never swept.
    looks_like_db = ".sqlite" in name or lowered.endswith((".db", ".bak"))
    if looks_like_db and (in_backup_dir or ".pre_" in name):
        return "snapshot"
    return "other"


def derive_origin(path: Path) -> str:
    name = path.name
    for suffix in SIDECAR_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if name.endswith(".bak"):
        name = name[: -len(".bak")]
    if name.endswith(".sqlite"):
        name = name[: -len(".sqlite")]
    for prefix in ("catalog.pre_", "catalog.sqlite.", "ui_state.sqlite.",
                   "jobs.sqlite.", "catalog."):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    name = strip_stamp(name)
    return name or path.name


def sidecar_base(path: Path) -> Optional[Path]:
    for suffix in SIDECAR_SUFFIXES:
        if path.name.endswith(suffix):
            return path.with_name(path.name[: -len(suffix)])
    return None


def default_roots(out: Path, repo_root: Optional[Path] = None) -> List[Path]:
    """cs_index/, cs_index/.backups/, and the repo-root .backups/."""
    out = Path(out)
    repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parent
    roots = [out, out / ".backups", repo_root / ".backups"]
    seen, unique = set(), []
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def scan(roots: Sequence[Path]) -> List[Entry]:
    """Collect one Entry per snapshot/incident/active item across roots."""
    entries: List[Entry] = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        in_backup_dir = root.name == ".backups"
        children = sorted(root.iterdir())
        # Only .sqlite-ish names matter outside a dedicated .backups directory —
        # cs_index/ also holds thousands of unrelated json/txt artefacts.
        candidates = [
            c for c in children if in_backup_dir or ".sqlite" in c.name
        ]
        by_name = {c.name: c for c in candidates}
        pending_sidecars: List[Path] = []
        local: Dict[str, Entry] = {}
        for child in candidates:
            base = sidecar_base(child)
            if base is not None and base.name in by_name:
                pending_sidecars.append(child)
                continue
            try:
                if child.is_dir():
                    size, mtime = dir_size_mtime(child)
                else:
                    stat = child.stat()
                    size, mtime = stat.st_size, stat.st_mtime
            except OSError:
                continue
            kind = "orphan" if base is not None else classify(child, in_backup_dir)
            entry = Entry(
                path=child,
                root=root,
                kind=kind,
                origin=derive_origin(child),
                mtime=mtime,
                size=size,
            )
            local[child.name] = entry
            entries.append(entry)
        for sidecar in pending_sidecars:
            base = sidecar_base(sidecar)
            owner = local.get(base.name) if base else None
            if owner is not None:
                owner.sidecars.append(sidecar)
                try:
                    owner.size += sidecar.stat().st_size
                except OSError:
                    pass
    return entries


def apply_policy(
    entries: Sequence[Entry],
    *,
    keep_latest: int = DEFAULT_KEEP_LATEST,
    keep_days: float = DEFAULT_KEEP_DAYS,
    group_by: str = "location",
    include_incident: bool = False,
    keep_orphans: bool = False,
) -> List[Entry]:
    """Mark each entry keep/prune. Returns the entries scheduled for deletion."""
    if keep_latest < 0:
        raise PruneError("--keep-latest는 0 이상이어야 합니다.")
    if keep_days < 0:
        raise PruneError("--keep-days는 0 이상이어야 합니다.")

    prunable_kinds = {"snapshot"}
    if include_incident:
        prunable_kinds.add("incident")

    for entry in entries:
        entry.keep = True
        if entry.kind == "active":
            entry.reason = "active DB — 대상 아님"
        elif entry.kind == "other":
            entry.reason = "미분류 — 자동 삭제하지 않음"
        elif entry.kind == "incident":
            entry.reason = "사고 증거 — --include-incident 필요"
        elif entry.kind == "orphan":
            if keep_orphans:
                entry.reason = "orphan sidecar (--keep-orphans)"
            else:
                entry.keep = False
                entry.reason = "orphan sidecar — 본체 없음"
        else:
            entry.reason = ""

    groups: Dict[str, List[Entry]] = {}
    for entry in entries:
        if entry.kind not in prunable_kinds:
            continue
        key = entry.origin if group_by == "origin" else entry.group_location
        groups.setdefault(key, []).append(entry)

    for key, members in groups.items():
        members.sort(key=lambda e: e.mtime, reverse=True)
        for index, entry in enumerate(members):
            recent_enough = entry.age_days <= keep_days
            within_latest = index < keep_latest
            if within_latest or recent_enough:
                entry.keep = True
                why = []
                if within_latest:
                    why.append(f"최신 {keep_latest}개 중 #{index + 1}")
                if recent_enough:
                    why.append(f"{entry.age_days:.1f}일 <= {keep_days:g}일")
                entry.reason = f"[{key}] " + " / ".join(why)
            else:
                entry.keep = False
                entry.reason = (
                    f"[{key}] #{index + 1} > 최신 {keep_latest}개 이고 "
                    f"{entry.age_days:.1f}일 > {keep_days:g}일"
                )

    return [e for e in entries if not e.keep]


def delete_entries(entries: Sequence[Entry]) -> List[dict]:
    """Remove the given entries (body + sidecars). Errors are reported, not raised."""
    removed: List[dict] = []
    for entry in entries:
        for target in entry.targets():
            record = {"path": str(target), "ok": True, "error": None}
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                else:
                    record["ok"] = False
                    record["error"] = "already gone"
            except OSError as exc:
                record["ok"] = False
                record["error"] = str(exc)
            removed.append(record)
    return removed


def prune(
    *,
    out: Path,
    roots: Optional[Sequence[Path]] = None,
    keep_latest: int = DEFAULT_KEEP_LATEST,
    keep_days: float = DEFAULT_KEEP_DAYS,
    group_by: str = "location",
    include_incident: bool = False,
    keep_orphans: bool = False,
    delete: bool = False,
    repo_root: Optional[Path] = None,
) -> dict:
    """Scan, apply the policy, and optionally delete. Returns a JSON-able report.

    ``delete=False`` (the default) is a pure dry-run: nothing is touched.
    """
    scan_roots = list(roots) if roots else default_roots(out, repo_root)
    entries = scan(scan_roots)
    doomed = apply_policy(
        entries,
        keep_latest=keep_latest,
        keep_days=keep_days,
        group_by=group_by,
        include_incident=include_incident,
        keep_orphans=keep_orphans,
    )
    removed = delete_entries(doomed) if delete else []
    kept = [e for e in entries if e.keep]
    by_kind: Dict[str, int] = {}
    for entry in entries:
        by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
    reclaimable = sum(e.size for e in doomed)
    return {
        "dry_run": not delete,
        "roots": [str(r) for r in scan_roots],
        "policy": {
            "keep_latest": keep_latest,
            "keep_days": keep_days,
            "group_by": group_by,
            "include_incident": include_incident,
            "keep_orphans": keep_orphans,
        },
        "counts": {
            "scanned": len(entries),
            "keep": len(kept),
            "prune": len(doomed),
            "by_kind": by_kind,
        },
        "reclaimable_bytes": reclaimable,
        "reclaimable_h": human_size(reclaimable),
        "total_bytes": sum(e.size for e in entries),
        "prune": [e.as_dict() for e in sorted(doomed, key=lambda e: e.mtime)],
        "keep": [e.as_dict() for e in sorted(kept, key=lambda e: e.mtime)],
        "deleted": removed,
    }


def render_text(report: dict) -> str:
    lines: List[str] = []
    mode = "DRY-RUN (아무것도 지우지 않음)" if report["dry_run"] else "DELETE"
    policy = report["policy"]
    lines.append(f"모드: {mode}")
    lines.append(
        "정책: keep-latest={keep_latest} 또는 keep-days={keep_days:g} "
        "(group-by={group_by}, include-incident={include_incident})".format(**policy)
    )
    lines.append("스캔 경로: " + ", ".join(report["roots"]))
    lines.append("")

    def table(title: str, rows: List[dict]) -> None:
        lines.append(f"== {title} ({len(rows)}건) ==")
        if not rows:
            lines.append("  (없음)")
            lines.append("")
            return
        for row in rows:
            lines.append(
                f"  {row['size_h']:>9}  {row['age_days']:>6.1f}d  "
                f"{row['kind']:<8}  {row['path']}"
            )
            lines.append(f"                            origin={row['origin']} "
                         f"creator={row['creator']}")
            lines.append(f"                            {row['reason']}")
            for sidecar in row["sidecars"]:
                lines.append(f"                            + {sidecar}")
        lines.append("")

    table("삭제 대상", report["prune"])
    table("보존", report["keep"])
    counts = report["counts"]
    lines.append(
        f"합계: 스캔 {counts['scanned']}건 / 보존 {counts['keep']}건 / "
        f"삭제 {counts['prune']}건 · 회수 가능 {report['reclaimable_h']} "
        f"(전체 {human_size(report['total_bytes'])})"
    )
    if report["dry_run"] and counts["prune"]:
        lines.append("실제 삭제하려면 --delete 를 붙여 다시 실행하세요.")
    for record in report["deleted"]:
        if not record["ok"]:
            lines.append(f"삭제 실패: {record['path']} — {record['error']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="catalog 스냅샷 보존 정책 적용 (기본 dry-run).",
    )
    parser.add_argument("--out", type=Path, default=Path("cs_index"),
                        help="cs_index 폴더 (기본: cs_index)")
    parser.add_argument("--path", type=Path, action="append", dest="paths",
                        help="스캔할 폴더 직접 지정 (반복 가능; 기본 경로를 대체)")
    parser.add_argument("--keep-latest", type=int, default=DEFAULT_KEEP_LATEST,
                        help=f"그룹별 보존 개수 (기본 {DEFAULT_KEEP_LATEST})")
    parser.add_argument("--keep-days", type=float, default=DEFAULT_KEEP_DAYS,
                        help=f"보존 기간(일) (기본 {DEFAULT_KEEP_DAYS:g}). "
                             "개수·기간 중 하나만 만족해도 보존한다.")
    parser.add_argument("--group-by", choices=["location", "origin"], default="location",
                        help="keep-latest를 적용할 그룹 단위 (기본 location)")
    parser.add_argument("--include-incident", action="store_true",
                        help="2026-07-12 손상 포렌식 등 사고 증거도 정책 대상에 포함")
    parser.add_argument("--keep-orphans", action="store_true",
                        help="본체 없는 -wal/-shm 찌꺼기도 남긴다")
    parser.add_argument("--dry-run", action="store_true",
                        help="기본 동작 (명시적으로 적어도 된다)")
    parser.add_argument("--delete", action="store_true",
                        help="실제로 삭제한다. 없으면 dry-run이다.")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.delete and args.dry_run:
        print("ERROR: --delete 와 --dry-run 을 함께 쓸 수 없습니다.", file=sys.stderr)
        return 2
    try:
        report = prune(
            out=args.out,
            roots=args.paths,
            keep_latest=args.keep_latest,
            keep_days=args.keep_days,
            group_by=args.group_by,
            include_incident=args.include_incident,
            keep_orphans=args.keep_orphans,
            delete=args.delete,
        )
    except PruneError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
          else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
