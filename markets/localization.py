"""Locale-aware labels for imported market metadata."""

from __future__ import annotations

from django.utils.translation import gettext as _

# Common Polymarket/Kalshi category strings → canonical Spanish labels.
CATEGORY_LABELS: dict[str, str] = {
    "politics": "Politics",
    "sports": "Sports",
    "crypto": "Crypto",
    "cryptocurrency": "Crypto",
    "economy": "Economy",
    "economics": "Economy",
    "business": "Business",
    "science": "Science",
    "tech": "Tech",
    "technology": "Tech",
    "culture": "Culture",
    "entertainment": "Entertainment",
    "world": "World",
    "finance": "Finance",
    "ai": "AI",
    "elections": "Elections",
    "us politics": "US Politics",
    "global politics": "Global Politics",
    "nba": "NBA",
    "nfl": "NFL",
    "mlb": "MLB",
    "soccer": "Soccer",
    "football": "Football",
    "basketball": "Basketball",
    "tennis": "Tennis",
    "mma": "MMA",
    "pop culture": "Pop Culture",
}

CATEGORY_LABELS_ES: dict[str, str] = {
    "politics": "Política",
    "sports": "Deportes",
    "crypto": "Cripto",
    "cryptocurrency": "Cripto",
    "economy": "Economía",
    "economics": "Economía",
    "business": "Negocios",
    "science": "Ciencia",
    "tech": "Tecnología",
    "technology": "Tecnología",
    "culture": "Cultura",
    "entertainment": "Entretenimiento",
    "world": "Mundo",
    "finance": "Finanzas",
    "ai": "IA",
    "elections": "Elecciones",
    "us politics": "Política de EE. UU.",
    "global politics": "Política global",
    "nba": "NBA",
    "nfl": "NFL",
    "mlb": "MLB",
    "soccer": "Fútbol",
    "football": "Fútbol americano",
    "basketball": "Baloncesto",
    "tennis": "Tenis",
    "mma": "MMA",
    "pop culture": "Cultura pop",
}

COMMON_OUTCOMES_ES: dict[str, str] = {
    "yes": "Sí",
    "no": "No",
    "draw": "Empate",
}


def localize_category_label(raw: str, *, language: str | None = None) -> str:
    label = (raw or "").strip()
    if not label:
        return ""

    from django.utils import translation

    lang = language or translation.get_language() or "en"
    key = label.casefold()

    if lang.startswith("es"):
        if key in CATEGORY_LABELS_ES:
            return CATEGORY_LABELS_ES[key]
        from markets.categories import CANONICAL_CATEGORIES

        for category in CANONICAL_CATEGORIES:
            if key in category.category_names or key == category.slug:
                return str(category.name)
        return label

    if key in CATEGORY_LABELS:
        return _(CATEGORY_LABELS[key])
    from markets.categories import CANONICAL_CATEGORIES

    for category in CANONICAL_CATEGORIES:
        if key in category.category_names or key == category.slug:
            return str(category.name)
    return label


def localize_outcome_label(label: str, *, language: str | None = None) -> str:
    text = (label or "").strip()
    if not text:
        return ""

    from django.utils import translation

    lang = language or translation.get_language() or "en"
    key = text.casefold()

    if lang.startswith("es") and key in COMMON_OUTCOMES_ES:
        return COMMON_OUTCOMES_ES[key]
    if key == "yes":
        return _("Yes")
    if key == "no":
        return _("No")
    if key == "draw":
        return _("Draw")
    return text
