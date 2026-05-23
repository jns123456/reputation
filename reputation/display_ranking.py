"""Display ordering for forecasts and threaded comments."""

DISPLAY_RANK_ORM_FIELDS = (
    "-popularity_score",
    "-user__profile__reputation_score",
    "-user__profile__popularity_score",
    "-created_at",
)


def display_rank_key(*, popularity_score, created_at, user):
    profile = getattr(user, "profile", None)
    reputation = float(getattr(profile, "reputation_score", 0) or 0)
    user_popularity = float(getattr(profile, "popularity_score", 0) or 0)
    timestamp = created_at.timestamp() if created_at is not None else 0.0
    return (
        -int(popularity_score),
        -reputation,
        -user_popularity,
        -timestamp,
    )


def display_rank_key_for_content(content):
    return display_rank_key(
        popularity_score=content.popularity_score,
        created_at=content.created_at,
        user=content.user,
    )
