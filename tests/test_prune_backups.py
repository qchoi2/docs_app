"""Retention policy for catalog snapshots — fake files only, never the real ones."""

import os
import time

import pytest

from prune_backups import (
    DEFAULT_KEEP_DAYS,
    DEFAULT_KEEP_LATEST,
    PruneError,
    apply_policy,
    derive_origin,
    prune,
    scan,
)

DAY = 86400.0


def make_snapshot(path, *, age_days: float, size: int = 4096):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def make_dir_snapshot(path, *, age_days: float, size: int = 4096):
    path.mkdir(parents=True, exist_ok=True)
    inner = path / "catalog.sqlite"
    inner.write_bytes(b"x" * size)
    stamp = time.time() - age_days * DAY
    os.utime(inner, (stamp, stamp))
    os.utime(path, (stamp, stamp))
    return path


@pytest.fixture
def index(tmp_path):
    """cs_index/ with an active DB, incident evidence, and dated snapshots."""
    out = tmp_path / "cs_index"
    backups = out / ".backups"
    backups.mkdir(parents=True)
    make_snapshot(out / "catalog.sqlite", age_days=0, size=8192)
    make_snapshot(out / "catalog.sqlite.malformed_20260712", age_days=17)
    make_snapshot(out / "catalog.sqlite.corrupt_20260712.bak", age_days=17)
    for i, age in enumerate([10.0, 9.0, 8.0, 1.0]):
        make_snapshot(out / f"catalog.pre_taxonomy_v{i}_20260724.sqlite", age_days=age)
    for age in [12.0, 6.0, 0.5]:
        stamp = f"2026072{int(age)}T010101"
        make_snapshot(backups / f"catalog.pre_rw_reextract_{stamp}.sqlite", age_days=age)
    return out


def paths_of(report_rows):
    return {row["path"].replace("\\", "/").split("/")[-1] for row in report_rows}


def test_owner_policy_is_the_shipped_default():
    """소유자 결정(2026-07-29): 최근 2개 + 30일. 바꾸려면 소유자 재확인이 필요하다."""
    assert DEFAULT_KEEP_LATEST == 2
    assert DEFAULT_KEEP_DAYS == 30.0


def test_dry_run_is_the_default_and_touches_nothing(index):
    before = sorted(p.name for p in index.rglob("*"))
    # keep_days를 명시한다 — 이 테스트의 대상은 dry-run 동작이지 기본 보존기간이 아니다.
    # (기본값에 기대면 정책이 바뀔 때마다 무관한 테스트가 깨진다.)
    report = prune(out=index, roots=[index, index / ".backups"], keep_days=5.0)
    assert report["dry_run"] is True
    assert report["deleted"] == []
    assert report["counts"]["prune"] > 0
    assert sorted(p.name for p in index.rglob("*")) == before


def test_owner_default_keeps_everything_inside_the_30_day_window(index):
    """30일 정책에서는 이 fixture(최대 17일)의 스냅샷이 하나도 지워지지 않는다."""
    report = prune(out=index, roots=[index, index / ".backups"])
    assert report["counts"]["prune"] == 0


def test_delete_flag_actually_removes_only_the_pruned_entries(index):
    report = prune(out=index, roots=[index, index / ".backups"], delete=True)
    assert report["dry_run"] is False
    for row in report["prune"]:
        assert not (index.parent / row["path"]).exists() or not os.path.exists(row["path"])
    for row in report["keep"]:
        assert os.path.exists(row["path"])
    assert (index / "catalog.sqlite").exists()


def test_active_db_is_never_a_candidate(index):
    report = prune(out=index, roots=[index, index / ".backups"], keep_latest=0,
                   keep_days=0, include_incident=True)
    assert "catalog.sqlite" not in paths_of(report["prune"])
    kept = {row["path"] for row in report["keep"] if row["kind"] == "active"}
    assert any(p.endswith("catalog.sqlite") for p in kept)


