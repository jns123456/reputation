"""How users interact with a market when placing a forecast.

Polymarket uses several shapes; PredictStamp maps them to three modes:

- ``binary`` — single Yes/No question (standalone binary market).
- ``pick_one`` — mutually exclusive outcomes (e.g. soccer moneyline: Team A / Draw / Team B).
- ``multi_binary`` — grouped event where each outcome is its own Yes/No sub-market
  (e.g. "Who will win the nomination?" with per-candidate binaries).
"""

from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND


class ForecastMode:
    BINARY = "binary"
    PICK_ONE = "pick_one"
    MULTI_BINARY = "multi_binary"


def get_forecast_mode(market) -> str:
    raw = getattr(market, "polymarket_raw", None) or {}
    market_kind = raw.get("market_kind", "")
    labels = getattr(market, "outcome_labels", None) or []

    if market_kind == "soccer_match_3way":
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
