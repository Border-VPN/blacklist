#!/usr/bin/env python3
"""Merge blacklist from an external file into local `blacklist.txt`.

Behavior:
- Reads local target (default: `blacklist.txt`) and external source file
- Normalizes entries (ignores empty lines and comments; extracts main value before any `#`)
- Username entries normalized to lowercase (usernames are case-insensitive)
- Removes duplicates (case-insensitive for usernames)
- Keeps top header comments from existing file
- Sorts entries for deterministic output
- Writes file only if changed and exits with 0

Usage:
  python scripts/merge_blacklist.py --source upstream/blacklist.txt

This script is intended to be used by CI (GitHub Actions) scheduled job.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Path to source blacklist file")
    p.add_argument(
        "--target", default="blacklist.txt", help="Target local blacklist file"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Do not write changes, just report"
    )
    return p.parse_args()


def split_main_and_comment(line: str) -> Tuple[str, str]:
    """Return (main, comment).

    Preserves inline comments: everything after the first '#' (stripped).
    If no comment, returns empty string for comment.
    """
    if "#" in line:
        main, comment = line.split("#", 1)
        return main.strip(), comment.strip()
    return line.strip(), ""


def read_file(path: Path) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Return (header_comments, entries)

    entries are tuples (main, comment)
    """
    if not path.exists():
        return [], []
    lines = path.read_text(encoding="utf-8").splitlines()
    header = []
    entries: List[Tuple[str, str]] = []
    header_done = False
    for raw in lines:
        s = raw.rstrip()
        if not header_done and (not s or s.startswith("#")):
            header.append(s)
            continue
        header_done = True
        main, comment = split_main_and_comment(s)
        if not main:
            continue
        entries.append((main, comment))
    return header, entries


def normalize_entry(entry: str) -> str:
    # usernames -> lowercase; numeric ids unchanged
    if entry.startswith("@"):
        return entry.strip().lower()
    return entry.strip()


def merge_entries(
    old: List[Tuple[str, str]], new: List[Tuple[str, str]]
) -> List[Tuple[str, str]]:
    """Merge entries preserving inline comments.

    For duplicates, keep the comment from the first occurrence (old before new).
    """
    seen = set()
    merged = []
    for e_main, e_comment in old + new:
        norm = normalize_entry(e_main)
        if norm in seen:
            continue
        seen.add(norm)
        # store normalized main (usernames lowercased) and comment
        main_out = normalize_entry(e_main)
        comment_out = e_comment
        merged.append((main_out, comment_out))

    # deterministic: sort numerically for pure digits, otherwise lexicographically
    def sort_key(item: Tuple[str, str]):
        x = item[0]
        if x.lstrip("-").isdigit():
            return (0, int(x))
        return (1, x.lower())

    merged_sorted = sorted(merged, key=sort_key)
    return merged_sorted


def build_contents(header: List[str], entries: List[Tuple[str, str]]) -> str:
    # Ensure header contains a machine-friendly generated line
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gen_line = f"# Merged on {timestamp}"
    # remove any existing generated lines starting with '# Merged on '
    header_filtered = [h for h in header if not h.startswith("# Merged on ")]
    header_out = header_filtered + [gen_line]

    def render_entry(item: Tuple[str, str]) -> str:
        main, comment = item
        if comment:
            return f"{main}  # {comment}"
        return main

    body = "\n".join(render_entry(entry) for entry in entries)
    parts = []
    if header_out:
        parts.append("\n".join(header_out))
    if body:
        parts.append(body)
    return "\n\n".join(parts) + "\n"


def main():
    args = parse_args()
    src = Path(args.source)
    tgt = Path(args.target)

    if not src.exists():
        print(f"ERROR: source file '{src}' not found", file=sys.stderr)
        return 2

    header_old, entries_old = read_file(tgt)
    _, entries_new = read_file(src)

    merged = merge_entries(entries_old, entries_new)

    new_contents = build_contents(header_old, merged)

    old_contents = tgt.read_text(encoding="utf-8") if tgt.exists() else ""

    if old_contents == new_contents:
        print("No changes to blacklist.")
        return 0

    print(f"Updating '{tgt}' — {len(merged)} entries (was {len(entries_old)}).")
    if args.dry_run:
        print(new_contents)
        return 0

    tgt.write_text(new_contents, encoding="utf-8")
    print("Wrote updated blacklist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
