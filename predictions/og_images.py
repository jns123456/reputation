"""Open Graph share-image rendering for public forecast cards.

Images are pure presentation: they read the same display metrics as the
forecast card partials (``build_forecast_card_metrics``) and never touch
scoring. Rendered bytes are cached because cards are immutable per status.
"""

import io
import textwrap

from django.core.cache import cache
from django.utils import timezone

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


def _viral_tagline(prediction, stamp_context):
    if prediction.status != Prediction.Status.RESOLVED:
        author = prediction.user.public_name or prediction.user.username
        return f"{author} predicts:", _FG
    if prediction.is_correct:
        return "I CALLED IT", _GREEN
    return "WRONG CALL", _AMBER


def _status_line(prediction, metrics, stamp_context):
    if prediction.status == Prediction.Status.RESOLVED:
        delta = metrics.get("pnl_delta")
        entry = metrics.get("entry_percent")
        days = stamp_context.get("days_before_resolution")
        if prediction.is_correct:
            parts = ["Result: Correct"]
            if delta is not None:
                parts.append(f"+{delta} reputation")
            if entry is not None:
                parts.insert(0, f"Predicted at {entry}%")
            if days is not None:
                parts.append(f"{days}d before resolution")
            return "  ·  ".join(parts), _GREEN
        parts = ["Result: Incorrect"]
        if delta is not None:
            parts.append(f"{delta} reputation")
        if entry is not None:
            direction = "YES" if prediction.predicted_direction == Prediction.Direction.YES else "NO"
            parts.insert(0, f"Predicted {direction} at {entry}%")
        return "  ·  ".join(parts), _RED
    if prediction.status == Prediction.Status.EXITED:
        delta = metrics.get("pnl_delta")
        if delta is None:
            return "EXITED", _AMBER
        sign = "+" if delta >= 0 else ""
        return f"EXITED  {sign}{delta} reputation", _AMBER
    delta = metrics.get("pnl_delta")
    entry = metrics.get("entry_percent")
    lines = []
    if entry is not None:
        direction = "YES" if prediction.predicted_direction == Prediction.Direction.YES else "NO"
        lines.append(f"Position: {direction}  ·  Market {entry}%")
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        lines.append(f"Unrealized {sign}{delta} rep")
    if not lines:
        return "OPEN FORECAST", _MUTED
    return "  ·  ".join(lines), _MUTED


def _format_timestamp(when):
    if when is None:
        return ""
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())
    return when.strftime("%B ") + str(when.day) + when.strftime(", %Y")


def render_prediction_og_image(prediction, metrics, stamp_context=None):
    from PIL import Image, ImageDraw

    stamp_context = stamp_context or {}
    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, OG_WIDTH, 18], fill=_BRAND)
    draw.text((OG_WIDTH - 280, 28), "PredictStamp.com", font=_font(28), fill=_BRAND)

    x = 72
    y = 56
    tagline, tagline_color = _viral_tagline(prediction, stamp_context)
    draw.text((x, y), tagline, font=_font(40), fill=tagline_color)
    y += 58

    title = (prediction.market.display_title or prediction.market.title or "").strip()
    for line in textwrap.wrap(title, width=42)[:2]:
        draw.text((x, y), line, font=_font(46), fill=_FG)
        y += 58
    y += 12

    pick = stamp_context.get("pick_label") or prediction.predicted_outcome
    pick_line = f"Forecast: {pick}"
    draw.text((x, y), pick_line, font=_font(34), fill=_MUTED)
    y += 48

    status_text, status_color = _status_line(prediction, metrics, stamp_context)
    for line in textwrap.wrap(status_text, width=54)[:2]:
        draw.text((x, y), line, font=_font(32), fill=status_color)
        y += 42
    y += 8

    meta_parts = []
    ts = _format_timestamp(prediction.created_at)
    if ts:
        meta_parts.append(ts)
    rep = stamp_context.get("reputation_points")
    if rep is not None:
        meta_parts.append(f"Rep {rep:,}")
    top_pct = stamp_context.get("category_top_percent")
    cat_name = stamp_context.get("category_name")
    if top_pct and cat_name:
        meta_parts.append(f"Top {top_pct}% in {cat_name}")
    if meta_parts:
        draw.text((x, y), "  ·  ".join(meta_parts), font=_font(26), fill=_MUTED)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_prediction_og_image(prediction, metrics, stamp_context=None):
    """Return cached PNG bytes for the forecast share card."""
    stamp_context = stamp_context or {}
    cache_key = (
        f"prediction-og:v2:{prediction.id}:{prediction.status}:"
        f"{metrics.get('pnl_delta')}:{stamp_context.get('category_top_percent')}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rendered = render_prediction_og_image(prediction, metrics, stamp_context)
    cache.set(cache_key, rendered, OG_CACHE_SECONDS)
    return rendered
