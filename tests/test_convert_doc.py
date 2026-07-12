import json
import os
import subprocess
from pathlib import Path

import pytest
from docx import Document

import convert_doc


def test_build_candidates_skips_existing_manifest_entry(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    source = root / "legacy.doc"
    source.write_bytes(bytes.fromhex("D0CF11E0") + b"legacy")
    source_sha256 = convert_doc.sha256_hex(source.read_bytes())
    target = out / "converted" / ("%s.docx" % source_sha256)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"docx")
    manifest = {
        "schema_version": 1,
        "items": {
            "legacy.doc": {
                "status": "ok",
                "source_sha256": source_sha256,
                "converted_docx": "converted/%s.docx" % source_sha256,
            }
        },
    }

    candidates, rejected, skipped = convert_doc.build_candidates(root, out, manifest=manifest)

    assert candidates == []
    assert rejected == []
    assert skipped == 1


def test_convert_docs_updates_manifest_with_mock_converter(tmp_path, monkeypatch):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    source = root / "legacy.doc"
    source.write_bytes(bytes.fromhex("D0CF11E0") + b"legacy")

    def fake_converter(jobs, *, worker_path, converted_dir, timeout):
        results = []
        for job in jobs:
            job.target_path.parent.mkdir(parents=True, exist_ok=True)
            job.target_path.write_bytes(b"docx")
            results.append(
                {
                    "source": str(job.path.resolve()),
                    "target": str(job.target_path.resolve()),
                    "status": "ok",
                    "error_reason": None,
                    "converter_version": "mock-word",
                }
            )
        return results

    monkeypatch.setattr(convert_doc, "run_powershell_converter", fake_converter)

    worker = tmp_path / "mock.ps1"
    worker.write_text("# mock", encoding="utf-8")

    result = convert_doc.convert_docs(root, out, worker_path=worker)

    assert result["converted_count"] == 1
    assert result["failure_count"] == 0
    manifest = json.loads((out / "converted" / "manifest.json").read_text(encoding="utf-8"))
    item = manifest["items"]["legacy.doc"]
    assert item["status"] == "ok"
    assert item["converter_version"] == "mock-word"
    assert (out / item["converted_docx"]).exists()


def test_non_ole_doc_is_recorded_as_unsupported(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    (root / "fake.doc").write_bytes(b"not-ole")

    result = convert_doc.convert_docs(root, out)

    assert result["converted_count"] == 0
    assert result["failure_count"] == 1
    manifest = json.loads((out / "converted" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["items"]["fake.doc"]["status"] == "unsupported"
    assert manifest["items"]["fake.doc"]["error_reason"] == "not_ole2_unknown"


def test_rtf_and_zip_doc_extensions_are_recorded_with_specific_reasons(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    (root / "fake_rtf.doc").write_bytes(b"{\\rtf1 text")
    (root / "fake_zip.doc").write_bytes(b"PK\x03\x04")

    result = convert_doc.convert_docs(root, out)

    assert result["converted_count"] == 0
    assert result["failure_count"] == 2
    manifest = json.loads((out / "converted" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["items"]["fake_rtf.doc"]["error_reason"] == "not_ole2_rtf"
    assert manifest["items"]["fake_zip.doc"]["error_reason"] == "not_ole2_zip"


def test_chunk_failure_quarantines_one_file_and_continues(tmp_path, monkeypatch):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    for name in ("bad.doc", "good.doc"):
        (root / name).write_bytes(bytes.fromhex("D0CF11E0") + name.encode("ascii"))

    calls = []

    def fake_converter(jobs, *, worker_path, converted_dir, timeout):
        calls.append([job.rel_path for job in jobs])
        if calls == [["bad.doc", "good.doc"]]:
            raise subprocess.TimeoutExpired(cmd="powershell", timeout=1)
        results = []
        for job in jobs:
            job.target_path.parent.mkdir(parents=True, exist_ok=True)
            job.target_path.write_bytes(b"docx")
            results.append(
                {
                    "source": str(job.path.resolve()),
                    "target": str(job.target_path.resolve()),
                    "status": "ok",
                    "error_reason": None,
                    "converter_version": "mock-word",
                }
            )
        return results

    monkeypatch.setattr(convert_doc, "run_powershell_converter", fake_converter)
    worker = tmp_path / "mock.ps1"
    worker.write_text("# mock", encoding="utf-8")

    result = convert_doc.convert_docs(root, out, chunk_size=2, worker_path=worker)

    assert result["converted_count"] == 1
    assert result["quarantine_count"] == 1
    assert result["quarantined"][0]["path"] == "bad.doc"
    assert calls == [["bad.doc", "good.doc"], ["good.doc"]]
    manifest = json.loads((out / "converted" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["items"]["bad.doc"]["status"] == "error"
    assert manifest["items"]["good.doc"]["status"] == "ok"


def test_word_unavailable_aborts_without_manifest(tmp_path, monkeypatch):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    (root / "legacy.doc").write_bytes(bytes.fromhex("D0CF11E0") + b"legacy")

    def fake_converter(jobs, *, worker_path, converted_dir, timeout):
        raise convert_doc.WordUnavailableError("Microsoft Word is unavailable")

    monkeypatch.setattr(convert_doc, "run_powershell_converter", fake_converter)
    worker = tmp_path / "mock.ps1"
    worker.write_text("# mock", encoding="utf-8")

    with pytest.raises(convert_doc.WordUnavailableError):
        convert_doc.convert_docs(root, out, worker_path=worker)

    assert not (out / "converted" / "manifest.json").exists()


def test_dry_run_does_not_write_manifest(tmp_path):
    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    (root / "legacy.doc").write_bytes(bytes.fromhex("D0CF11E0") + b"legacy")

    result = convert_doc.convert_docs(root, out, dry_run=True)

    assert result["candidate_count"] == 1
    assert result["converted_count"] == 0
    assert not (out / "converted" / "manifest.json").exists()


def test_real_word_conversion_when_sample_doc_is_provided(tmp_path):
    sample = os.environ.get("CONVERT_DOC_INTEGRATION_DOC")
    if not sample:
        pytest.skip("set CONVERT_DOC_INTEGRATION_DOC to run the Word COM integration test")
    sample_path = Path(sample)
    if not sample_path.exists():
        pytest.skip("CONVERT_DOC_INTEGRATION_DOC does not exist")

    root = tmp_path / "contracts"
    out = tmp_path / "cs_index"
    root.mkdir()
    source = root / sample_path.name
    source.write_bytes(sample_path.read_bytes())

    result = convert_doc.convert_docs(root, out, chunk_size=1, timeout=120)

    assert result["converted_count"] == 1
    manifest = json.loads((out / "converted" / "manifest.json").read_text(encoding="utf-8"))
    item = next(iter(manifest["items"].values()))
    converted = out / item["converted_docx"]
    assert converted.exists()
    document = Document(converted)
    assert "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
