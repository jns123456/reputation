"""Translate imported market copy into Spanish for locale-aware display."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "market_translation:es:"
_MAX_CHUNK_LENGTH = 450
_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_DEEPL_URL = "https://api-free.deepl.com/v2/translate"

# Light post-processing for common prediction-market phrasing.
_PHRASE_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bprediction market\b", re.I), "mercado de predicción"),
    (re.compile(r"\bmarket resolves\b", re.I), "el mercado se resuelve"),
    (re.compile(r"\bresolves to\b", re.I), "se resuelve como"),
    (re.compile(r"\bby December 31\b", re.I), "antes del 31 de diciembre"),
    (re.compile(r"\bby January 31\b", re.I), "antes del 31 de enero"),
    (re.compile(r"\bby February 28\b", re.I), "antes del 28 de febrero"),
    (re.compile(r"\bby March 31\b", re.I), "antes del 31 de marzo"),
    (re.compile(r"\bby April 30\b", re.I), "antes del 30 de abril"),
    (re.compile(r"\bby May 31\b", re.I), "antes del 31 de mayo"),
    (re.compile(r"\bby June 30\b", re.I), "antes del 30 de junio"),
    (re.compile(r"\bby July 31\b", re.I), "antes del 31 de julio"),
    (re.compile(r"\bby August 31\b", re.I), "antes del 31 de agosto"),
    (re.compile(r"\bby September 30\b", re.I), "antes del 30 de septiembre"),
    (re.compile(r"\bby October 31\b", re.I), "antes del 31 de octubre"),
    (re.compile(r"\bby November 30\b", re.I), "antes del 30 de noviembre"),
    (re.compile(r"\bor more\b", re.I), "o más"),
    (re.compile(r"\bor less\b", re.I), "o menos"),
    (re.compile(r"\bor higher\b", re.I), "o superior"),
    (re.compile(r"\bor lower\b", re.I), "o inferior"),
)


def translation_enabled() -> bool:
    return bool(getattr(settings, "MARKET_TRANSLATION_ENABLED", False))


def _cache_key(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}{digest}"


def _get_cached(text: str) -> str | None:
    return cache.get(_cache_key(text))


def _set_cached(text: str, translated: str) -> None:
    timeout = getattr(settings, "MARKET_TRANSLATION_CACHE_SECONDS", 60 * 60 * 24 * 30)
    cache.set(_cache_key(text), translated, timeout=timeout)


def _polish_spanish(text: str) -> str:
    polished = text.strip()
    for pattern, replacement in _PHRASE_FIXES:
        polished = pattern.sub(replacement, polished)
    return polished


def _split_chunks(text: str) -> list[str]:
    paragraphs = text.split("\n")
    if len(paragraphs) > 1:
        chunks: list[str] = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
            if len(paragraph) <= _MAX_CHUNK_LENGTH:
                chunks.append(paragraph)
                continue
            start = 0
            while start < len(paragraph):
                end = min(start + _MAX_CHUNK_LENGTH, len(paragraph))
                if end < len(paragraph):
                    split_at = paragraph.rfind(" ", start, end)
                    if split_at > start:
                        end = split_at
                chunks.append(paragraph[start:end].strip())
                start = end
        return chunks

    if len(text) <= _MAX_CHUNK_LENGTH:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + _MAX_CHUNK_LENGTH, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def _translate_with_deepl(text: str) -> str | None:
    auth_key = getattr(settings, "DEEPL_AUTH_KEY", "") or ""
    if not auth_key:
        return None

    api_url = getattr(settings, "DEEPL_API_URL", _DEEPL_URL)
    payload = urllib.parse.urlencode(
        {
            "text": text,
            "target_lang": "ES",
            "source_lang": "EN",
            "preserve_formatting": "1",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Authorization": f"DeepL-Auth-Key {auth_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        logger.warning("DeepL translation failed (%s): %s", exc.code, text[:80])
        return None
    except OSError:
        logger.exception("DeepL translation request failed")
        return None

    translations = body.get("translations") or []
    if not translations:
        return None
    translated = translations[0].get("text")
    return translated.strip() if translated else None


def _translate_with_mymemory(text: str) -> str:
    query = urllib.parse.urlencode({"q": text, "langpair": "en|es"})
    url = f"{_MYMEMORY_URL}?{query}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                time.sleep(2**attempt + 1)
                continue
            logger.warning("MyMemory translation failed (%s): %s", exc.code, text[:80])
            return text
        except OSError:
            logger.exception("MyMemory translation request failed")
            return text
    translated = payload.get("responseData", {}).get("translatedText", text)
    if not translated:
        return text
    return translated.strip()


def _translate_chunk(text: str) -> str:
    cached = _get_cached(text)
    if cached is not None:
        return cached

    provider_order: tuple[Callable[[str], str | None], ...]
    provider_order = (_translate_with_deepl,)

    translated = None
    for provider in provider_order:
        translated = provider(text)
        if translated:
            break
    if not translated:
        translated = _translate_with_mymemory(text)

    translated = _polish_spanish(translated)
    _set_cached(text, translated)
    delay = getattr(settings, "MARKET_TRANSLATION_REQUEST_DELAY", 0.0)
    if delay:
        time.sleep(delay)
    return translated


def translate_market_copy(text: str) -> str:
    """Translate English market title/description copy into Spanish."""
    source = (text or "").strip()
    if not source:
        return ""

    chunks = _split_chunks(source)
    if len(chunks) == 1:
        return _translate_chunk(chunks[0])

    translated_chunks = [_translate_chunk(chunk) for chunk in chunks]
    rebuilt: list[str] = []
    chunk_index = 0
    for paragraph in source.split("\n"):
        if not paragraph.strip():
            rebuilt.append("")
            continue
        rebuilt.append(translated_chunks[chunk_index])
        chunk_index += 1
    return "\n".join(rebuilt)


def apply_spanish_translations_to_defaults(defaults: dict, *, existing_market=None) -> dict:
    """Populate title_es/description_es when imported English copy changes."""
    if not translation_enabled():
        return defaults

    title = defaults.get("title") or ""
    description = defaults.get("description") or ""

    previous_title = getattr(existing_market, "title", "") if existing_market else ""
    previous_description = getattr(existing_market, "description", "") if existing_market else ""
    existing_title_es = getattr(existing_market, "title_es", "") if existing_market else ""
    existing_description_es = getattr(existing_market, "description_es", "") if existing_market else ""

    if title:
        if not existing_title_es or title != previous_title:
            defaults["title_es"] = translate_market_copy(title)[:500]
    else:
        defaults["title_es"] = ""

    if description:
        if not existing_description_es or description != previous_description:
            defaults["description_es"] = translate_market_copy(description)
    else:
        defaults["description_es"] = ""

    return defaults
