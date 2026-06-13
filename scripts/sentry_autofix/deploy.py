#!/usr/bin/env python3
"""Push main to GitHub and Heroku for autofix deploy."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


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

    code = run(["git", "push", "heroku", f"{args.branch}:main"])
    if code != 0:
        print("deploy FAIL: heroku push")
        return code

    print(f"deploy OK: pushed to origin and heroku ({args.app})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
