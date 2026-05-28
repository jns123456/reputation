"""@mention parsing for comments and forum posts."""

import re

# Usernames are matched conservatively: letters, digits and _ . - after an @.
# A preceding word char is rejected so we don't match emails like a@b.
_MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9_.\-]{0,149})")

# Cap mentions processed per piece of content to avoid notification spam abuse.
MAX_MENTIONS_PER_CONTENT = 10


def extract_mention_usernames(body):
    """Return up to MAX_MENTIONS_PER_CONTENT unique usernames mentioned in ``body``."""
    if not body:
        return []
    seen = []
    for raw in _MENTION_RE.findall(body):
        username = raw.rstrip(".-")
        if username and username not in seen:
            seen.append(username)
        if len(seen) >= MAX_MENTIONS_PER_CONTENT:
            break
    return seen
