#!/usr/bin/env python3
"""Fill empty Spanish msgstr entries in locale/es/LC_MESSAGES/django.po."""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import polib

PO_PATH = Path(__file__).resolve().parent.parent / "locale" / "es" / "LC_MESSAGES" / "django.po"
CACHE_PATH = Path(__file__).resolve().parent / "spanish_translation_cache.json"


def fetch_translation(text: str, cache: dict[str, str]) -> str:
    if text in cache:
        return cache[text]
    if len(text) > 450:
        chunks = []
        for part in text.split("\n"):
            chunks.append(fetch_translation(part, cache) if part else "")
        result = "\n".join(chunks)
        cache[text] = result
        return result
    query = urllib.parse.urlencode({"q": text, "langpair": "en|es"})
    url = f"https://api.mymemory.translated.net/get?{query}"
    context = ssl._create_unverified_context()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30, context=context) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                time.sleep(2 ** attempt + 2)
                continue
            raise
    translated = payload.get("responseData", {}).get("translatedText", text)
    if translated == text and payload.get("responseStatus") != 200:
        raise RuntimeError(f"Translation failed for: {text[:80]!r}")
    cache[text] = translated
    time.sleep(0.6)
    return translated


def main() -> None:
    cache: dict[str, str] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    po = polib.pofile(str(PO_PATH))
    empty = [entry for entry in po if entry.msgid and not entry.msgstr.strip()]
    print(f"Filling {len(empty)} empty translations…")

    for index, entry in enumerate(empty, start=1):
        if entry.msgid in cache:
            entry.msgstr = cache[entry.msgid]
        else:
            entry.msgstr = fetch_translation(entry.msgid, cache)
        if index % 25 == 0:
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {index}/{len(empty)}")

    for entry in po:
        if "fuzzy" in entry.flags and entry.msgstr:
            entry.flags.remove("fuzzy")

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    po.save(str(PO_PATH))
    remaining = [e for e in po if e.msgid and not e.msgstr.strip()]
    print(f"Done. Remaining empty: {len(remaining)}")


if __name__ == "__main__":
    main()
