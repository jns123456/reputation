#!/usr/bin/env python3
"""Rollback Heroku release and revert last commit on main."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback autofix deploy")
    parser.add_argument(
        "--app",
        default=os.environ.get("HEROKU_APP", "reputation-juan"),
        help="Heroku app name",
    )
    parser.add_argument(
        "--skip-git-revert",
        action="store_true",
        help="Only rollback Heroku, do not git revert",
    )
    args = parser.parse_args()

    heroku_result = run(
        ["heroku", "releases:rollback", "-a", args.app],
        check=False,
    )
    if heroku_result.returncode != 0:
        print("rollback WARN: heroku rollback failed:", heroku_result.stderr.strip())
    else:
        print("rollback OK: heroku release rolled back")

    if args.skip_git_revert:
        return 0 if heroku_result.returncode == 0 else 1

    revert_result = run(
        ["git", "revert", "--no-edit", "HEAD"],
        check=False,
    )
    if revert_result.returncode != 0:
        print("rollback WARN: git revert failed:", revert_result.stderr.strip())
        return 1

    push_result = run(["git", "push", "origin", "main"], check=False)
    if push_result.returncode != 0:
        print("rollback WARN: push origin failed:", push_result.stderr.strip())

    heroku_push = run(["git", "push", "heroku", "main"], check=False)
    if heroku_push.returncode != 0:
        print("rollback WARN: push heroku failed:", heroku_push.stderr.strip())

    print("rollback OK: git revert pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
