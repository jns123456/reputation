"""User follow read queries."""

from accounts.models import UserFollow


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
