#!/usr/bin/env python3
"""Validate staged/working diff before autofix commit (denylist, size, secrets)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _denylist import forbidden_files, load_patterns  # noqa: E402

MAX_FILES = 8
MAX_LINES = 200
SECRET_PATTERNS = [
    re.compile(r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.I),
    re.compile(r"re_[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
]


def git_lines(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def changed_files(staged: bool) -> list[str]:
    flag = "--cached" if staged else ""
    out = git_lines(["diff", "--name-only", flag] if flag else ["diff", "--name-only"])
    names = [line.strip() for line in out.splitlines() if line.strip()]
    if staged:
        return names
    staged_names = set(git_lines(["diff", "--name-only", "--cached"]).splitlines())
    unstaged = [n.strip() for n in git_lines(["diff", "--name-only"]).splitlines() if n.strip()]
    return sorted(set(staged_names) | set(unstaged))


def diff_stat_lines(staged: bool) -> int:
    args = ["diff", "--stat", "--cached"] if staged else ["diff", "--stat"]
    out = git_lines(args)
    total = 0
    for line in out.splitlines():
        if "|" not in line:
            continue
        tail = line.rsplit("|", 1)[-1].strip()
        if "+" in tail:
            parts = tail.split()
            for part in parts:
                if part.endswith("+") and part[:-1].isdigit():
                    total += int(part[:-1])
    return total


def scan_secrets(staged: bool) -> list[str]:
    args = ["diff", "--cached"] if staged else ["diff"]
    diff = git_lines(args)
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(diff):
            hits.append(pattern.pattern)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Autofix preflight checks")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Only check staged changes (default: all working tree changes)",
    )
    args = parser.parse_args()

    files = changed_files(staged=args.staged)
    if not files:
        print("preflight: no changes to validate")
        return 0

    patterns = load_patterns()
    blocked = forbidden_files(files, patterns)
    if blocked:
        print("preflight FAIL: denylisted paths:", ", ".join(blocked))
        return 1

    if len(files) > MAX_FILES:
        print(f"preflight FAIL: too many files ({len(files)} > {MAX_FILES})")
        return 1

    line_count = diff_stat_lines(staged=args.staged)
    if line_count > MAX_LINES:
        print(f"preflight FAIL: diff too large ({line_count} lines > {MAX_LINES})")
        return 1

    secrets = scan_secrets(staged=args.staged)
    if secrets:
        print("preflight FAIL: possible secrets in diff")
        return 1

    print(
        f"preflight OK: {len(files)} file(s), ~{line_count} line(s) changed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
