"""Template context for challenge invitations in navigation."""

from accounts.nav_cache import get_cached_pending_challenge_invites_count


def challenge_context(request):
    if not request.user.is_authenticated:
        return {
            "pending_challenge_invites_count": 0,
        }

    return {
        "pending_challenge_invites_count": get_cached_pending_challenge_invites_count(
            user=request.user,
        ),
    }
