#!/usr/bin/env python3
"""Record autofix outcome on a Sentry issue (note + optional resolve)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _config import sentry_api_base, sentry_org  # noqa: E402
from _sentry_issues import add_issue_comment  # noqa: E402


def resolve_issue_id(
    api: str,
    headers: dict[str, str],
    org: str,
    issue_ref: str,
) -> tuple[str, str | None]:
    """Return (numeric_issue_id, project_slug)."""
    if issue_ref.isdigit():
        detail = requests.get(
            f"{api}/issues/{issue_ref}/",
            headers=headers,
            timeout=30,
        )
        if detail.status_code != 200:
            return issue_ref, None
        project = detail.json().get("project", {})
        return issue_ref, project.get("slug")

    search = requests.get(
        f"{api}/organizations/{org}/issues/",
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
    parser.add_argument("--org", default=sentry_org())
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve issue when marker is deployed (skipped always resolves)",
    )
    args = parser.parse_args()

    token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    if not token or not args.org:
        print("tag_issue FAIL: set SENTRY_AUTH_TOKEN and SENTRY_ORG")
        return 1

    api = sentry_api_base()
    headers = {"Authorization": f"Bearer {token}"}
    issue_id, project_slug = resolve_issue_id(api, headers, args.org, args.issue_ref)
    if not issue_id:
        print("tag_issue FAIL: could not resolve issue")
        return 1

    note_text = f"[autofix:{args.marker}] Cursor autonomous fix pipeline"
    ok, status_code = add_issue_comment(
        api,
        headers,
        issue_id,
        note_text,
        args.org,
        project_slug or "",
    )
    if ok:
        print(f"tag_issue OK: comment added ({args.marker})")
    else:
        print(f"tag_issue WARN: comment failed {status_code}")

    # deployed: resolve with --resolve; skipped: always resolve (clear non-app noise)
    should_resolve = args.marker == "skipped" or (
        args.marker == "deployed" and args.resolve
    )
    if should_resolve:
        resolve_resp = requests.put(
            f"{api}/issues/{issue_id}/",
            headers=headers,
            json={"status": "resolved"},
            timeout=30,
        )
        if resolve_resp.status_code != 200:
            print(f"tag_issue WARN: resolve failed {resolve_resp.status_code}")
        else:
            print(f"tag_issue OK: issue resolved ({args.marker})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
