"""Template context for challenge invitations in navigation."""


def challenge_context(request):
    if not request.user.is_authenticated:
        return {
            "pending_challenge_invites_count": 0,
        }

    from challenges.selectors import get_pending_challenge_invitations_count

    return {
        "pending_challenge_invites_count": get_pending_challenge_invitations_count(
            request.user,
        ),
    }
