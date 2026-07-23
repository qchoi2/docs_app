"""Merge the fixed 300/351 V4 remaining-rest review batches."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()

    payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in args.batch
    ]
    documents = [
        row for payload in payloads for row in payload.get("documents", [])
    ]
    keys = [str(row["file_key"]) for row in documents]
    if len(keys) != len(set(keys)):
        raise SystemExit("review batches overlap")

    candidates: dict[str, dict] = {}
    evidence: dict[str, list[dict]] = defaultdict(list)
    for payload in payloads:
        for row in payload.get("candidates", []):
            candidate_id = str(row["candidate_id"])
            candidates.setdefault(
                candidate_id,
                {key: value for key, value in row.items() if key not in {"document_count", "evidence"}},
            )
            evidence[candidate_id].extend(row.get("evidence", []))

    combined_candidates = []
    for candidate_id, row in candidates.items():
        rows = sorted(
            evidence[candidate_id],
            key=lambda value: (
                -int(value["legal_score"]),
                {False: 0, None: 1, True: 2}[value["is_draft"]],
                value["file_key"],
            ),
        )
        combined_candidates.append(
            {
                **row,
                "document_count": sum(
                    int(
                        next(
                            item["document_count"]
                            for item in payload["candidates"]
                            if item["candidate_id"] == candidate_id
                        )
                    )
                    for payload in payloads
                ),
                "evidence": rows[:20],
            }
        )

    first_selection = payloads[0]["selection"]
    output = {
        "review_version": "v4-remaining-rest-1",
        "batches": [
            {
                "path": str(path),
                "offset": payload["selection"]["batch_offset"],
                "count": payload["selection"]["batch_selected_count"],
            }
            for path, payload in zip(args.batch, payloads)
        ],
        "excluded_reviewed_count": payloads[0]["excluded_reviewed_count"],
        "selection": {
            "eligible_unreviewed_count": first_selection["eligible_unreviewed_count"],
            "prior_selected_count": first_selection["prior_selected_count"],
            "selected_count": len(documents),
            "selection_fraction": len(documents)
            / first_selection["eligible_unreviewed_count"],
            "population_by_stratum": first_selection["population_by_stratum"],
            "selected_by_stratum": first_selection["selected_by_stratum"],
        },
        "documents": documents,
        "candidate_count": len(combined_candidates),
        "new_candidate_count": sum(
            row.get("candidate_generation") == "remaining-rest"
            for row in combined_candidates
        ),
        "candidates": combined_candidates,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "documents": len(documents),
                "candidate_count": len(combined_candidates),
                "candidate_nonzero": sum(
                    int(row["document_count"]) > 0 for row in combined_candidates
                ),
                "new_candidate_nonzero": sum(
                    row.get("candidate_generation") == "remaining-rest"
                    and int(row["document_count"]) > 0
                    for row in combined_candidates
                ),
                "json": str(args.json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
