# Contract Search

Local Windows-first indexing and search tooling for M&A contract samples.

## Setup

Use a local Python environment. Python 3.10+ is recommended, while the code keeps Python 3.9 syntax compatibility.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Keep `cs_index/` on a local PC disk. The source contract root may be a local folder or a readable network drive, but `catalog.sqlite`, `txt/`, API cache, and logs should not live on a network filesystem.

## Indexing

Pilot a selected subset:

```powershell
python index_contracts.py --root C:\path\to\contracts --out C:\path\to\cs_index --file-list pilot_files.txt --batch-label pilot_001
```

For local test runs, if `root/` exists next to `index_contracts.py`, `--root` may be omitted:

```powershell
python index_contracts.py --out .\cs_index --sample 200 --sample-seed 42 --batch-label pilot_001
```

Expand to the full root using the same `--root` and `--out`:

```powershell
python index_contracts.py --root C:\path\to\contracts --out C:\path\to\cs_index --batch-label full_001
```

Force a generated index rebuild:

```powershell
python index_contracts.py --root C:\path\to\contracts --out C:\path\to\cs_index --full --batch-label full_001
```

Use `--dry-run` to create a change report without writing the database or text cache.

## Runtime Data

The YAML files in `data/` are runtime configuration. Update those files rather than changing code when term dictionaries, type rules, golden queries, API budget settings, or manual metadata overrides need adjustment.

## Search

Search the current index with JSON output:

```powershell
python search_contracts.py --out .\cs_index --kw 손해배상 --limit 10 --json
```

Repeat `--kw` for AND conditions. Term dictionary expansion is on by default; use `--expand strict`, `--expand broad`, or `--no-expand` to control it. Result sets are deduplicated by default, and `--show-duplicates` expands duplicate groups.

## Current Scope

Implemented so far: normalization, catalog schema creation, DOCX/PDF indexing, txt cache generation, FTS population, incremental indexing, pilot/full options, index reports, and the FTS-backed search CLI.

Next Phase 1A work: stats CLI, file inspection helpers, evaluation, and fuller README/FAQ coverage.
