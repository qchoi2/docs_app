def test_scaffold_files_exist():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    assert (root / "README.md").exists()
    assert (root / "requirements.txt").exists()
    assert (root / "CLAUDE.md").exists()
    assert (root / "lib").exists()
    assert (root / "data").exists()
    assert (root / "tests").exists()


def test_runtime_yaml_files_are_placed_in_data():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    for filename in [
        "term_dict.yaml",
        "type_rules.yaml",
        "golden_queries.yaml",
        "api_budget.yaml",
        "manual_overrides.yaml",
    ]:
        assert (root / "data" / filename).exists()
