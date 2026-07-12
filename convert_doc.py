from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from index_contracts import TypeRules, is_misc_path, load_type_rules
from lib.console import configure_utf8_stdio


OLE2_MAGIC = bytes.fromhex("D0CF11E0")
RTF_MAGIC = b"{\\rtf"
ZIP_MAGIC = b"PK"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_CHUNK_SIZE = 25
DEFAULT_TIMEOUT = 300


@dataclass
class DocCandidate:
    path: Path
    rel_path: str
    source_sha256: str
    target_path: Path
    target_rel: str


class ConvertDocError(RuntimeError):
    pass


class WordUnavailableError(ConvertDocError):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(out_dir: Path) -> Dict[str, object]:
    path = out_dir / "converted" / "manifest.json"
    if not path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION, "items": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConvertDocError("invalid manifest.json: %s" % exc)
    if not isinstance(data, dict):
        raise ConvertDocError("manifest.json must be an object")
    if not isinstance(data.get("items"), dict):
        data["items"] = {}
    data["schema_version"] = MANIFEST_SCHEMA_VERSION
    return data


def write_manifest(out_dir: Path, manifest: Dict[str, object]) -> Path:
    converted_dir = out_dir / "converted"
    converted_dir.mkdir(parents=True, exist_ok=True)
    path = converted_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def detect_doc_kind(path: Path) -> str:
    try:
        prefix = path.read_bytes()[:8]
    except OSError:
        return "unreadable"
    if prefix.startswith(OLE2_MAGIC):
        return "ole2"
    if prefix.startswith(RTF_MAGIC):
        return "rtf"
    if prefix.startswith(ZIP_MAGIC):
        return "zip"
    return "unknown"


def iter_doc_paths(root: Path, include_misc: bool, rules: TypeRules) -> List[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() == ".doc"
        and (include_misc or not is_misc_path(path.relative_to(root), rules))
    )


