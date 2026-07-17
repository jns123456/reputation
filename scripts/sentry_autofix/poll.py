#!/usr/bin/env python3
"""Pick the next production error for autonomous autofix (cron automation entrypoint)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _config import sentry_api_base, sentry_org, sentry_project  # noqa: E402
from _sentry_issues import already_handled, issue_activity_text  # noqa: E402


def auth_headers() -> dict[str, str]:
    token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    if not token:
        raise SystemExit("poll FAIL: set SENTRY_AUTH_TOKEN")
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Sentry for next autofix candidate")
    parser.add_argument("--json", action="store_true", help="Print issue JSON on stdout")
    parser.add_argument("--org", default=sentry_org())
    parser.add_argument("--project", default=sentry_project())
    args = parser.parse_args()

    api = sentry_api_base()
    headers = auth_headers()
    query = os.environ.get(
        "SENTRY_AUTOFIX_QUERY",
        f"is:unresolved level:error environment:production project:{args.project}",
    )

    search = requests.get(
        f"{api}/organizations/{args.org}/issues/",
        headers=headers,
        params={"query": query, "sort": "freq", "limit": 10},
        timeout=30,
    )
    if search.status_code != 200:
        print(f"poll FAIL: search {search.status_code} {search.text[:200]}")
        return 1

    issues = search.json()
    if not issues:
        print("poll: no matching issues")
        return 2

    for row in issues:
        issue_id = str(row["id"])
        short_id = row.get("shortId", issue_id)
        project_slug = row.get("project", {}).get("slug") or args.project
        activity = issue_activity_text(
            api, headers, issue_id, args.org, project_slug
        )
        if already_handled(activity):
            continue

        payload = {
            "id": issue_id,
            "shortId": short_id,
            "title": row.get("title", ""),
            "permalink": row.get("permalink", ""),
            "project": project_slug,
            "org": args.org,
            "regionUrl": os.environ.get("SENTRY_REGION_URL", "https://us.sentry.io"),
        }
        if args.json:
            print(json.dumps(payload))
        else:
            print(f"poll OK: {short_id} — {payload['title']}")
        return 0

    print("poll: all candidates already handled by autofix")
    return 2


if __name__ == "__main__":
    sys.exit(main())
