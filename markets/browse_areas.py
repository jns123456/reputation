"""Sub-area filters within canonical browse categories (Polymarket-style leagues/topics)."""

from dataclasses import dataclass

from markets.categories import FIFA_WORLD_CUP_CATEGORY_SLUG, _collect_tag_slugs

WORLD_CUP_GAMES_AREA_SLUG = "world-cup-games"


@dataclass(frozen=True)
class BrowseArea:
    slug: str
    name: str
    tag_slugs: frozenset[str]
    category_slug: str


BROWSE_AREAS: tuple[BrowseArea, ...] = (
    # Sports
    BrowseArea(
        WORLD_CUP_GAMES_AREA_SLUG,
        "FIFA World Cup 2026",
        frozenset({"fifa-world-cup", "2026-fifa-world-cup"}),
        "sports",
    ),
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
    from integrations.polymarket.soccer_matches import is_world_cup_match_market

    tag_slugs = _collect_tag_slugs(market)
    matched: list[str] = []
    for area in BROWSE_AREAS:
        if tag_slugs.intersection(area.tag_slugs):
            matched.append(area.slug)
    if is_world_cup_match_market(market) and WORLD_CUP_GAMES_AREA_SLUG not in matched:
        matched.append(WORLD_CUP_GAMES_AREA_SLUG)
    return matched


def market_matches_browse_area(market, area: BrowseArea) -> bool:
    """True when a market belongs to ``area`` using the denormalized membership.

    Reads ``Market.browse_area_slugs`` (a small, always-loaded column) instead of
    the deferred raw JSON payloads, so this is safe to call in a loop over card
    querysets without incurring per-row database fetches.
    """
    if area.slug == WORLD_CUP_GAMES_AREA_SLUG and area.category_slug == "sports":
        return (getattr(market, "canonical_category_slug", "") or "") == FIFA_WORLD_CUP_CATEGORY_SLUG
    return area.slug in (getattr(market, "browse_area_slugs", None) or [])
