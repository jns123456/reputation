"""User discovery search with relevance ranking and fuzzy matching."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from django.db import connection
from django.db.models import Q

from accounts.models import User

EXACT_MATCH_SCORE = 50.0
SIMILAR_MATCH_SCORE = 15.0


@dataclass(frozen=True)
class UserSearchResults:
    exact: tuple[User, ...]
    similar: tuple[User, ...]

    @property
    def users(self) -> list[User]:
        return list(self.exact) + list(self.similar)

    @property
    def exact_users(self) -> list[User]:
        return list(self.exact)

    @property
    def similar_users(self) -> list[User]:
        return list(self.similar)


def normalize_user_search_query(query: str) -> str:
    cleaned = (query or "").strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:].strip()
    return cleaned


def _search_tokens(cleaned: str) -> list[str]:
    return [token for token in cleaned.split() if token]


def _minimum_query_length(cleaned: str) -> bool:
    if not cleaned:
        return False
    if "@" in cleaned:
        return len(cleaned) >= 3
    return len(cleaned) >= 2


def _visible_users():
    return (
        User.objects.filter(is_active=True, hide_from_user_directory=False)
        .exclude(identity_mode=User.IdentityMode.ANONYMOUS)
        .select_related("profile")
    )


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def _score_user(user: User, *, cleaned: str, tokens: list[str]) -> float:
    query = cleaned.lower()
    username = user.username.lower()
    display_name = (user.display_name or "").lower()
    email = (user.email or "").lower()
    bio = (user.bio or "").lower()
    score = 0.0

    if username == query:
        score += 200
    if display_name == query:
        score += 180
    if email == query:
        score += 170

    if username.startswith(query):
        score += 80
    if display_name.startswith(query):
        score += 70
    if email.startswith(query):
        score += 65

    if query in username:
        score += 35
    if query in display_name:
        score += 30
    if query in email:
        score += 28
    if query in bio:
        score += 10

    for token in tokens:
        token_lower = token.lower()
        if token_lower in username:
            score += 15
        if token_lower in display_name:
            score += 12
        if token_lower in email:
            score += 10
        if token_lower in bio:
            score += 4

    for field in (username, display_name, email):
        ratio = _text_similarity(cleaned, field)
        if ratio >= 0.55:
            score += ratio * 40

    profile = getattr(user, "profile", None)
    if profile is not None:
        score += min(profile.reputation_score, 50) * 0.1
        score += min(profile.popularity_score, 50) * 0.05

    return score


def _contains_filter(*, cleaned: str, tokens: list[str]) -> Q:
    if not tokens:
        tokens = [cleaned]

    combined = Q()
    for token in tokens:
        token_match = (
            Q(username__icontains=token)
            | Q(display_name__icontains=token)
            | Q(email__icontains=token)
            | Q(bio__icontains=token)
        )
        combined &= token_match
    return combined


def _postgres_fuzzy_candidates(*, cleaned: str, limit: int):
    from django.contrib.postgres.search import TrigramSimilarity
    from django.db.models.functions import Greatest

    similarity = Greatest(
        TrigramSimilarity("username", cleaned),
        TrigramSimilarity("display_name", cleaned),
        TrigramSimilarity("email", cleaned),
        TrigramSimilarity("bio", cleaned),
    )
    return (
        _visible_users()
        .annotate(search_similarity=similarity)
        .filter(search_similarity__gte=0.18)
        .order_by("-search_similarity")[: limit * 4]
    )


def _sqlite_fuzzy_candidates(*, cleaned: str, limit: int):
    if len(cleaned) < 3:
        return User.objects.none()

    prefix = cleaned[:2]
    return _visible_users().filter(username__istartswith=prefix).order_by("username")[: limit * 6]


def _collect_candidates(*, cleaned: str, tokens: list[str], limit: int) -> dict[int, User]:
    candidates: dict[int, User] = {}

    for user in _visible_users().filter(_contains_filter(cleaned=cleaned, tokens=tokens))[: limit * 4]:
        candidates[user.pk] = user

    if len(candidates) < limit:
        fuzzy_qs = (
            _postgres_fuzzy_candidates(cleaned=cleaned, limit=limit)
            if connection.vendor == "postgresql"
            else _sqlite_fuzzy_candidates(cleaned=cleaned, limit=limit)
        )
        for user in fuzzy_qs:
            candidates.setdefault(user.pk, user)

    return candidates


def is_valid_user_search_query(query: str) -> bool:
    return _minimum_query_length(normalize_user_search_query(query))


def search_user_matches(*, query="", limit=20) -> UserSearchResults:
    """Rank users by name, username, email, bio, and fuzzy similarity."""
    cleaned = normalize_user_search_query(query)
    if not _minimum_query_length(cleaned):
        return UserSearchResults(exact=(), similar=())

    tokens = _search_tokens(cleaned)
    candidates = _collect_candidates(cleaned=cleaned, tokens=tokens, limit=limit)

    scored: list[tuple[float, User]] = []
    for user in candidates.values():
        score = _score_user(user, cleaned=cleaned, tokens=tokens)
        if score >= SIMILAR_MATCH_SCORE:
            scored.append((score, user))

    scored.sort(key=lambda item: (-item[0], item[1].username.lower()))
    ranked = [user for _, user in scored[:limit]]

    exact: list[User] = []
    similar: list[User] = []
    for user in ranked:
        score = _score_user(user, cleaned=cleaned, tokens=tokens)
        if score >= EXACT_MATCH_SCORE:
            exact.append(user)
        else:
            similar.append(user)

    return UserSearchResults(exact=tuple(exact), similar=tuple(similar))


BROWSABLE_USERS_PAGE_SIZE = 50


def get_browsable_users(*, limit=BROWSABLE_USERS_PAGE_SIZE, offset=0):
    """Active, non-anonymous users for the platform directory."""
    return list(
        _visible_users()
        .order_by(
            "-profile__reputation_score",
            "-profile__popularity_score",
            "username",
        )[offset : offset + limit]
    )


def count_browsable_users():
    return _visible_users().count()


def search_users(*, query="", limit=20):
    """Backward-compatible queryset-like helper returning ranked users."""
    return search_user_matches(query=query, limit=limit).users
