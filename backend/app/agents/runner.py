"""Run one AI Coach request: route, let the chosen agent call its permitted tools, check the answer.

Controls enforced here, in code:
- Only the workflow's allow-listed tools are offered; any other tool name is refused.
- Tool arguments are validated; the user id comes from the session, never from the model.
- At most MAX_MODEL_CALLS model calls and MAX_TOOL_CALLS tool calls per run; a daily per-user run cap.
- Every model call's real token usage is stored (ai_usage) with an estimated cost at reference prices.
- The final answer is checked: numbers must match tool results; named exercises must pass the
  user's equipment/limitation rules. Failures are shown to the user, not hidden.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.model import AgentModel, ModelError, ModelResponse
from app.agents.prompts import instructions_for
from app.agents.router import ROUTER_INSTRUCTIONS, keyword_route, parse_route
from app.agents.safety import check_numbers, collect_numbers, mentioned_exercises
from app.agents.tools import AGENT_TOOLS, TOOLS, AgentContext, ToolArgumentError, _ctx_or_message, validate_args
from app.ai.pricing import estimate_cost_usd
from app.models import AgentRun, AiUsage
from app.services.exercises import catalog
from app.services.workout_rules import check_exercise

MAX_MODEL_CALLS = 6
MAX_TOOL_CALLS = 8
MAX_TOOL_RESULT_CHARS = 6000
DAILY_RUN_LIMIT = 40


def runs_today(db: Session, user_id: int) -> int:
    since = datetime.now(UTC) - timedelta(days=1)
    return db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.user_id == user_id, AgentRun.created_at >= since)) or 0


class Run:
    def __init__(self, db: Session, user_id: int, question: str, model: AgentModel):
        self.db, self.user_id, self.question, self.model = db, user_id, question, model
        self.trace: list[dict] = []
        self.usages: list[AiUsage] = []
        self.started = time.perf_counter()

    def record_call(self, purpose: str, resp: ModelResponse | None, status: str = "ok") -> None:
        u = resp.usage if resp else None
        reported = bool(u and u.reported)
        cost = estimate_cost_usd(self.model.name, u.input_tokens or 0, u.cached_input_tokens or 0, u.cache_write_tokens or 0,
                                 u.output_tokens or 0) if reported else None
        row = AiUsage(user_id=self.user_id, purpose=purpose, model=self.model.name, served_model=resp.served_model if resp else None,
                      status=status, input_tokens=(u.input_tokens or 0) if u else 0,
                      cached_input_tokens=(u.cached_input_tokens or 0) if u else 0,
                      cache_write_tokens=(u.cache_write_tokens or 0) if u else 0,
                      output_tokens=(u.output_tokens or 0) if u else 0, reasoning_tokens=(u.reasoning_tokens or 0) if u else 0,
                      latency_ms=resp.latency_ms if resp else 0, usage_reported=reported, estimated_cost_usd=cost)
        self.usages.append(row)
        self.trace.append({"step": "model_call", "purpose": purpose, "status": status,
                           "input_tokens": row.input_tokens if reported else None,
                           "cached_input_tokens": row.cached_input_tokens if reported else None,
                           "output_tokens": row.output_tokens if reported else None,
                           "reasoning_tokens": row.reasoning_tokens if reported else None,
                           "estimated_cost_usd": cost, "latency_ms": row.latency_ms,
                           "tool_calls_requested": [c["name"] for c in resp.calls] if resp else []})


def route(run: Run, question: str, forced: str | None) -> tuple[str, str]:
    if forced:
        run.trace.append({"step": "router", "method": "user", "workflow": forced})
        return forced, "user"
    wf = keyword_route(question)
    if wf:
        run.trace.append({"step": "router", "method": "keywords", "workflow": wf})
        return wf, "keywords"
    resp = run.model.respond(ROUTER_INSTRUCTIONS, [{"role": "user", "content": question}], [])
    run.record_call("agent:router", resp)
    wf = parse_route(resp.text)
    run.trace.append({"step": "router", "method": "model", "workflow": wf, "raw": resp.text[:20]})
    return wf, "model"


def execute_tool(run: Run, ctx: AgentContext, workflow: str, name: str, raw_args: str) -> tuple[dict, set[float]]:
    allowed = AGENT_TOOLS[workflow]
    if name not in allowed or name not in TOOLS:
        run.trace.append({"step": "tool_rejected", "tool": name, "reason": f"not permitted for the {workflow} agent"})
        return {"error": f"Tool '{name}' is not available to this agent."}, set()
    try:
        args = validate_args(TOOLS[name], json.loads(raw_args or "{}"))
        result = TOOLS[name].handler(ctx, args)
    except (ToolArgumentError, json.JSONDecodeError) as error:
        run.trace.append({"step": "tool_rejected", "tool": name, "reason": str(error)})
        return {"error": f"Invalid arguments: {error}"}, set()
    run.trace.append({"step": "tool_call", "tool": name, "args": args, "ok": "error" not in result,
                      "result_keys": sorted(result)[:8]})
    return result, collect_numbers(result)


def answer_checks(ctx: AgentContext, workflow: str, answer: str, facts: set[float], question: str) -> dict:
    g = check_numbers(answer, facts, question)
    checks = {"numbers_checked": g.checked, "numbers_verified": g.verified, "unverified_numbers": g.unverified,
              "grounded": g.ok, "untrusted_text_flags": sorted(set(ctx.flags))}
    names = {e.name.lower(): e.id for e in catalog().values()}
    mentioned = mentioned_exercises(answer, names)
    conflicts = []
    if mentioned:
        tctx = _ctx_or_message(ctx)
        if not isinstance(tctx, str):
            for ex_id in mentioned:
                c = check_exercise(catalog()[ex_id], tctx[0], enforce_level=False)
                if not c.ok:
                    conflicts.append({"exercise": catalog()[ex_id].name, "reasons": c.reasons})
    checks["exercises_mentioned"] = [catalog()[i].name for i in mentioned]
    checks["exercise_conflicts"] = conflicts
    return checks


def run_coach(db: Session, user_id: int, question: str, model: AgentModel, today: date,
              tz_offset: int | None = None, forced_workflow: str | None = None) -> AgentRun:
    run = Run(db, user_id, question, model)
    ctx = AgentContext(db=db, user_id=user_id, today=today, tz_offset=tz_offset)
    agent_run = AgentRun(user_id=user_id, question=question[:500], workflow="?", routed_by="?", status="error", model=model.name)
    facts: set[float] = set()
    tool_calls = 0
    try:
        workflow, routed_by = route(run, question, forced_workflow)
        agent_run.workflow, agent_run.routed_by = workflow, routed_by
        tools = [TOOLS[n].spec() for n in AGENT_TOOLS[workflow]]
        instructions = instructions_for(workflow, today.isoformat())
        items: list[dict] = [{"role": "user", "content": question}]
        answer = None
        for step in range(MAX_MODEL_CALLS):
            resp = model.respond(instructions, items, tools)
            run.record_call(f"agent:{workflow}", resp)
            if not resp.calls:
                answer = resp.text.strip()
                break
            items += resp.items
            for call in resp.calls:
                tool_calls += 1
                if tool_calls > MAX_TOOL_CALLS:
                    result, nums = {"error": "Tool-call limit reached; answer with the data you have."}, set()
                    run.trace.append({"step": "tool_rejected", "tool": call["name"], "reason": "tool-call limit"})
                else:
                    result, nums = execute_tool(run, ctx, workflow, call["name"], call["arguments"])
                facts |= nums
                items.append({"type": "function_call_output", "call_id": call["call_id"],
                              "output": json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS]})
        if answer:
            agent_run.status, agent_run.answer = "ok", answer
            agent_run.checks = answer_checks(ctx, workflow, answer, facts, question)
            run.trace.append({"step": "validation", **agent_run.checks})
        else:
            agent_run.status, agent_run.error = "limit", "The coach reached its step limit without an answer. Please ask a narrower question."
    except ModelError as error:
        run.record_call(f"agent:{agent_run.workflow}", None, status="error")
        agent_run.status, agent_run.error = "error", str(error)
    agent_run.trace = run.trace
    agent_run.tool_calls = tool_calls
    agent_run.model_calls = len(run.usages)
    agent_run.input_tokens = sum(u.input_tokens for u in run.usages)
    agent_run.cached_input_tokens = sum(u.cached_input_tokens for u in run.usages)
    agent_run.output_tokens = sum(u.output_tokens for u in run.usages)
    agent_run.reasoning_tokens = sum(u.reasoning_tokens for u in run.usages)
    agent_run.usage_complete = all(u.usage_reported for u in run.usages)
    agent_run.estimated_cost_usd = round(sum(u.estimated_cost_usd or 0 for u in run.usages), 8)
    agent_run.latency_ms = int((time.perf_counter() - run.started) * 1000)
    db.add(agent_run)
    db.flush()
    for u in run.usages:
        u.run_id = agent_run.id
        db.add(u)
    db.commit()
    return agent_run
