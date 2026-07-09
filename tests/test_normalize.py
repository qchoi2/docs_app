from lib.normalize import normalize


def test_normalize_handles_unicode_and_whitespace():
    raw = "Cafe\u0301\u00a0\u200bworld"
    assert normalize(raw) == "Café world"


def test_normalize_unifies_hyphens_and_quotes():
    raw = "earn\u2011out \u201cearn-out\u201d \u2018test\u2019"
    assert normalize(raw) == 'earn-out "earn-out" \'test\''


def test_normalize_collapses_repeated_whitespace():
    raw = "  first\t\tsecond   third\n\nfourth  "
    assert normalize(raw) == "first second third fourth"
