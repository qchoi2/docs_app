# A-2 Sample Quality Loop v2

Date: 2026-07-12

Scope: Appendix D/C follow-up for the same 10 SPA sample documents used in
`A2_SAMPLE_QUALITY_20260711.md`. No paid API was called. The existing reviewed
A-2 clause maps in `doc_meta` were replayed through the strengthened
`enrich_contracts.py` v2 harness to verify schema migration, re-extraction
selection, and validation behavior deterministically.

## Results

| Check | v1 Gate | v2 Gate |
|---|---:|---:|
| `meta_schema_version` accepted by harness | 1 | 2 |
| v1 `doc_meta` selected for re-extraction | Not applicable | Confirmed |
| SPA sample documents processed | 10 | 10 |
| Processing errors after v2 normalization | 0 | 0 |
| Incremental skip after v2 write | Confirmed for sample file | Confirmed |
| Indemnity documents with required subfields | Not enforced | 10/10 |
| Indemnity subfields explicitly `not confirmed` | Not enforced | 24/40 |
| Non-compete `present=true` count | 1/10 | 1/10 |
| MAC `present=true` count | 9/10 | 9/10 |
| Top-level `confidence=low` count | 0/10 | 0/10 |

## What Changed

- `META_SCHEMA_VERSION` is now 2, so v1 rows are treated as re-extraction
  targets instead of being skipped.
- Any evaluated `clause_map` tag must contain `present: true` or
  `present: false`. Missing or null `present` now fails validation.
- `손해배상` with `present=true` must include `cap_verbatim`,
  `basket_verbatim`, `de_minimis_verbatim`, and `survival_verbatim`.
  Unknown values are explicit as `"not confirmed"`.
- Location validation remains strict: `loc_start` and `loc_end` must be
  positive integers or null, and reversed ranges fail.

## Notes

This pass confirms the v2 harness and schema gate, not a new semantic extraction
model comparison. The underlying reviewed A-2 clause decisions were preserved.
The main quality gain is that future extraction outputs cannot silently omit
evaluated `present` values or indemnity subfields.

## Verification

- `python enrich_contracts.py --out cs_index --limit 10` -> 10 processed, 0 errors
- `python enrich_contracts.py --out cs_index --file-key 2a08ef8b2699dca5 --dry-run` -> 0 candidates
- `python -m pytest -q tests/test_enrich_contracts.py` -> 10 passed
- `python -m pytest -q tests/test_read_contract.py tests/test_search_contracts.py tests/test_eval_search.py` -> 30 passed
- `python -m pytest -q` -> 116 passed
