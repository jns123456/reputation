"""User follow read queries."""

from accounts.models import MarketWatch, TopicFollow, UserFollow


def get_followed_topic_slugs(user):
    if not user or not user.is_authenticated:
        return []
    return list(TopicFollow.objects.filter(user=user).values_list("category_slug", flat=True))


def is_following_topic(*, user, category_slug):
    if not user or not user.is_authenticated:
        return False
    return TopicFollow.objects.filter(user=user, category_slug=category_slug).exists()


def get_watched_market_ids(user):
    if not user or not user.is_authenticated:
        return []
    return list(MarketWatch.objects.filter(user=user).values_list("market_id", flat=True))


def is_watching_market(*, user, market):
    if not user or not user.is_authenticated:
        return False
    return MarketWatch.objects.filter(user=user, market=market).exists()


def is_following(*, follower, following_user):
    if not follower or not follower.is_authenticated:
        return False
    return UserFollow.objects.filter(
        follower=follower,
        following=following_user,
    ).exists()


def get_follower_count(user):
    return UserFollow.objects.filter(following=user).count()


def get_following_count(user):
    return UserFollow.objects.filter(follower=user).count()


def are_mutual_followers(user_a, user_b):
    if not user_a or not user_b:
        return False
    if user_a.id == user_b.id:
        return False
    return is_following(follower=user_a, following_user=user_b) and is_following(
        follower=user_b,
        following_user=user_a,
    )


def get_mutual_followers(user):
    """Users who follow each other with the given user."""
    if not user or not user.is_authenticated:
        from django.contrib.auth import get_user_model

        return get_user_model().objects.none()

    following_ids = UserFollow.objects.filter(follower=user).values_list(
        "following_id",
        flat=True,
    )
    follower_ids = UserFollow.objects.filter(following=user).values_list(
        "follower_id",
        flat=True,
    )
    mutual_ids = set(following_ids) & set(follower_ids)
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.filter(id__in=mutual_ids).select_related("profile").order_by(
        "username",
    )


def get_follower_ids(user):
    return UserFollow.objects.filter(following=user).values_list("follower_id", flat=True)


def get_following_ids(user):
    if not user or not user.is_authenticated:
        return UserFollow.objects.none().values_list("following_id", flat=True)
    return UserFollow.objects.filter(follower=user).values_list("following_id", flat=True)


def get_followers(user, *, limit=100):
    """Users who follow the given user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not user:
        return User.objects.none()
    return (
        User.objects.filter(is_active=True, following_relations__following=user)
        .select_related("profile")
        .order_by("-following_relations__created_at")
        .distinct()[:limit]
    )


def get_following_users(user, *, limit=100):
    """Users the given user follows."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not user:
        return User.objects.none()
    return (
        User.objects.filter(is_active=True, follower_relations__follower=user)
        .select_related("profile")
        .order_by("-follower_relations__created_at")
        .distinct()[:limit]
    )
