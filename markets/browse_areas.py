"""Sub-area filters within canonical browse categories (Polymarket-style leagues/topics)."""

from dataclasses import dataclass

from markets.categories import _collect_tag_slugs


@dataclass(frozen=True)
class BrowseArea:
    slug: str
    name: str
    tag_slugs: frozenset[str]
    category_slug: str


KALSHI_SERIES_BY_BROWSE_AREA: dict[tuple[str, str], frozenset[str]] = {
    ("sports", "soccer"): frozenset(),
    ("sports", "nba"): frozenset({"KXNBAGAME", "KXWNBAGAME", "KXNBAH2HPTS"}),
    ("sports", "mlb"): frozenset({"KXMLBGAME", "KXMLBSPREAD"}),
    ("sports", "nhl"): frozenset({"KXNHLGAME"}),
    ("sports", "nfl"): frozenset({"KXNFLGAME", "KXNFLNFCCHAMP"}),
    ("sports", "ufc"): frozenset(),
    ("sports", "tennis"): frozenset(),
    ("sports", "cricket"): frozenset(),
    ("economy", "fed"): frozenset({"KXFED", "KXFEDDECISION", "KXEFFR", "KXCBDECISIONENGLAND"}),
    ("economy", "finance"): frozenset({"KXUSTYLD", "KXMORTGAGERATE"}),
    ("economy", "macro"): frozenset({"KXECONSTATCPIYOY", "KXPAYROLLS", "KXJOBLESS", "KXU3"}),
    ("science-tech", "ai"): frozenset({"KXAILABDIS", "KXFRONTIERAI"}),
}


def _kalshi_series_ticker(market) -> str:
    raw = market.kalshi_raw or {}
    event_payload = market.kalshi_event_raw or {}
    event = event_payload.get("event") if isinstance(event_payload, dict) else {}
    if not isinstance(event, dict):
        event = event_payload if isinstance(event_payload, dict) else {}
    return (raw.get("series_ticker") or event.get("series_ticker") or "").upper()


BROWSE_AREAS: tuple[BrowseArea, ...] = (
    # Sports
    BrowseArea("soccer", "Soccer", frozenset({"soccer", "ucl", "champions-league"}), "sports"),
    BrowseArea("nba", "NBA", frozenset({"nba", "nba-finals", "nba-champion", "2026-nba-playoffs", "basketball"}), "sports"),
    BrowseArea("mlb", "MLB", frozenset({"mlb", "baseball"}), "sports"),
    BrowseArea("nhl", "NHL", frozenset({"nhl", "hockey", "stanley-cup", "2026-nhl-playoffs"}), "sports"),
    BrowseArea("nfl", "NFL", frozenset({"nfl", "ncaa", "american-football", "football"}), "sports"),
    BrowseArea("ufc", "UFC", frozenset({"ufc", "mma"}), "sports"),
    BrowseArea("tennis", "Tennis", frozenset({"tennis"}), "sports"),
    BrowseArea("cricket", "Cricket", frozenset({"cricket"}), "sports"),
    # Crypto
    BrowseArea("bitcoin", "Bitcoin", frozenset({"bitcoin"}), "crypto"),
    BrowseArea("ethereum", "Ethereum", frozenset({"ethereum", "eth"}), "crypto"),
    BrowseArea("defi", "DeFi", frozenset({"defi"}), "crypto"),
    BrowseArea("nft", "NFT", frozenset({"nft", "nfts"}), "crypto"),
    BrowseArea("altcoins", "Altcoins", frozenset({"solana", "megaeth", "airdrops", "pre-market"}), "crypto"),
    # Politics
    BrowseArea("us-elections", "US Elections", frozenset({"us-presidential-election", "primaries", "united-states"}), "politics"),
    BrowseArea("global-elections", "Global Elections", frozenset({"world-elections", "global-elections", "elections"}), "politics"),
    BrowseArea("policy", "Policy & Courts", frozenset({"courts", "congress"}), "politics"),
    BrowseArea("geopolitics", "Geopolitics", frozenset({"geopolitics", "macro-geopolitics", "war", "middle-east"}), "politics"),
    # Economy
    BrowseArea("fed", "Fed & Rates", frozenset({"fed", "fed-rates", "fomc", "jerome-powell", "economic-policy"}), "economy"),
    BrowseArea("finance", "Finance", frozenset({"finance", "business", "stocks", "microstrategy"}), "economy"),
    BrowseArea("macro", "Macro", frozenset({"economy"}), "economy"),
    # Pop Culture
    BrowseArea("movies", "Movies", frozenset({"movies", "gta-vi"}), "pop-culture"),
    BrowseArea("gaming", "Gaming", frozenset({"gaming", "gta-vi", "video-games"}), "pop-culture"),
    BrowseArea("music", "Music", frozenset({"music"}), "pop-culture"),
    BrowseArea("tv", "TV", frozenset({"tv", "television"}), "pop-culture"),
    # Science & Tech
    BrowseArea("ai", "AI", frozenset({"ai", "artificial-intelligence", "big-tech"}), "science-tech"),
    BrowseArea("space", "Space", frozenset({"space", "nasa"}), "science-tech"),
    BrowseArea("tech", "Tech", frozenset({"tech", "technology"}), "science-tech"),
    # World
    BrowseArea("middle-east", "Middle East", frozenset({"middle-east", "iran", "israel"}), "world"),
    BrowseArea("ukraine", "Ukraine", frozenset({"ukraine"}), "world"),
    BrowseArea("china", "China", frozenset({"china"}), "world"),
    BrowseArea("conflicts", "Conflicts", frozenset({"war", "geopolitics", "macro-geopolitics"}), "world"),
)

