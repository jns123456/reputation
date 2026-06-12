"""Live event rooms — real-time-feel discussion around markets resolving soon.

A market enters "live mode" when it is still open but close to resolution (or
already in play). Live mode adds a polled comment stream and a countdown CTA
to the market detail page, plus a slow-mode comment throttle so high-velocity
rooms stay readable and spam-resistant.

No WebSockets: the stream is a small HTMX-polled partial backed by a short
server-side cache. The poll target is a dedicated container — never a
paginated feed (AGENTS.md §18).
"""

from django.core.cache import cache
from django.utils import timezone

LIVE_ROOM_WINDOW_HOURS = 12
LIVE_STREAM_LIMIT = 30
LIVE_STREAM_CACHE_SECONDS = 5
# Slow mode: one comment per user per market per this many seconds while live.
LIVE_SLOW_MODE_SECONDS = 15


def is_live_room(market):
    """True when the market should render in live mode."""
    if not market.is_open:
        return False
    if getattr(market, "is_in_play", False):
        return True
    close_date = market.close_date
    if not close_date:
        return False
    now = timezone.now()
    if close_date <= now:
        return False
    return (close_date - now).total_seconds() <= LIVE_ROOM_WINDOW_HOURS * 3600


def build_live_room_context(market):
    """Return live-room template context, or ``None`` when not live."""
    if not is_live_room(market):
        return None
    return {
        "close_at": market.close_date,
        "slow_mode_seconds": LIVE_SLOW_MODE_SECONDS,
    }


def get_live_stream_comments(market, *, limit=LIVE_STREAM_LIMIT):
    """Latest comments across all forecast threads of the market (cached)."""
    cache_key = f"live-stream:{market.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from comments.models import Comment

    comments = list(
        Comment.objects.filter(market=market)
        .select_related("user", "user__profile", "prediction")
        .order_by("-created_at")[:limit]
    )
    cache.set(cache_key, comments, LIVE_STREAM_CACHE_SECONDS)
    return comments


def enforce_live_slow_mode(*, user, market):
    """Raise ``ValueError`` when the user comments too fast in a live room.

    Cache-based throttle layered on top of the regular write guard. Fails open
    if the cache backend is unavailable (never block writes on cache errors).
    """
    if not is_live_room(market):
        return
    try:
        key = f"live-slowmode:{user.id}:{market.id}"
        if not cache.add(key, 1, LIVE_SLOW_MODE_SECONDS):
            from django.utils.translation import gettext as _

            raise ValueError(
                _("Slow mode is on for this live event — wait a few seconds between comments.")
            )
    except ValueError:
        raise
    except Exception:
        return
