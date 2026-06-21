"""Share-sheet copy for public forecast cards (open vs resolved)."""

from __future__ import annotations

from django.utils.translation import gettext as _

from predictions.models import Prediction


def _truncate_title(title: str | None, *, max_len: int = 50) -> str:
    cleaned = (title or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def get_forecast_share_copy(prediction: Prediction) -> dict[str, str]:
    """Return localized share title, body, labels, and UI tone for a forecast."""
    market_title = _truncate_title(
        prediction.market.display_title or prediction.market.title
    )

    if prediction.status == Prediction.Status.RESOLVED:
        if prediction.is_correct:
            return {
                "title": _("I told you so · %(title)s") % {"title": market_title},
                "text": _("I told you so — I called %(title)s.") % {"title": market_title},
                "button_label": _("I told you so"),
                "sheet_title": _("Share your win"),
                "aria_label": _("Share — I told you so"),
                "tone": "win",
            }
        return {
            "title": _("You were right · %(title)s") % {"title": market_title},
            "text": _("You were right on %(title)s :(") % {"title": market_title},
            "button_label": _("You were right :("),
            "sheet_title": _("Share how it went"),
            "aria_label": _("Share — you were right"),
            "tone": "loss",
        }

    author = prediction.user.public_name or prediction.user.username
    short_title = _truncate_title(market_title, max_len=40)
    return {
        "title": _("%(name)s on %(title)s") % {"name": author, "title": short_title},
        "text": _("See my forecast on %(title)s") % {"title": market_title},
        "button_label": _("Share"),
        "sheet_title": _("Share forecast"),
        "aria_label": _("Share forecast"),
        "tone": "default",
    }
