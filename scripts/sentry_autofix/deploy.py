#!/usr/bin/env python3
"""Push main to GitHub and Heroku for autofix deploy."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def ensure_heroku_remote(app: str) -> None:
    """Add git remote `heroku` when HEROKU_API_KEY is set and remote is missing."""
    api_key = os.environ.get("HEROKU_API_KEY", "")
    if not api_key:
        return
    check = subprocess.run(
        ["git", "remote", "get-url", "heroku"],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return
    remote_url = f"https://heroku:{api_key}@git.heroku.com/{app}.git"
    subprocess.run(["git", "remote", "add", "heroku", remote_url], check=True)
    print(f"deploy: added heroku remote for {app}")


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    result = subprocess.run(cmd, text=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy autofix to origin + Heroku")
    parser.add_argument(
        "--app",
        default=os.environ.get("HEROKU_APP", "reputation-juan"),
        help="Heroku app (for logging; uses git remote heroku)",
    )
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    code = run(["git", "push", "origin", args.branch])
    if code != 0:
        print("deploy FAIL: origin push")
        return code

    try:
        ensure_heroku_remote(args.app)
    except subprocess.CalledProcessError as exc:
        print(f"deploy FAIL: could not configure heroku remote ({exc})")
        return 1

    code = run(["git", "push", "heroku", f"{args.branch}:main"])
    if code != 0:
        print("deploy FAIL: heroku push")
        return code

    print(f"deploy OK: pushed to origin and heroku ({args.app})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
