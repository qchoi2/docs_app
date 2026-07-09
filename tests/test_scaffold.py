def test_scaffold_files_exist():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    assert (root / "README.md").exists()
    assert (root / "requirements.txt").exists()
    assert (root / "CLAUDE.md").exists()
    assert (root / "lib").exists()
    assert (root / "data").exists()
    assert (root / "tests").exists()