def test_incident_evidence_is_excluded_by_default(index):
    report = prune(out=index, roots=[index, index / ".backups"],
                   keep_latest=0, keep_days=0)
    pruned = paths_of(report["prune"])
    assert "catalog.sqlite.malformed_20260712" not in pruned
    assert "catalog.sqlite.corrupt_20260712.bak" not in pruned
    incident = [r for r in report["keep"] if r["kind"] == "incident"]
    assert len(incident) == 2


def test_incident_evidence_needs_explicit_opt_in(index):
    report = prune(out=index, roots=[index, index / ".backups"],
                   keep_latest=0, keep_days=0, include_incident=True)
    pruned = paths_of(report["prune"])
    assert "catalog.sqlite.malformed_20260712" in pruned
    assert "catalog.sqlite.corrupt_20260712.bak" in pruned


def test_keep_days_alone_saves_a_snapshot_beyond_keep_latest(index):
    # keep_latest=0 so only the age rule can save anything.
    report = prune(out=index, roots=[index], keep_latest=0, keep_days=3)
    kept = paths_of(report["keep"])
    assert "catalog.pre_taxonomy_v3_20260724.sqlite" in kept  # 1 day old
    assert "catalog.pre_taxonomy_v0_20260724.sqlite" in paths_of(report["prune"])


def test_keep_latest_alone_saves_old_snapshots(index):
    # keep_days=0 so only the count rule can save anything.
    report = prune(out=index, roots=[index], keep_latest=2, keep_days=0)
    kept = paths_of(report["keep"])
    # newest two of the four snapshots: 1d and 8d
    assert "catalog.pre_taxonomy_v3_20260724.sqlite" in kept
    assert "catalog.pre_taxonomy_v2_20260724.sqlite" in kept
    pruned = paths_of(report["prune"])
    assert {"catalog.pre_taxonomy_v1_20260724.sqlite",
            "catalog.pre_taxonomy_v0_20260724.sqlite"} <= pruned


def test_either_rule_keeps_the_union(index):
    report = prune(out=index, roots=[index], keep_latest=1, keep_days=9.5)
    kept = paths_of(report["keep"])
    assert "catalog.pre_taxonomy_v3_20260724.sqlite" in kept   # newest (count)
    assert "catalog.pre_taxonomy_v2_20260724.sqlite" in kept   # 8d <= 9.5d (age)
    assert "catalog.pre_taxonomy_v1_20260724.sqlite" in kept   # 9d <= 9.5d (age)
    assert "catalog.pre_taxonomy_v0_20260724.sqlite" in paths_of(report["prune"])


def test_groups_are_independent_per_location(index):
    report = prune(out=index, roots=[index, index / ".backups"],
                   keep_latest=1, keep_days=0)
    kept = paths_of(report["keep"])
    # one survivor from cs_index/ and one from cs_index/.backups/
    assert "catalog.pre_taxonomy_v3_20260724.sqlite" in kept
    assert any(name.startswith("catalog.pre_rw_reextract") for name in kept)


