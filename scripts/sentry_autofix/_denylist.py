"""Shared denylist matching for Sentry autofix scripts."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DENYLIST = ROOT / "config" / "autofix_denylist.txt"


def load_patterns(path: Path | None = None) -> list[str]:
    denylist = path or DEFAULT_DENYLIST
    patterns: list[str] = []
    for line in denylist.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped.replace("\\", "/"))
    return patterns


def path_matches(patterns: list[str], file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lstrip("/")
    for pattern in patterns:
        if fnmatch(normalized, pattern) or normalized == pattern.rstrip("/"):
            return True
        if pattern.endswith("/") and normalized.startswith(pattern):
            return True
    return False


def forbidden_files(files: list[str], patterns: list[str] | None = None) -> list[str]:
    pats = patterns or load_patterns()
    return [f for f in files if path_matches(pats, f)]
