"""Open Graph share images for public challenge cards."""

import io
import textwrap

from django.core.cache import cache

from challenges.models import Challenge

OG_WIDTH = 1200
OG_HEIGHT = 630
OG_CACHE_SECONDS = 60 * 60

_BG = (15, 23, 42)
_FG = (241, 245, 249)
_MUTED = (148, 163, 184)
_BRAND = (99, 102, 241)
_GREEN = (52, 211, 153)


def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_challenge_og_image(challenge, stamp_context):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), _BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, OG_WIDTH, 18], fill=_BRAND)
    draw.text((OG_WIDTH - 280, 28), "PredictStamp.com", font=_font(28), fill=_BRAND)

    x, y = 72, 56
    duel = stamp_context.get("duel_users")
    if duel:
        creator, opponent = duel
        line = f"{creator.public_name} challenged {opponent.public_name}"
        for wrapped in textwrap.wrap(line, width=44)[:2]:
            draw.text((x, y), wrapped, font=_font(40), fill=_FG)
            y += 52
        y += 12

    market = stamp_context.get("primary_market")
    if market:
        title = (market.display_title or market.title or "").strip()
        for line in textwrap.wrap(title, width=42)[:2]:
            draw.text((x, y), line, font=_font(44), fill=_FG)
            y += 56
        y += 12

    creator_pick = stamp_context.get("creator_pick")
    opponent_pick = stamp_context.get("opponent_pick")
    if creator_pick and opponent_pick and duel:
        draw.text(
            (x, y),
            f"{duel[0].public_name}: {creator_pick}  ·  {duel[1].public_name}: {opponent_pick}",
            font=_font(32),
            fill=_MUTED,
        )
        y += 48

    if challenge.status == Challenge.Status.COMPLETED and challenge.winner:
        draw.text(
            (x, y),
            f"Winner: {challenge.winner.public_name}",
            font=_font(38),
            fill=_GREEN,
        )
    elif challenge.status == Challenge.Status.ACTIVE:
        draw.text((x, y), "LIVE CHALLENGE", font=_font(36), fill=_BRAND)
    else:
        draw.text((x, y), "PENDING CHALLENGE", font=_font(36), fill=_MUTED)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_challenge_og_image(challenge, stamp_context):
    cache_key = f"challenge-og:{challenge.id}:{challenge.status}:{challenge.winner_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rendered = render_challenge_og_image(challenge, stamp_context)
    cache.set(cache_key, rendered, OG_CACHE_SECONDS)
    return rendered