def test_group_by_origin_keeps_one_per_workflow(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    make_snapshot(out / "catalog.sqlite", age_days=0)
    make_snapshot(out / "catalog.pre_rw_reextract_20260701T010101.sqlite", age_days=30)
    make_snapshot(out / "catalog.pre_rw_reextract_20260702T010101.sqlite", age_days=29)
    make_snapshot(out / "catalog.pre_pay_reextract_20260703T010101.sqlite", age_days=28)
    report = prune(out=out, roots=[out], keep_latest=1, keep_days=0, group_by="origin")
    kept = paths_of(report["keep"])
    # newest of each origin survives even though pay_* is the oldest overall
    assert "catalog.pre_rw_reextract_20260702T010101.sqlite" in kept
    assert "catalog.pre_pay_reextract_20260703T010101.sqlite" in kept
    assert "catalog.pre_rw_reextract_20260701T010101.sqlite" in paths_of(report["prune"])


def test_directory_snapshots_are_single_entries(tmp_path):
    dest = tmp_path / ".backups"
    dest.mkdir()
    for i, age in enumerate([20.0, 15.0, 10.0]):
        make_dir_snapshot(dest / f"cs_index_backup_2026070{i}_010101", age_days=age)
    report = prune(out=tmp_path / "cs_index", roots=[dest], keep_latest=1, keep_days=0)
    assert report["counts"]["prune"] == 2
    assert (dest / "cs_index_backup_20260702_010101").is_dir()
    prune(out=tmp_path / "cs_index", roots=[dest], keep_latest=1, keep_days=0,
          delete=True)
    assert not (dest / "cs_index_backup_20260700_010101").exists()
    assert (dest / "cs_index_backup_20260702_010101").is_dir()


def test_live_sidecars_follow_their_base_file(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    make_snapshot(out / "catalog.sqlite", age_days=0)
    make_snapshot(out / "catalog.sqlite-wal", age_days=0)
    make_snapshot(out / "catalog.sqlite-shm", age_days=0)
    report = prune(out=out, roots=[out], keep_latest=0, keep_days=0)
    assert report["counts"]["prune"] == 0
    active = [r for r in report["keep"] if r["kind"] == "active"]
    assert len(active) == 1
    assert len(active[0]["sidecars"]) == 2


def test_orphan_sidecars_are_swept(tmp_path):
    backups = tmp_path / ".backups"
    backups.mkdir()
    make_snapshot(backups / "catalog.pre_rw_reextract_20260701T010101.sqlite-wal",
                  age_days=1)
    make_snapshot(backups / "catalog.pre_rw_reextract_20260701T010101.sqlite-shm",
                  age_days=1)
    report = prune(out=tmp_path / "cs_index", roots=[backups])
    assert report["counts"]["by_kind"]["orphan"] == 2
    assert report["counts"]["prune"] == 2
    report = prune(out=tmp_path / "cs_index", roots=[backups], keep_orphans=True)
    assert report["counts"]["prune"] == 0


def test_unknown_files_are_reported_but_never_deleted(tmp_path):
    backups = tmp_path / ".backups"
    backups.mkdir()
    make_snapshot(backups / "README.txt", age_days=99)
    report = prune(out=tmp_path / "cs_index", roots=[backups], keep_latest=0, keep_days=0)
    assert report["counts"]["prune"] == 0
    assert report["counts"]["by_kind"]["other"] == 1


def test_unrelated_cs_index_artefacts_are_not_scanned(tmp_path):
    out = tmp_path / "cs_index"
    out.mkdir()
    make_snapshot(out / "catalog.sqlite", age_days=0)
    make_snapshot(out / "query_log.jsonl", age_days=99)
    (out / "txt").mkdir()
    report = prune(out=out, roots=[out], keep_latest=0, keep_days=0)
    scanned = {row["path"] for row in report["keep"] + report["prune"]}
    assert not any("query_log" in p or p.endswith("txt") for p in scanned)


def test_missing_root_is_tolerated(tmp_path):
    report = prune(out=tmp_path / "nope", roots=[tmp_path / "nope"])
    assert report["counts"]["scanned"] == 0
    assert report["reclaimable_bytes"] == 0


def test_negative_policy_values_are_rejected(index):
    with pytest.raises(PruneError):
        apply_policy(scan([index]), keep_latest=-1)
    with pytest.raises(PruneError):
        apply_policy(scan([index]), keep_days=-1)


def test_origin_strips_stamps_and_versions():
    from pathlib import Path
    assert derive_origin(Path("catalog.pre_taxonomy_v9_20260724.sqlite")) == "taxonomy"
    assert derive_origin(
        Path("catalog.pre_rw_reextract_20260729T070531.sqlite")) == "rw_reextract"
    assert derive_origin(Path("cs_index_backup_20260724_130731")) == "cs_index_backup"
    assert derive_origin(
        Path("catalog.pre_rw_reextract_20260728T005549.sqlite-wal")) == "rw_reextract"


def test_defaults_are_conservative():
    assert DEFAULT_KEEP_LATEST >= 1
    assert DEFAULT_KEEP_DAYS >= 1
