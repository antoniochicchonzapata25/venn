"""AI Coach API: ask a question, list runs, inspect a run trace, see usage totals and deterministic metrics.

Without an API key the coach reports "disabled"; everything else in Venn keeps working.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.model import LunaModel, ModelError
from app.agents.runner import DAILY_RUN_LIMIT, run_coach, runs_today
from app.agents.tools import AgentContext, get_progress_metrics
from app.ai.pricing import PRICE_SOURCE, REFERENCE_PRICES
from app.config import get_settings
from app.db import get_db
from app.models import AgentRun, AiUsage, User
from app.security import current_user

router = APIRouter(prefix="/api/coach", tags=["coach"])


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)
    workflow: str | None = Field(default=None, pattern="^(auto|nutrition|training|progress)$")
    local_date: date | None = None  # the user's local date (defaults to the server's)
    tz_offset: int | None = Field(default=None, ge=-900, le=900)

    @field_validator("question")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = "".join(ch for ch in v if ch.isprintable()).strip()
        if len(v) < 3:
            raise ValueError("please ask a question")
        return v


def run_out(r: AgentRun, detail: bool = False) -> dict:
    out = {
        "id": r.id, "question": r.question, "workflow": r.workflow, "routed_by": r.routed_by, "status": r.status,
        "answer": r.answer, "error": r.error, "model": r.model, "model_calls": r.model_calls, "tool_calls": r.tool_calls,
        "usage": {"input_tokens": r.input_tokens, "cached_input_tokens": r.cached_input_tokens,
                  "output_tokens": r.output_tokens, "reasoning_tokens": r.reasoning_tokens, "complete": r.usage_complete},
        "estimated_cost_usd": r.estimated_cost_usd, "latency_ms": r.latency_ms, "checks": r.checks,
        "tools_used": [s["tool"] for s in r.trace if s.get("step") == "tool_call"],
        "created_at": r.created_at.isoformat() if r.created_at else None, "price_source": PRICE_SOURCE,
    }
    if detail:
        out["trace"] = r.trace
    return out


@router.get("/status")
def coach_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    return {"enabled": s.ai_configured, "model": s.model_name, "runs_today": runs_today(db, user.id), "daily_limit": DAILY_RUN_LIMIT,
            "message": None if s.ai_configured else "The AI Coach is unavailable because no API key is configured. "
                                                     "Nutrition, training and your numbers below still work."}


@router.post("/ask")
def ask(body: AskIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not get_settings().ai_configured:
        return {"status": "disabled", "message": "The AI Coach is unavailable because no API key is configured."}
    if runs_today(db, user.id) >= DAILY_RUN_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Daily AI Coach limit reached ({DAILY_RUN_LIMIT} questions).")
    factory = getattr(request.app.state, "coach_model_factory", None) or LunaModel
    try:
        model = factory()
    except ModelError as error:
        return {"status": "error", "message": str(error)}
    forced = None if body.workflow in (None, "auto") else body.workflow
    run = run_coach(db, user.id, body.question, model, body.local_date or date.today(), body.tz_offset, forced)
    return run_out(run, detail=True)


@router.get("/runs")
def list_runs(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(AgentRun).where(AgentRun.user_id == user.id).order_by(AgentRun.id.desc()).limit(20))
    return {"runs": [run_out(r) for r in rows]}


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    r = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user.id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found.")
    out = run_out(r, detail=True)
    out["model_calls_detail"] = [
        {"purpose": u.purpose, "status": u.status, "served_model": u.served_model, "usage_reported": u.usage_reported,
         "input_tokens": u.input_tokens if u.usage_reported else None,
         "cached_input_tokens": u.cached_input_tokens if u.usage_reported else None,
         "cache_write_tokens": u.cache_write_tokens if u.usage_reported else None,
         "output_tokens": u.output_tokens if u.usage_reported else None,
         "reasoning_tokens": u.reasoning_tokens if u.usage_reported else None,
         "estimated_cost_usd": u.estimated_cost_usd, "latency_ms": u.latency_ms,
         "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in db.scalars(select(AiUsage).where(AiUsage.run_id == r.id, AiUsage.user_id == user.id).order_by(AiUsage.id))]
    return out


@router.get("/usage")
def usage(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(AgentRun.workflow, func.count(), func.sum(AgentRun.input_tokens), func.sum(AgentRun.cached_input_tokens),
               func.sum(AgentRun.output_tokens), func.sum(AgentRun.estimated_cost_usd))
        .where(AgentRun.user_id == user.id, AgentRun.status == "ok").group_by(AgentRun.workflow)).all()
    return {"price_source": PRICE_SOURCE, "reference_prices_per_million": REFERENCE_PRICES[get_settings().model_name],
            "by_workflow": [{"workflow": w, "runs": n, "input_tokens": i or 0, "cached_input_tokens": c or 0,
                             "output_tokens": o or 0, "estimated_cost_usd": round(cost or 0, 8),
                             "average_cost_per_run_usd": round((cost or 0) / n, 8) if n else None} for w, n, i, c, o, cost in rows],
            "note": "Token counts are measured from API responses; costs are estimates at the reference prices."}


@router.get("/metrics")
def metrics(day: date | None = None, tz_offset: int | None = None, user: User = Depends(current_user),
            db: Session = Depends(get_db)) -> dict:
    """Deterministic metrics (no AI): the same numbers the Progress Coach receives."""
    ctx = AgentContext(db=db, user_id=user.id, today=day or date.today(), tz_offset=tz_offset)
    return get_progress_metrics(ctx, {"days": 7})
