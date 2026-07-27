from cluster_v4_candidates import cluster_rows, normalize_candidate_text


def test_normalize_candidate_text_collapses_case_and_punctuation():
    assert normalize_candidate_text("No  Claim--Pending.") == "no claim pending"


def test_cluster_rows_ranks_repeated_documents_and_keeps_coordinates():
    rows = [
        {
            "candidate_id": candidate_id,
            "family": "REM",
            "nearest_taxonomy_id": "REM.NO_DOUBLE_RECOVERY",
            "verbatim": text,
            "evidence_file_key": file_key,
            "loc_start": candidate_id,
            "loc_end": candidate_id,
            "ctype": "SPA",
            "lang": "영문",
            "path": f"{file_key}.docx",
        }
        for candidate_id, file_key, text in (
            (1, "a", "No double recovery."),
            (2, "b", "No double recovery!"),
            (3, "b", "No double recovery."),
            (4, "c", "A singleton."),
        )
    ]

    clusters = cluster_rows(rows, min_count=2)

    assert len(clusters) == 1
    assert clusters[0]["candidate_count"] == 3
    assert clusters[0]["document_count"] == 2
    assert clusters[0]["candidate_ids"] == [1, 2, 3]
    assert clusters[0]["evidence"][0]["loc_start"] == 1
