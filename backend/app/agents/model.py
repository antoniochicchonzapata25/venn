"""A thin, swappable model interface. Production uses gpt-6-luna via Portkey (Responses API);
tests use a scripted fake. No other model is ever used."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from app.ai.client import build_openai_client
from app.config import get_settings

AGENT_TIMEOUT_SECONDS = 30
MAX_OUTPUT_TOKENS = 900


@dataclass
class Usage:
    input_tokens: int | None
    cached_input_tokens: int | None
    cache_write_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None

    @property
    def reported(self) -> bool:
        return self.input_tokens is not None and self.output_tokens is not None


@dataclass
class ModelResponse:
    items: list[dict]  # output items as dicts (function_call / message / reasoning)
    text: str
    usage: Usage
    served_model: str | None = None
    latency_ms: int = 0
    calls: list[dict] = field(default_factory=list)  # function calls: {call_id, name, arguments}


class ModelError(RuntimeError):
    """The model call failed (timeout, provider error). Carries a user-safe message."""


class AgentModel(Protocol):
    name: str

    def respond(self, instructions: str, input_items: list[dict], tools: list[dict]) -> ModelResponse: ...


def _usage(u) -> Usage:  # noqa: ANN001
    if u is None:
        return Usage(None, None, None, None, None)
    ind = getattr(u, "input_tokens_details", None)
    outd = getattr(u, "output_tokens_details", None)
    return Usage(getattr(u, "input_tokens", None), getattr(ind, "cached_tokens", None) if ind else None,
                 getattr(ind, "cache_write_tokens", None) if ind else None, getattr(u, "output_tokens", None),
                 getattr(outd, "reasoning_tokens", None) if outd else None)


class LunaModel:
    """gpt-6-luna through the course Portkey gateway. Stateless (store=False): the runner resends items."""

    def __init__(self) -> None:
        self.name = get_settings().model_name  # always "gpt-6-luna"
        self.client = build_openai_client().with_options(timeout=AGENT_TIMEOUT_SECONDS, max_retries=0)

    def respond(self, instructions: str, input_items: list[dict], tools: list[dict]) -> ModelResponse:
        started = time.perf_counter()
        try:
            r = self.client.responses.create(model=self.name, instructions=instructions, input=input_items,
                                             tools=tools or None, store=False, max_output_tokens=MAX_OUTPUT_TOKENS)
        except Exception as error:  # noqa: BLE001 - timeouts and provider errors become a safe message
            kind = "timed out" if "timeout" in type(error).__name__.lower() else f"failed ({type(error).__name__})"
            raise ModelError(f"The AI service {kind}. Your data is unchanged; please try again.") from error
        items = [o.model_dump(exclude_none=True) for o in r.output]
        calls = [{"call_id": o.call_id, "name": o.name, "arguments": o.arguments} for o in r.output if o.type == "function_call"]
        return ModelResponse(items=items, text=r.output_text or "", usage=_usage(r.usage), served_model=getattr(r, "model", None),
                             latency_ms=int((time.perf_counter() - started) * 1000), calls=calls)