AREAS_BY_CATEGORY: dict[str, tuple[BrowseArea, ...]] = {}
for _area in BROWSE_AREAS:
    AREAS_BY_CATEGORY.setdefault(_area.category_slug, []).append(_area)
AREAS_BY_CATEGORY = {key: tuple(value) for key, value in AREAS_BY_CATEGORY.items()}

AREA_BY_KEY: dict[tuple[str, str], BrowseArea] = {
    (area.category_slug, area.slug): area for area in BROWSE_AREAS
}


def get_browse_areas_for_category(category_slug: str) -> tuple[BrowseArea, ...]:
    return AREAS_BY_CATEGORY.get(category_slug, ())


def get_browse_area(category_slug: str, area_slug: str) -> BrowseArea | None:
    return AREA_BY_KEY.get((category_slug, area_slug))


def compute_browse_area_slugs(market) -> list[str]:
    """All browse-area slugs a market belongs to, derived from raw payloads.

    Denormalized onto ``Market.browse_area_slugs`` at save/import time so that
    request-time filtering and counting never touch the large raw JSON payloads
    (which are deferred on card querysets and would trigger N+1 fetches).
    """
    tag_slugs = _collect_tag_slugs(market)
    series = _kalshi_series_ticker(market)
    matched: list[str] = []
    for area in BROWSE_AREAS:
        if tag_slugs.intersection(area.tag_slugs):
            matched.append(area.slug)
            continue
        if series:
            kalshi_series = KALSHI_SERIES_BY_BROWSE_AREA.get(
                (area.category_slug, area.slug), frozenset()
            )
            if series in kalshi_series:
                matched.append(area.slug)
    return matched


def market_matches_browse_area(market, area: BrowseArea) -> bool:
    """True when a market belongs to ``area`` using the denormalized membership.

    Reads ``Market.browse_area_slugs`` (a small, always-loaded column) instead of
    the deferred raw JSON payloads, so this is safe to call in a loop over card
    querysets without incurring per-row database fetches.
    """
    return area.slug in (getattr(market, "browse_area_slugs", None) or [])