def build_candidates(
    root: Path,
    out_dir: Path,
    *,
    include_misc: bool = False,
    manifest: Optional[Dict[str, object]] = None,
) -> Tuple[List[DocCandidate], List[Dict[str, str]], int]:
    rules = load_type_rules()
    manifest = manifest or load_manifest(out_dir)
    items = manifest.setdefault("items", {})
    converted_dir = out_dir / "converted"
    candidates: List[DocCandidate] = []
    rejected: List[Dict[str, str]] = []
    skipped = 0

    for path in iter_doc_paths(root, include_misc, rules):
        rel_path = path.relative_to(root).as_posix()
        kind = detect_doc_kind(path)
        if kind != "ole2":
            rejected.append({"path": rel_path, "reason": "not_ole2_%s" % kind})
            items[rel_path] = {
                "source_path": rel_path,
                "status": "unsupported",
                "error_reason": "not_ole2_%s" % kind,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            continue
        data = path.read_bytes()
        source_sha256 = sha256_hex(data)
        existing = items.get(rel_path)
        target_rel = "converted/%s.docx" % source_sha256
        target_path = converted_dir / ("%s.docx" % source_sha256)
        if (
            isinstance(existing, dict)
            and existing.get("status") == "ok"
            and existing.get("source_sha256") == source_sha256
            and target_path.exists()
        ):
            skipped += 1
            continue
        candidates.append(
            DocCandidate(
                path=path,
                rel_path=rel_path,
                source_sha256=source_sha256,
                target_path=target_path,
                target_rel=target_rel,
            )
        )
    return candidates, rejected, skipped


def chunks(items: Sequence[DocCandidate], size: int) -> List[List[DocCandidate]]:
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


def run_powershell_converter(
    jobs: Sequence[DocCandidate],
    *,
    worker_path: Path,
    converted_dir: Path,
    timeout: int,
) -> List[Dict[str, object]]:
    converted_dir.mkdir(parents=True, exist_ok=True)
    input_path = converted_dir / "convert_jobs.json"
    output_path = converted_dir / "convert_results.json"
    payload = [
        {"source": str(job.path.resolve()), "target": str(job.target_path.resolve())}
        for job in jobs
    ]
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")
    command = [
        "powershell",
        "-Sta",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(worker_path),
        "-InputJson",
        str(input_path),
        "-OutputJson",
        str(output_path),
    ]
    proc = subprocess.run(command, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        raise ConvertDocError((stderr or stdout or "PowerShell conversion failed").strip())
    try:
        data = json.loads(output_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConvertDocError("invalid PowerShell conversion output: %s" % exc)
    if isinstance(data, dict):
        results = [data]
    elif isinstance(data, list):
        results = [item for item in data if isinstance(item, dict)]
    else:
        raise ConvertDocError("PowerShell conversion output must be object or array")
    for item in results:
        if item.get("status") == "fatal" and item.get("source") is None:
            raise WordUnavailableError(str(item.get("error_reason") or "Microsoft Word is unavailable"))
    return results


def update_manifest_from_results(
    manifest: Dict[str, object],
    jobs: Sequence[DocCandidate],
    results: Sequence[Dict[str, object]],
) -> Tuple[int, List[Dict[str, str]]]:
    fatal_reason = None
    for item in results:
        if item.get("status") == "fatal" and item.get("source") is None:
            fatal_reason = str(item.get("error_reason") or "fatal_conversion_error")
            break
    by_source = {str(item.get("source")): item for item in results if item.get("source") is not None}
    items = manifest.setdefault("items", {})
    converted = 0
    failures: List[Dict[str, str]] = []
    now = datetime.now(timezone.utc).isoformat()
    for job in jobs:
        result = by_source.get(str(job.path.resolve()))
        status = str(result.get("status")) if result else "error"
        error_reason = (
            str(result.get("error_reason") or "missing_result")
            if result
            else (fatal_reason or "missing_result")
        )
        converter_version = result.get("converter_version") if result else None
        if status == "ok" and job.target_path.exists():
            converted += 1
            items[job.rel_path] = {
                "source_path": job.rel_path,
                "source_sha256": job.source_sha256,
                "converted_docx": job.target_rel,
                "converted_at": now,
                "converter_version": converter_version,
                "status": "ok",
                "error_reason": None,
            }
        else:
            failures.append({"path": job.rel_path, "reason": error_reason})
            items[job.rel_path] = {
                "source_path": job.rel_path,
                "source_sha256": job.source_sha256,
                "converted_docx": job.target_rel,
                "converted_at": now,
                "converter_version": converter_version,
                "status": "error",
                "error_reason": error_reason,
            }
    return converted, failures


def failure_result_for_job(job: DocCandidate, reason: str) -> Dict[str, object]:
    return {
        "source": str(job.path.resolve()),
        "target": str(job.target_path.resolve()),
        "status": "error",
        "error_reason": reason,
        "converter_version": None,
    }


def convert_docs(
    root: Path,
    out: Path,
    *,
    include_misc: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int = DEFAULT_TIMEOUT,
    dry_run: bool = False,
    worker_path: Optional[Path] = None,
) -> Dict[str, object]:
    root_path = Path(root).resolve()
    out_dir = Path(out).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ConvertDocError("root must be an existing directory: %s" % root_path)
    if chunk_size < 1:
        raise ConvertDocError("--chunk-size must be >= 1")

    manifest = load_manifest(out_dir)
    candidates, rejected, skipped = build_candidates(
        root_path, out_dir, include_misc=include_misc, manifest=manifest
    )
    converted = 0
    failures: List[Dict[str, str]] = list(rejected)
    quarantined: List[Dict[str, str]] = []

    if not dry_run and candidates:
        worker = worker_path or (Path(__file__).resolve().parent / "convert_doc_worker.ps1")
        if not worker.exists():
            raise ConvertDocError("PowerShell worker not found: %s" % worker)
        index = 0
        while index < len(candidates):
            group = candidates[index : index + chunk_size]
            try:
                results = run_powershell_converter(
                    group,
                    worker_path=worker,
                    converted_dir=out_dir / "converted",
                    timeout=timeout,
                )
            except WordUnavailableError:
                raise
            except (subprocess.TimeoutExpired, ConvertDocError) as exc:
                suspect = group[0]
                reason = str(exc)
                quarantined.append({"path": suspect.rel_path, "reason": reason})
                results = [failure_result_for_job(suspect, reason)]
                group = [suspect]
            group_converted, group_failures = update_manifest_from_results(manifest, group, results)
            converted += group_converted
            failures.extend(group_failures)
            write_manifest(out_dir, manifest)
            index += len(group)
    elif not dry_run:
        write_manifest(out_dir, manifest)

    return {
        "root": str(root_path),
        "out": str(out_dir),
        "candidate_count": len(candidates),
        "converted_count": converted,
        "skipped_count": skipped,
        "failure_count": len(failures),
        "failures": failures,
        "quarantined": quarantined,
        "quarantine_count": len(quarantined),
        "dry_run": dry_run,
        "manifest": str(out_dir / "converted" / "manifest.json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert legacy .doc files to staged .docx copies.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--include-misc", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = convert_docs(
            args.root,
            args.out,
            include_misc=args.include_misc,
            chunk_size=args.chunk_size,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    except ConvertDocError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
