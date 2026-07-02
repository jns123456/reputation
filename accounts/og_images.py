"""Branded Open Graph images for public user profiles."""

import io
import textwrap

from django.core.cache import cache

OG_WIDTH = 1200
OG_HEIGHT = 630
OG_CACHE_SECONDS = 60 * 60

_BG = (15, 23, 42)
_FG = (241, 245, 249)
_MUTED = (148, 163, 184)
_BRAND = (99, 102, 241)
_REP = (52, 211, 153)
_POP = (251, 191, 36)


def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_profile_og_image(user, share_context):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, OG_WIDTH, 18], fill=_BRAND)
    draw.text((OG_WIDTH - 280, 28), "PredictStamp.com", font=_font(28), fill=_BRAND)

    x, y = 72, 56
    name = user.public_name or user.username
    handle = f"@{user.username}" if user.show_username_publicly else ""
    draw.text((x, y), name, font=_font(52), fill=_FG)
    y += 64
    if handle:
        draw.text((x, y), handle, font=_font(30), fill=_MUTED)
        y += 44

    profile = getattr(user, "profile", None)
    if profile:
        line = f"Rep {profile.reputation_points:,}  ·  {profile.reputation_score} per forecast"
        draw.text((x, y), line, font=_font(32), fill=_REP)
        y += 46
        summary = share_context.get("prediction_summary") or {}
        accuracy = summary.get("accuracy_pct")
        acc_line = f"Popularity {profile.popularity_points:,}"
        if accuracy is not None:
            acc_line = f"{acc_line}  ·  {accuracy}% accuracy"
        draw.text((x, y), acc_line, font=_font(28), fill=_POP)
        y += 42

    tagline = share_context.get("tagline") or "Predictive reputation on real-world markets"
    for line in textwrap.wrap(str(tagline), width=48)[:2]:
        draw.text((x, OG_HEIGHT - 120), line, font=_font(26), fill=_MUTED)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_profile_og_image(user, share_context):
    profile = getattr(user, "profile", None)
    cache_key = (
        f"profile-og:{user.pk}:{getattr(profile, 'reputation_points', 0)}:"
        f"{getattr(profile, 'popularity_points', 0)}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rendered = render_profile_og_image(user, share_context)
    cache.set(cache_key, rendered, OG_CACHE_SECONDS)
    return rendered
