"""Open Graph share-image rendering for public forecast cards.

Images are pure presentation: they read the same display metrics as the
forecast card partials (``build_forecast_card_metrics``) and never touch
scoring. Rendered bytes are cached because cards are immutable per status.
"""

import io
import textwrap

from django.core.cache import cache

from predictions.models import Prediction

OG_WIDTH = 1200
OG_HEIGHT = 630
OG_CACHE_SECONDS = 60 * 60

_BG = (15, 23, 42)  # slate-900
_FG = (241, 245, 249)  # slate-100
_MUTED = (148, 163, 184)  # slate-400
_BRAND = (99, 102, 241)  # indigo-500
_GREEN = (52, 211, 153)
_RED = (248, 113, 113)
_AMBER = (251, 191, 36)


def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow fallback
        return ImageFont.load_default()


def _viral_tagline(prediction):
    if prediction.status != Prediction.Status.RESOLVED:
        return None, None
    if prediction.is_correct:
        return "I TOLD YOU SO", _GREEN
    return "YOU WERE RIGHT :(", _AMBER


def _status_line(prediction, metrics):
    if prediction.status == Prediction.Status.RESOLVED:
        delta = metrics.get("pnl_delta")
        if prediction.is_correct:
            return (f"CORRECT  +{delta} reputation" if delta is not None else "CORRECT"), _GREEN
        return (f"INCORRECT  {delta} reputation" if delta is not None else "INCORRECT"), _RED
    if prediction.status == Prediction.Status.EXITED:
        delta = metrics.get("pnl_delta")
        if delta is None:
            return "EXITED", _AMBER
        sign = "+" if delta >= 0 else ""
        return f"EXITED  {sign}{delta} reputation", _AMBER
    delta = metrics.get("pnl_delta")
    if delta is None:
        return "OPEN FORECAST", _MUTED
    sign = "+" if delta >= 0 else ""
    return f"OPEN  {sign}{delta} unrealized", _GREEN if delta >= 0 else _RED


def render_prediction_og_image(prediction, metrics):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, OG_WIDTH, 14], fill=_BRAND)

    x = 72
    y = 70
    draw.text((x, y), "PredictStamp", font=_font(36), fill=_BRAND)
    y += 70

    title = (prediction.market.display_title or prediction.market.title or "").strip()
    for line in textwrap.wrap(title, width=42)[:3]:
        draw.text((x, y), line, font=_font(48), fill=_FG)
        y += 62
    y += 18

    direction = "No " if prediction.predicted_direction == Prediction.Direction.NO else ""
    pick = f"{direction}{prediction.predicted_outcome}".strip()
    entry = metrics.get("entry_percent")
    pick_line = f"Forecast: {pick}"
    if entry is not None:
        pick_line = f"{pick_line}  ·  entry {entry}%"
    for line in textwrap.wrap(pick_line, width=52)[:2]:
        draw.text((x, y), line, font=_font(38), fill=_MUTED)
        y += 50
    y += 18

    tagline, tagline_color = _viral_tagline(prediction)
    if tagline:
        draw.text((x, y), tagline, font=_font(52), fill=tagline_color)
        y += 64

    status_text, status_color = _status_line(prediction, metrics)
    draw.text((x, y), status_text, font=_font(44), fill=status_color)

    author = prediction.user.public_name or prediction.user.username
    draw.text((x, OG_HEIGHT - 90), f"by {author}", font=_font(32), fill=_MUTED)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_prediction_og_image(prediction, metrics):
    """Return cached PNG bytes for the forecast share card."""
    cache_key = (
        f"prediction-og:{prediction.id}:{prediction.status}:"
        f"{metrics.get('pnl_delta')}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rendered = render_prediction_og_image(prediction, metrics)
    cache.set(cache_key, rendered, OG_CACHE_SECONDS)
    return rendered
