"""Guards against silent catalog corruption (see RECOVERY_20260712.md).

Two lightweight, non-blocking checks used by the write-path CLIs
(index_contracts.py, enrich_contracts.py):

- ``risky_out_path_warnings(path)`` warns when ``--out`` lives on a network,
  mapped, or file-sync location. SQLite in WAL mode is unsafe on such
  filesystems and has truncated the catalog before; large index/enrich writes
  belong on a local disk.
- ``integrity_warnings(db_path)`` runs ``PRAGMA quick_check`` after a write
  batch so corruption is caught immediately instead of many sessions later.

Both functions return a list of human-readable warning strings and never
raise. Callers print them (typically to stderr). Nothing here blocks a run.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import List

# Folder-name markers for common file-sync clients (matched case-insensitively).
_SYNC_MARKERS = (
    "onedrive",
    "dropbox",
    "google drive",
    "googledrive",
    "box sync",
    "icloud",
)


def risky_out_path_warnings(path) -> List[str]:
    """Return warnings if ``path`` looks like an unsafe location for the catalog."""
    warnings: List[str] = []
    # Match against the raw input so UNC prefixes survive on non-Windows hosts,
    # where Path.resolve() would rewrite backslashes.
    raw = str(path)
    lowered = raw.lower()
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        resolved = None

    if raw.startswith("\\\\") or raw.startswith("//"):
        warnings.append(
            "risky_out_path:network_share - --out looks like a network share (%s). "
            "SQLite WAL is unsafe on network filesystems and has corrupted the catalog "
            "before; use a local disk such as C:\\cs_index." % raw
        )

    if resolved is not None and _is_windows_network_drive(resolved):
        warnings.append(
            "risky_out_path:mapped_drive - --out is on a mapped network drive (%s). "
            "Use a local disk to avoid catalog corruption." % raw
        )

    for marker in _SYNC_MARKERS:
        if marker in lowered:
            warnings.append(
                "risky_out_path:sync_folder - --out is inside a file-sync folder "
                "('%s' in %s). Live sync during large SQLite writes can corrupt the "
                "catalog; use a local, non-synced disk." % (marker, raw)
            )
            break

    return warnings


def _is_windows_network_drive(resolved: Path) -> bool:
    """Best-effort DRIVE_REMOTE detection on Windows; False everywhere else."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        drive = os.path.splitdrive(str(resolved))[0]
        if not drive:
            return False
        root = drive + "\\"
        # GetDriveTypeW: DRIVE_REMOTE == 4
        return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 4
    except Exception:
        return False


def integrity_warnings(db_path) -> List[str]:
    """Return warnings unless ``db_path`` passes SQLite ``PRAGMA quick_check``."""
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % path.as_posix(), uri=True)
        try:
            row = conn.execute("PRAGMA quick_check").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return [
            "integrity_check:failed - %s could not be verified (%s). The catalog may "
            "be corrupt; see RECOVERY_20260712.md." % (path, exc)
        ]
    result = row[0] if row else None
    if result != "ok":
        return [
            "integrity_check:not_ok - %s failed quick_check (%s). "
            "See RECOVERY_20260712.md." % (path, result)
        ]
    return []
