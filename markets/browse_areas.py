"""Sub-area filters within canonical browse categories (Polymarket-style leagues/topics)."""

from dataclasses import dataclass

from markets.categories import _collect_tag_slugs


@dataclass(frozen=True)
class BrowseArea:
    slug: str
    name: str
    tag_slugs: frozenset[str]
    category_slug: str


BROWSE_AREAS: tuple[BrowseArea, ...] = (
    # Sports
    BrowseArea("soccer", "Soccer", frozenset({"soccer", "fifa-world-cup", "2026-fifa-world-cup", "ucl", "champions-league"}), "sports"),
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


def market_matches_browse_area(market, area: BrowseArea) -> bool:
    return bool(_collect_tag_slugs(market).intersection(area.tag_slugs))
