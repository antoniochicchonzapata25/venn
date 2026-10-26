"""Health checks. `GET /api/health` never calls the model; the live AI check needs a login."""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.pricing import PRICE_SOURCE, estimate_cost_usd
from app.branding import APP_NAME, APP_VERSION
from app.config import get_settings
from app.db import get_db
from app.models import AiUsage, User
from app.security import current_user

router = APIRouter(prefix="/api/health", tags=["health"])

AI_CHECK_CACHE_SECONDS = 600
_cache_lock = threading.Lock()


def ai_status() -> dict:
    settings = get_settings()
    return {
        "configured": settings.ai_configured,
        "model": settings.model_name,
        "provider": "portkey",
        "message": None if settings.ai_configured else "AI features are disabled: PORTKEY_API_KEY is not set.",
    }


@router.get("")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report, don't crash the health check
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "app": APP_NAME, "version": APP_VERSION, "database": database, "ai": ai_status(),
    }


@router.post("/ai")
def check_ai(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Live connection test (one tiny model call), cached for 10 minutes to protect the budget."""
    base = ai_status()
    if not base["configured"]:
        return {**base, "status": "disabled", "cached": False}

    state = request.app.state
    with _cache_lock:
        cached = getattr(state, "ai_check_cache", None)
        if cached and time.monotonic() - cached[0] < AI_CHECK_CACHE_SECONDS:
            return {**base, **cached[1], "cached": True}

        result = ai_client.check_connection()
        db.add(AiUsage(
            user_id=user.id, purpose="health_check", model=result.model, served_model=result.served_model,
            status=result.status, input_tokens=result.input_tokens, cached_input_tokens=result.cached_input_tokens,
            cache_write_tokens=result.cache_write_tokens,
            output_tokens=result.output_tokens, reasoning_tokens=result.reasoning_tokens, latency_ms=result.latency_ms,
        ))
        db.commit()
        payload = {
            "status": result.status, "served_model": result.served_model, "latency_ms": result.latency_ms,
            "usage": {
                "input_tokens": result.input_tokens, "cached_input_tokens": result.cached_input_tokens,
                "cache_write_tokens": result.cache_write_tokens,
                "output_tokens": result.output_tokens, "reasoning_tokens": result.reasoning_tokens,
            },
            "estimated_cost_usd": estimate_cost_usd(result.model, result.input_tokens, result.cached_input_tokens,
                                                    result.cache_write_tokens, result.output_tokens),
            "price_source": PRICE_SOURCE,
            "message": result.message or None,
        }
        if result.status == "ok":
            state.ai_check_cache = (time.monotonic(), payload)
    return {**base, **payload, "cached": False}
