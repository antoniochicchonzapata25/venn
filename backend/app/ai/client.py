"""The single place Venn talks to the model provider (Portkey -> OpenAI, gpt-6-luna only).

Milestone 1 only needs a connection check. Agents (Phase 5) will reuse
`build_openai_client()` through PydanticAI's OpenAIResponsesModel, as in HW5.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI

from app.config import AI_TIMEOUT_SECONDS, PORTKEY_BASE_URL, get_settings


class AiNotConfigured(RuntimeError):
    """PORTKEY_API_KEY is missing, so AI features are disabled."""


@dataclass
class AiCallResult:
    status: str  # "ok" | "error"
    model: str
    served_model: str | None = None
    latency_ms: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    message: str = ""


def build_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.ai_configured:
        raise AiNotConfigured("PORTKEY_API_KEY is not set. Add it to .env (see .env.example).")
    return OpenAI(
        api_key=settings.portkey_api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
        timeout=AI_TIMEOUT_SECONDS,
        max_retries=0,
    )


def check_connection() -> AiCallResult:
    """One tiny Responses API call. Never raises for provider errors; never includes the key."""
    model = get_settings().model_name
    client = build_openai_client()
    started = time.perf_counter()
    try:
        response = client.responses.create(
            model=model, input="Reply with exactly: ok", max_output_tokens=16, store=False,
        )
    except AuthenticationError:
        return AiCallResult("error", model, message="The provider rejected the API key.")
    except APIConnectionError:
        return AiCallResult("error", model, message="Could not reach the AI provider.")
    except APIError as error:
        code = getattr(error, "status_code", None) or "API error"
        return AiCallResult("error", model, message=f"The AI provider returned {code}.")
    except Exception as error:  # noqa: BLE001 - the app must keep running if the provider misbehaves
        return AiCallResult("error", model, message=f"AI check failed ({type(error).__name__}).")
    latency = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    in_details = getattr(usage, "input_tokens_details", None)
    out_details = getattr(usage, "output_tokens_details", None)
    return AiCallResult(
        status="ok",
        model=model,
        served_model=getattr(response, "model", None),
        latency_ms=latency,
        input_tokens=usage.input_tokens if usage else 0,
        cached_input_tokens=(getattr(in_details, "cached_tokens", 0) or 0) if in_details else 0,
        cache_write_tokens=(getattr(in_details, "cache_write_tokens", 0) or 0) if in_details else 0,
        output_tokens=usage.output_tokens if usage else 0,
        reasoning_tokens=(getattr(out_details, "reasoning_tokens", 0) or 0) if out_details else 0,
    )
