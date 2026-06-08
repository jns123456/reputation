from django.conf import settings
from django.core.cache import cache

from markets.selectors import get_landing_tape_markets

TAPE_MARKETS_CACHE_KEY = "landing_tape_markets"


def load_tape_markets():
    markets = cache.get(TAPE_MARKETS_CACHE_KEY)
    if markets is None:
        markets = get_landing_tape_markets()
        cache.set(TAPE_MARKETS_CACHE_KEY, markets, settings.MARKET_SYNC_CACHE_SECONDS)
    return markets


def tape_markets_context(request):
    return {"landing_tape_markets": load_tape_markets()}
