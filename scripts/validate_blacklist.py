#!/usr/bin/env python3
"""Validator for blacklist.txt

Checks:
- ignores blank lines and lines starting with '#'
- line is either a Telegram username (@username, 5-32 chars, letters/digits/underscore) or integer id (digits, optional leading '-')
- no duplicate entries (case-insensitive for usernames)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BLACKLIST = Path(__file__).resolve().parents[1] / "blacklist.txt"

USERNAME_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
ID_RE = re.compile(r"^-?\d+$")


def validate(lines):
    errors = []
    seen = set()
    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        # ignore empty or full-line comments
        if not line or line.startswith("#"):
            continue
        # allow inline comments after a value: "12345 # reason"
        main_part = line.split("#", 1)[0].strip()
        if not main_part:
            continue
        key = main_part.lower()
        if key in seen:
            errors.append((i, line, "duplicate"))
            continue
        seen.add(key)
        if USERNAME_RE.match(main_part):
            continue
        if ID_RE.match(main_part):
            continue
        errors.append((i, line, "invalid format"))
    return errors


def main(path: Path = BLACKLIST):
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2
    content = path.read_text(encoding="utf-8").splitlines()
    errs = validate(content)
    if errs:
        print("Validation failed:")
        for lineno, value, reason in errs:
            print(f"  Line {lineno}: '{value}' — {reason}")
        print(f"\nFound {len(errs)} problem(s). Fix them and re-run.")
        return 1
    print("OK — blacklist format looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
