"""Cost-optimisation experiment: deterministic keyword routing vs. a gpt-6-luna routing call.

Runs each question through both routers, records the model router's real token usage, and
writes docs/evidence/router_experiment.json. Needs PORTKEY_API_KEY (makes ~10 tiny model calls).

    python scripts/router_experiment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model import LunaModel  # noqa: E402
from app.agents.router import ROUTER_INSTRUCTIONS, keyword_route, parse_route  # noqa: E402
from app.ai.pricing import estimate_cost_usd  # noqa: E402

# (question, expected workflow) - expected labels set by the author before running
QUESTIONS = [
    ("How am I doing against my protein goal?", "nutrition"),
    ("Which days did I fall outside my protein range?", "nutrition"),
    ("What's a good alternative to barbell squats for me?", "training"),
    ("Can you build me a 45 minute upper body workout?", "training"),
    ("I've trained consistently this week, but I'm struggling to hit my protein goal. What could I change?", "progress"),
    ("What foods contribute most to my protein intake?", "nutrition"),
    ("How is my overall progress this month?", "progress"),
    ("Should I eat more on the days I lift?", "progress"),
    ("Is my plan working?", "progress"),
    ("What should I have for dinner tonight?", "nutrition"),
]


def main() -> int:
    model = LunaModel()
    rows = []
    for q, expected in QUESTIONS:
        kw = keyword_route(q)
        r = model.respond(ROUTER_INSTRUCTIONS, [{"role": "user", "content": q}], [])
        u = r.usage
        cost = estimate_cost_usd(model.name, u.input_tokens or 0, u.cached_input_tokens or 0, u.cache_write_tokens or 0, u.output_tokens or 0)
        rows.append({"question": q, "expected": expected, "keyword_route": kw, "model_route": parse_route(r.text),
                     "model_raw": r.text.strip()[:20], "input_tokens": u.input_tokens, "cached_input_tokens": u.cached_input_tokens,
                     "output_tokens": u.output_tokens, "reasoning_tokens": u.reasoning_tokens, "estimated_cost_usd": cost,
                     "latency_ms": r.latency_ms})
        print(rows[-1])
    summary = {
        "questions": len(rows),
        "keyword_routed": sum(1 for r in rows if r["keyword_route"]),
        "keyword_correct_when_routed": sum(1 for r in rows if r["keyword_route"] and r["keyword_route"] == r["expected"]),
        "model_correct": sum(1 for r in rows if r["model_route"] == r["expected"]),
        "model_total_tokens": sum((r["input_tokens"] or 0) + (r["output_tokens"] or 0) for r in rows),
        "model_total_cost_usd": round(sum(r["estimated_cost_usd"] or 0 for r in rows), 8),
        "model_avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows)),
        "price_source": "MGT 409 class slide reference prices",
    }
    out = ROOT / "docs" / "evidence" / "router_experiment.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
