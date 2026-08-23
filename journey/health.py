"""Best-effort operational health checks (PAT expiry, etc).

These are advisory only and must never break the main journaling flow: any
network hiccup, unexpected response shape, or missing config here is
swallowed and treated as "nothing to report," not an error.
"""
from __future__ import annotations

import datetime
import urllib.request

from . import config

PAT_WARNING_WINDOW_DAYS = 7


def check_pat_expiry() -> str | None:
    """Returns a warning message if ENTRIES_REPO_TOKEN expires soon, else None.

    Uses GitHub's own 'github-authentication-token-expiration' response
    header on an authenticated API call, rather than guessing from whenever
    the token might have been created -- so this reflects whatever expiry
    the user actually set (or later changed), authoritatively.
    """
    if not config.ENTRIES_REPO_TOKEN or not config.ENTRIES_REPO:
        return None  # not available outside the GitHub Actions run

    try:
        # Request construction is inside the try too, not just urlopen() --
        # this function's whole contract is "advisory, never raise", so the
        # broad except below is intentional, not laziness: anything going
        # wrong here should be a skipped check, never a crashed run.
        req = urllib.request.Request(
            f"https://api.github.com/repos/{config.ENTRIES_REPO}",
            headers={
                "Authorization": f"Bearer {config.ENTRIES_REPO_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            expiration_header = resp.headers.get("github-authentication-token-expiration")
    except Exception:
        return None

    if not expiration_header:
        return None  # token has no expiration set, or GitHub changed the header

    try:
        expires_at = datetime.datetime.strptime(expiration_header, "%Y-%m-%d %H:%M:%S %Z").date()
    except ValueError:
        return None  # didn't match the expected format -- don't guess, just skip

    days_left = (expires_at - datetime.date.today()).days
    if 0 <= days_left <= PAT_WARNING_WINDOW_DAYS:
        return (
            f"journey status: your GitHub token (ENTRIES_REPO_TOKEN) expires in "
            f"{days_left} day(s), on {expires_at.isoformat()}. Create a new "
            f"fine-grained PAT scoped to the entries repo and update the "
            f"ENTRIES_REPO_TOKEN secret in the journey repo before then, or "
            f"future replies won't be able to be saved."
        )
    return None
