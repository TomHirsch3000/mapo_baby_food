#!/usr/bin/env python3
"""
console.py — Make stdout safe for research metadata on Windows.

Paper titles routinely carry characters cp1252 cannot encode (U+2010 non-breaking
hyphen, en dashes, Greek letters in chemical names). Printing one of those on a
default Windows console raises UnicodeEncodeError and kills a long-running
import mid-way, so every CLI entry point calls init() first.
"""

import sys


def init(errors="replace"):
    """Switch stdout/stderr to UTF-8, degrading unencodable characters instead
    of raising. No-op on streams that do not support reconfigure (e.g. pipes
    already wrapped by a test harness)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors=errors)
        except (AttributeError, ValueError):
            pass
