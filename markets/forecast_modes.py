"""How users interact with a market when placing a forecast.

Polymarket uses several shapes; PredictStamp maps them to three modes:

- ``binary`` — single Yes/No question (standalone binary market).
- ``pick_one`` — mutually exclusive outcomes (e.g. soccer moneyline: Team A / Draw / Team B).
- ``multi_binary`` — grouped event where each outcome is its own Yes/No sub-market
  (e.g. "Who will win the nomination?" with per-candidate binaries).
"""

from integrations.polymarket.constants import (
    MULTI_OUTCOME_EVENT_KIND,
    POLYMARKET_EVENT_EXTERNAL_PREFIX,
)
from integrations.polymarket.head_to_head_matches import (
    H2H_MATCH_EXTERNAL_PREFIX,
    H2H_MATCH_KIND,
)


class ForecastMode:
    BINARY = "binary"
    PICK_ONE = "pick_one"
    MULTI_BINARY = "multi_binary"


WORLD_CUP_MATCH_EXTERNAL_PREFIX = "wc-match:"


def get_forecast_mode(market) -> str:
    external_id = getattr(market, "external_id", "") or ""
    labels = getattr(market, "outcome_labels", None) or []

    if external_id.startswith(WORLD_CUP_MATCH_EXTERNAL_PREFIX):
        return ForecastMode.PICK_ONE
    if external_id.startswith(H2H_MATCH_EXTERNAL_PREFIX):
        return ForecastMode.PICK_ONE
    if external_id.startswith(POLYMARKET_EVENT_EXTERNAL_PREFIX):
        return ForecastMode.MULTI_BINARY

    deferred = getattr(market, "_card_payloads_deferred", None)
    raw = {}
    if not callable(deferred) or not deferred():
        raw = getattr(market, "polymarket_raw", None) or {}
    market_kind = raw.get("market_kind", "")

    if market_kind in {"soccer_match_3way", H2H_MATCH_KIND}:
        return ForecastMode.PICK_ONE
    if market_kind == MULTI_OUTCOME_EVENT_KIND:
        return ForecastMode.MULTI_BINARY
    if len(labels) > 2:
        return ForecastMode.PICK_ONE
    return ForecastMode.BINARY


def uses_multi_binary_panel(market) -> bool:
    return get_forecast_mode(market) == ForecastMode.MULTI_BINARY


def uses_pick_one_form(market) -> bool:
    return get_forecast_mode(market) in {ForecastMode.BINARY, ForecastMode.PICK_ONE}
