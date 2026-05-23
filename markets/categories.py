"""Canonical market categories for browse UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalCategory:
    slug: str
    name: str
    description: str
    tag_slugs: frozenset[str]
    category_names: frozenset[str]
    polymarket_tag: str
    icon_bg: str
    icon_fg: str
    ring: str
    hero_bg: str
    card_glow: str
    card_hover: str


CANONICAL_CATEGORIES: tuple[CanonicalCategory, ...] = (
    CanonicalCategory(
        slug="crypto",
        name="Crypto",
        description="Bitcoin, Ethereum, and digital assets",
        tag_slugs=frozenset(
            {
                "crypto",
                "bitcoin",
                "ethereum",
                "defi",
                "nft",
                "blockchain",
                "megaeth",
                "solana",
            }
        ),
        category_names=frozenset({"crypto", "cryptocurrency"}),
        polymarket_tag="crypto",
        icon_bg="bg-violet-500/15",
        icon_fg="text-violet-600",
        ring="ring-violet-500/20",
        hero_bg="bg-gradient-to-br from-violet-500/10 to-purple-600/5",
        card_glow="bg-gradient-to-br from-violet-500/20 to-purple-600/10",
        card_hover="from-violet-500/0 to-purple-600/0 group-hover:from-violet-500/10 group-hover:to-purple-600/5",
    ),
    CanonicalCategory(
        slug="economy",
        name="Economy",
        description="Rates, inflation, jobs, and macro trends",
        tag_slugs=frozenset(
            {
                "economy",
                "business",
                "fed-rates",
                "fed",
                "fomc",
                "economic-policy",
                "jerome-powell",
                "finance",
            }
        ),
        category_names=frozenset({"economy", "economics", "business"}),
        polymarket_tag="economy",
        icon_bg="bg-emerald-500/15",
        icon_fg="text-emerald-600",
        ring="ring-emerald-500/20",
        hero_bg="bg-gradient-to-br from-emerald-500/10 to-teal-600/5",
        card_glow="bg-gradient-to-br from-emerald-500/20 to-teal-600/10",
        card_hover="from-emerald-500/0 to-teal-600/0 group-hover:from-emerald-500/10 group-hover:to-teal-600/5",
    ),
    CanonicalCategory(
        slug="politics",
        name="Politics",
        description="Elections, policy, and government",
        tag_slugs=frozenset(
            {
                "politics",
                "elections",
                "global-elections",
                "world-elections",
                "us-presidential-election",
                "primaries",
                "united-states",
                "courts",
                "congress",
            }
        ),
        category_names=frozenset({"politics"}),
        polymarket_tag="politics",
        icon_bg="bg-blue-500/15",
        icon_fg="text-blue-600",
        ring="ring-blue-500/20",
        hero_bg="bg-gradient-to-br from-blue-500/10 to-indigo-600/5",
        card_glow="bg-gradient-to-br from-blue-500/20 to-indigo-600/10",
        card_hover="from-blue-500/0 to-indigo-600/0 group-hover:from-blue-500/10 group-hover:to-indigo-600/5",
    ),
    CanonicalCategory(
        slug="sports",
        name="Sports",
        description="Leagues, tournaments, and championships",
        tag_slugs=frozenset(
            {
                "sports",
                "soccer",
                "fifa-world-cup",
                "2026-fifa-world-cup",
                "nba",
                "nfl",
                "mlb",
                "nhl",
                "ncaa",
                "tennis",
                "mma",
                "ufc",
            }
        ),
        category_names=frozenset({"sports"}),
        polymarket_tag="sports",
        icon_bg="bg-orange-500/15",
        icon_fg="text-orange-600",
        ring="ring-orange-500/20",
        hero_bg="bg-gradient-to-br from-orange-500/10 to-amber-600/5",
        card_glow="bg-gradient-to-br from-orange-500/20 to-amber-600/10",
        card_hover="from-orange-500/0 to-amber-600/0 group-hover:from-orange-500/10 group-hover:to-amber-600/5",
    ),
    CanonicalCategory(
        slug="pop-culture",
        name="Pop Culture",
        description="Movies, games, music, and entertainment",
        tag_slugs=frozenset(
            {
                "pop-culture",
                "movies",
                "music",
                "entertainment",
                "gta-vi",
                "gaming",
                "tv",
            }
        ),
        category_names=frozenset({"pop culture", "entertainment"}),
        polymarket_tag="pop-culture",
        icon_bg="bg-pink-500/15",
        icon_fg="text-pink-600",
        ring="ring-pink-500/20",
        hero_bg="bg-gradient-to-br from-pink-500/10 to-rose-600/5",
        card_glow="bg-gradient-to-br from-pink-500/20 to-rose-600/10",
        card_hover="from-pink-500/0 to-rose-600/0 group-hover:from-pink-500/10 group-hover:to-rose-600/5",
    ),
    CanonicalCategory(
        slug="science-tech",
        name="Science & Tech",
        description="AI, space, breakthroughs, and innovation",
        tag_slugs=frozenset(
            {
                "science",
                "tech",
                "technology",
                "ai",
                "artificial-intelligence",
                "space",
            }
        ),
        category_names=frozenset({"technology", "science", "tech", "science & tech"}),
        polymarket_tag="science",
        icon_bg="bg-cyan-500/15",
        icon_fg="text-cyan-600",
        ring="ring-cyan-500/20",
        hero_bg="bg-gradient-to-br from-cyan-500/10 to-sky-600/5",
        card_glow="bg-gradient-to-br from-cyan-500/20 to-sky-600/10",
        card_hover="from-cyan-500/0 to-sky-600/0 group-hover:from-cyan-500/10 group-hover:to-sky-600/5",
    ),
    CanonicalCategory(
        slug="world",
        name="World",
        description="Geopolitics, conflicts, and global events",
        tag_slugs=frozenset(
            {
                "geopolitics",
                "world-affairs",
                "international",
                "middle-east",
                "ukraine",
                "china",
                "war",
            }
        ),
        category_names=frozenset({"world", "geopolitics"}),
        polymarket_tag="geopolitics",
        icon_bg="bg-slate-500/15",
        icon_fg="text-slate-600",
        ring="ring-slate-500/20",
        hero_bg="bg-gradient-to-br from-slate-500/10 to-slate-800/5",
        card_glow="bg-gradient-to-br from-slate-500/20 to-slate-800/10",
        card_hover="from-slate-500/0 to-slate-800/0 group-hover:from-slate-500/10 group-hover:to-slate-800/5",
    ),
)

OTHER_CATEGORY = CanonicalCategory(
    slug="other",
    name="Other",
    description="More markets across the platform",
    tag_slugs=frozenset(),
    category_names=frozenset(),
    polymarket_tag="",
    icon_bg="bg-slate-500/15",
    icon_fg="text-slate-500",
    ring="ring-slate-500/20",
    hero_bg="bg-gradient-to-br from-slate-400/10 to-slate-500/5",
    card_glow="bg-gradient-to-br from-slate-400/20 to-slate-500/10",
    card_hover="from-slate-400/0 to-slate-500/0 group-hover:from-slate-400/10 group-hover:to-slate-500/5",
)

CATEGORY_BY_SLUG = {category.slug: category for category in CANONICAL_CATEGORIES}
CATEGORY_BY_SLUG[OTHER_CATEGORY.slug] = OTHER_CATEGORY


def _collect_tag_slugs(market) -> set[str]:
    slugs = set()
    for payload in (market.polymarket_event_raw or {}, market.polymarket_raw or {}):
        for tag in payload.get("tags") or []:
            if isinstance(tag, dict):
                slug = tag.get("slug") or tag.get("label")
            else:
                slug = str(tag)
            if slug:
                slugs.add(str(slug).lower())
    return slugs


def resolve_market_category_slug(market) -> str:
    """Map a market to one canonical category slug."""
    tag_slugs = _collect_tag_slugs(market)

    for category in CANONICAL_CATEGORIES:
        if tag_slugs.intersection(category.tag_slugs):
            return category.slug

    category_name = (market.category or "").strip().lower()
    for category in CANONICAL_CATEGORIES:
        if category_name in category.category_names:
            return category.slug

    return OTHER_CATEGORY.slug


def get_category_for_slug(slug: str) -> CanonicalCategory | None:
    return CATEGORY_BY_SLUG.get(slug)


def get_all_chart_categories() -> tuple[CanonicalCategory, ...]:
    """All categories shown on profile radar charts and category leaderboards."""
    return CANONICAL_CATEGORIES + (OTHER_CATEGORY,)
