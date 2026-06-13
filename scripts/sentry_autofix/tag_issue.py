#!/usr/bin/env python3
"""Record autofix outcome on a Sentry issue (note + optional resolve)."""

from __future__ import annotations

import argparse
import os
import sys

import requests

SENTRY_API = "https://sentry.io/api/0"


def resolve_issue_id(
    headers: dict[str, str],
    org: str,
    issue_ref: str,
) -> tuple[str, str | None]:
    """Return (numeric_issue_id, project_slug)."""
    if issue_ref.isdigit():
        detail = requests.get(
            f"{SENTRY_API}/issues/{issue_ref}/",
            headers=headers,
            timeout=30,
        )
        if detail.status_code != 200:
            return issue_ref, None
        project = detail.json().get("project", {})
        return issue_ref, project.get("slug")

    search = requests.get(
        f"{SENTRY_API}/organizations/{org}/issues/",
        headers=headers,
        params={"query": issue_ref, "limit": 1},
        timeout=30,
    )
    if search.status_code != 200 or not search.json():
        return "", None
    row = search.json()[0]
    return str(row["id"]), row.get("project", {}).get("slug")


def main() -> int:
    parser = argparse.ArgumentParser(description="Annotate Sentry issue after autofix")
    parser.add_argument("issue_ref", help="Numeric id or short id PROJECT-123")
    parser.add_argument(
        "marker",
        help="Marker e.g. deployed, skipped, failed",
    )
    parser.add_argument("--org", default=os.environ.get("SENTRY_ORG", ""))
    parser.add_argument("--resolve", action="store_true", help="Resolve issue if deployed")
    args = parser.parse_args()

    token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    if not token or not args.org:
        print("tag_issue FAIL: set SENTRY_AUTH_TOKEN and SENTRY_ORG")
        return 1

    headers = {"Authorization": f"Bearer {token}"}
    issue_id, project_slug = resolve_issue_id(headers, args.org, args.issue_ref)
    if not issue_id:
        print("tag_issue FAIL: could not resolve issue")
        return 1

    note_text = f"[autofix:{args.marker}] Cursor autonomous fix pipeline"
    if project_slug:
        note_resp = requests.post(
            f"{SENTRY_API}/projects/{args.org}/{project_slug}/issues/{issue_id}/notes/",
            headers=headers,
            json={"text": note_text},
            timeout=30,
        )
        if note_resp.status_code not in (200, 201):
            print(f"tag_issue WARN: note failed {note_resp.status_code}")
        else:
            print(f"tag_issue OK: note added ({args.marker})")

    if args.resolve and args.marker == "deployed":
        resolve_resp = requests.put(
            f"{SENTRY_API}/issues/{issue_id}/",
            headers=headers,
            json={"status": "resolved"},
            timeout=30,
        )
        if resolve_resp.status_code != 200:
            print(f"tag_issue WARN: resolve failed {resolve_resp.status_code}")
        else:
            print("tag_issue OK: issue resolved")

    return 0


if __name__ == "__main__":
    sys.exit(main())
