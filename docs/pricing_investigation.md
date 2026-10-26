# Model pricing (decision G2)

**Status (2026-10-25):** Venn uses the **professor-provided reference prices** from the MGT 409 class slide. Token counts come from real API responses. Dollar amounts are **estimates** made by applying the reference prices to those counts. They are not measured costs, and no billing source has confirmed them.

## Reference prices (class slide, USD per 1M tokens)

| Model | Input | Cached input | Cache write | Output | How Venn uses it |
|---|---:|---:|---:|---:|---|
| `gpt-6-luna` | $0.10 | $0.01 | $0.125 | $0.50 | Default for all AI features. It is the only model used so far. |
| `gpt-6.1-sol` | $2.00 | $0.10 | $2.50 | $10.00 | Not used. Reserved for specific reasoning-heavy tasks if that is justified later. |
| `gpt-6-astra` | $10.00 | $1.00 | $12.50 | $50.00 | Not used. |

These numbers are coded in `backend/app/ai/pricing.py`, together with their source label.

- **Formula:** cost = (input − cached − cache write) × input price + cached × cached price + cache write × cache-write price + output × output price.
- **Assumption:** `input_tokens` from the API includes the cached and cache-write tokens. This matches the OpenAI usage format and was not checked further.
- **Reasoning tokens:** these are part of `output_tokens` and are billed at the output price.

**Conflict to resolve before using `gpt-6.1-sol`.** The *Final Project Instructions* PDF says the course key may be used with **`gpt-6-luna` only** ("No other models on the course key"). Venn's config only allows `gpt-6-luna`. Using Sol would need the instructor's approval, or the student's own `OPENAI_API_KEY`.

## Investigation log (2026-10-24 and 2026-10-25)

| Source | Result |
|---|---|
| `response.usage` from the Responses API through Portkey | **Available.** It returns: <ul><li>`input_tokens`, with `input_tokens_details.cached_tokens` and `cache_write_tokens`;</li><li>`output_tokens`, with `output_tokens_details.reasoning_tokens`.</li></ul> Venn stores all of these in the `ai_usage` table. |
| Response headers | **No cost or price headers.** <ul><li>Served by Azure OpenAI (`x-ms-region: East US 2`).</li><li>Model snapshot: `x-ms-served-model: gpt-6-luna-2026-09-22`; the response body reports `gpt-6-luna-global`.</li><li>Rate limits: 15,000 requests and 15M tokens per 60 s.</li></ul> |
| Portkey analytics API (`/v1/analytics/graphs/cost`) | **403**: the course key has no analytics permission. |
| Portkey logs API (`/v1/logs`) | **403**: forbidden. |
| Course materials | The professor's class slide (prices above). |

No authoritative source found so far contradicts the class reference prices. If one turns up (an instructor note or a provider price page), record it here and keep it separate from the class reference.

## Measured calls

| When (UTC) | Purpose | Model (served) | Input | Cached | Output | Reasoning | Latency | Estimated cost (reference price) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-10-25 14:26 | Health check from the dashboard | `gpt-6-luna` (`gpt-6-luna-global`) | 11 | 0 | 5 | 0 | 3,026 ms | $0.0000036 |
| 2026-10-25 14:31 | Health check during the fresh-clone rehearsal | `gpt-6-luna` (`gpt-6-luna-global`) | 11 | 0 | 5 | 0 | 1,399 ms | $0.0000036 |

Milestone 2 (Nutrition Core) makes **no** model calls. Search, barcode lookup, logging and all nutrition math are deterministic code, so nutrition logging costs $0 in tokens.

## Agent runs (Milestone 4, measured)

Six-question live evaluation (runs 1–6, 2026-10-26), plus one separate injection-defense run (#7). Full per-call data is in `docs/evidence/m4_live_runs.json`, and the summary is in `docs/milestone4.md`.

- **Tokens (runs 1–6):** 12,675 input (including 6,690 cache-write, 0 cache reads) and 1,115 output (including reasoning tokens).
- **Estimated cost (runs 1–6):** $0.00199 in total, or **$0.00033 per question** on average at the reference prices.
- **Prompt caching:** the provider reported no cache reads on any call, but cache-write tokens on the last call of runs 1–5.
- **Run 7 (separate):** 1,315 input / 215 output tokens, $0.000239.
- **How costs are calculated:** each call is priced as (input − cached − cache write) × $0.10 + cached × $0.01 + cache write × $0.125 + output × $0.50 per 1M tokens. Calls without usage are stored as `usage_reported = false`, with no estimate.

