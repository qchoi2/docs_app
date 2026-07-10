"""Console helpers for Windows-safe UTF-8 output.

When stdout/stderr are piped or redirected on Windows, Python falls back to
the locale encoding (cp949), and characters like en-dashes or smart quotes
raise UnicodeEncodeError and kill the batch (implementation brief §4).
"""

import sys


def configure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 with replacement, best effort."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
