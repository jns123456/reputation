#!/usr/bin/env python3
"""Post-deploy health verification for Sentry autofix."""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 6
DEFAULT_DELAY = 20


def check_health(base_url: str, timeout: int) -> tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/health/"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return False, f"request failed: {exc}"
    if response.status_code != 200:
        return False, f"status {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return False, "non-JSON response"
    if payload.get("status") != "ok":
        return False, f"body status={payload.get('status')}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deploy health")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SITE_BASE_URL", ""),
        help="Site base URL (or set SITE_BASE_URL)",
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    base_url = args.base_url.strip()
    if not base_url:
        print("verify FAIL: set SITE_BASE_URL or pass --base-url")
        return 1

    for attempt in range(1, args.retries + 1):
        ok, detail = check_health(base_url, args.timeout)
        if ok:
            print(f"verify OK: {base_url}/health/ ({attempt}/{args.retries})")
            return 0
        print(f"verify attempt {attempt}/{args.retries} failed: {detail}")
        if attempt < args.retries:
            time.sleep(args.delay)

    print("verify FAIL: health check did not pass")
    return 1


if __name__ == "__main__":
    sys.exit(main())
