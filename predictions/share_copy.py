"""Share-sheet copy for public forecast cards (open vs resolved)."""

from __future__ import annotations

from django.utils.translation import gettext as _

from predictions.models import Prediction


def _truncate_title(title: str | None, *, max_len: int = 50) -> str:
    cleaned = (title or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def get_forecast_share_copy(prediction: Prediction, *, metrics: dict | None = None) -> dict[str, str]:
    """Return localized share title, body, labels, and UI tone for a forecast."""
    market_title = _truncate_title(
        prediction.market.display_title or prediction.market.title
    )
    metrics = metrics or {}

    if prediction.status == Prediction.Status.RESOLVED:
        entry = metrics.get("entry_percent")
        pnl = metrics.get("pnl_delta")
        if prediction.is_correct:
            body = _("I called it — %(title)s.") % {"title": market_title}
            if entry is not None and pnl is not None:
                body = _(
                    "I called it. Predicted at %(entry)s%%. Result: Correct. "
                    "Reputation earned: +%(points)s."
                ) % {"entry": entry, "points": pnl}
            return {
                "title": _("I called it · %(title)s") % {"title": market_title},
                "text": body,
                "button_label": _("I called it"),
                "sheet_title": _("Share your win"),
                "aria_label": _("Share — I called it"),
                "tone": "win",
            }
        body = _("This prediction aged badly — %(title)s.") % {"title": market_title}
        if entry is not None and pnl is not None:
            direction = (
                _("NO") if prediction.predicted_direction == Prediction.Direction.NO else _("YES")
            )
            body = _(
                "This prediction aged badly. Predicted %(direction)s at %(entry)s%%. "
                "Result: NO. Reputation lost: %(points)s."
            ) % {"direction": direction, "entry": entry, "points": pnl}
        return {
            "title": _("This aged badly · %(title)s") % {"title": market_title},
            "text": body,
            "button_label": _("This aged badly"),
            "sheet_title": _("Share how it went"),
            "aria_label": _("Share — this aged badly"),
            "tone": "loss",
        }

    author = prediction.user.public_name or prediction.user.username
    short_title = _truncate_title(market_title, max_len=40)
    return {
        "title": _("%(name)s predicts · %(title)s") % {"name": author, "title": short_title},
        "text": _("See my forecast on %(title)s") % {"title": market_title},
        "button_label": _("Share"),
        "sheet_title": _("Share prediction stamp"),
        "aria_label": _("Share forecast"),
        "tone": "default",
    }
