"""Reference token prices and cost estimates.

Prices are the professor-provided reference prices from the MGT 409 class slide
(USD per 1M tokens). They are not independently verified current prices; see
docs/pricing_investigation.md. Token counts are measured; dollar amounts are estimates.
"""

from __future__ import annotations

PRICE_SOURCE = "MGT 409 class slide (professor-provided reference prices, USD per 1M tokens)"

REFERENCE_PRICES: dict[str, dict[str, float]] = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50},
    "gpt-6.1-sol": {"input": 2.00, "cached_input": 0.10, "cache_write": 2.50, "output": 10.00},
    "gpt-6-astra": {"input": 10.00, "cached_input": 1.00, "cache_write": 12.50, "output": 50.00},
}


def estimate_cost_usd(model: str, input_tokens: int, cached_input_tokens: int = 0,
                      cache_write_tokens: int = 0, output_tokens: int = 0) -> float | None:
    """Estimated cost of one call. `input_tokens` is the API's total input count, which
    includes cached and cache-write tokens; those parts are priced at their own rates.
    Reasoning tokens are part of `output_tokens`. Returns None for unknown models."""
    p = REFERENCE_PRICES.get(model)
    if p is None:
        return None
    uncached = max(input_tokens - cached_input_tokens - cache_write_tokens, 0)
    cost = (uncached * p["input"] + cached_input_tokens * p["cached_input"]
            + cache_write_tokens * p["cache_write"] + output_tokens * p["output"]) / 1_000_000
    return round(cost, 8)
