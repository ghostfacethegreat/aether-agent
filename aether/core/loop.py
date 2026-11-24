import inspect
import json
import os
import threading
import time
from dataclasses import dataclass, field

from aether.errors import AetherError, ContextOverflow, ProviderError
from aether.providers.catalog import provider_is_billable, rough_cost
from aether.utils import estimate_tokens, message_tokens, parse_bool, redact, truncate, utc_now


def new_usage() -> dict:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_chars": 0,
        "estimated_cost": 0.0,
        "priced_calls": 0,
        "unpriced_calls": 0,
        "cost_known": False,
        "preflight_estimate_usd": 0.0,
    }


def new_spend_budget(limit: float | None = None) -> dict:
    return {
        "spent": 0.0,
        "reserved": 0.0,
        "limit": limit,
        "lock": threading.Lock(),
        "usage": new_usage(),
    }


@dataclass
class TurnState:
    messages: list
    system_prompt: str
    tools: list
    provider_candidates: list
    provider_manager: object
    context_manager: object
    executor: object
    config: object
    session_id: str = ""
    max_iterations: int = 12
    on_delta: object = None
    on_status: object = None
    new_messages: list = field(default_factory=list)
    tool_log: list = field(default_factory=list)
    usage: dict = field(default_factory=new_usage)
    final_text: str = ""
    exit_reason: str = ""
    error: str = ""
    plan: str = ""
    execution_plan: object = None
    spend_budget: dict = field(default_factory=lambda: new_spend_budget())
    cancel_event: threading.Event = field(default_factory=threading.Event)
    routing_decision: dict = field(default_factory=dict)
    task_requirements: dict = field(default_factory=dict)
    context_recovery: list = field(default_factory=list)
    verification: dict = field(default_factory=lambda: {"status": "unverified", "sources": [], "model_claim": ""})
    started_at: float = field(default_factory=time.monotonic)
    turn_limit: float | None = None

    def status(self, kind: str, **payload) -> None:
        if self.on_status:
            self.on_status({"kind": kind, "at": utc_now(), **payload})


def _as_tool_call(call) -> dict:
    return {
        "id": getattr(call, "id", "") or "",
        "type": "function",
        "function": {
            "name": getattr(call, "name", ""),
            "arguments": getattr(call, "raw_arguments", "") or json.dumps(getattr(call, "arguments", {}) or {}),
        },
    }


def _options(state: TurnState) -> dict:
    return {
        "temperature": state.config.get("temperature", 0.2),
        "max_tokens": state.config.get("max_tokens", 2048),
        "top_p": state.config.get("top_p", 1.0),
        "reasoning_effort": state.config.get("reasoning_effort"),
    }


def _paid_not_confirmed(state: TurnState) -> bool:
    env = os.environ.get("AETHER_CONFIRM_PAID")
    if env is not None:
        return not parse_bool(env, False)
    raw = state.config.get("costs.confirm_paid")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return True


def _cost_limit(state: TurnState) -> float | None:
    raw = state.config.get("costs.max_estimated_usd_per_turn")
    try:
        configured = None if raw is None else float(raw)
    except (TypeError, ValueError) as exc:
        raise AetherError("costs.max_estimated_usd_per_turn must be a number") from exc
    inherited = state.spend_budget.get("limit")
    if configured is None:
        limit = inherited
    elif inherited is None:
        limit = configured
    else:
        limit = min(configured, inherited)
    with state.spend_budget["lock"]:
        current = state.spend_budget.get("limit")
        state.spend_budget["limit"] = limit if current is None else (min(current, limit) if limit is not None else current)
        shared_limit = state.spend_budget["limit"]
    turn_limit = state.turn_limit
    if turn_limit is None:
        return shared_limit
    try:
        turn_limit = float(turn_limit)
    except (TypeError, ValueError) as exc:
        raise AetherError("turn cost limit must be a number") from exc
    if shared_limit is None:
        return turn_limit
    return min(shared_limit, turn_limit)


def _over_cost_limit(state: TurnState) -> bool:
    limit = _cost_limit(state)
    return limit is not None and float(state.spend_budget["spent"]) >= limit


def _sync_usage(state: TurnState) -> None:
    for key, value in new_usage().items():
        state.usage.setdefault(key, value)
    state.usage["cost_known"] = state.usage.get("unpriced_calls", 0) == 0 and state.usage.get("priced_calls", 0) > 0


def _preflight_cost(state: TurnState, provider) -> tuple[float | None, float]:
    if provider_is_billable(provider.name, provider.model) and _paid_not_confirmed(state):
        raise ProviderError(
            f"Paid provider '{provider.name}' is not confirmed. Use --confirm-paid or set costs.confirm_paid=false.",
            provider=provider.name,
            retryable=False,
        )
    limit = _cost_limit(state)
    prompt_tokens = message_tokens(state.messages) + message_tokens([{"content": state.tools}])
    estimate = rough_cost(
        provider.name,
        provider.model,
        {"prompt_tokens": int(prompt_tokens * 1.25), "completion_tokens": int(_options(state).get("max_tokens") or 0)},
    )
    if estimate is None:
        if limit is not None:
            raise AetherError(
                f"Cannot enforce costs.max_estimated_usd_per_turn={limit:.6f} for unpriced model "
                f"'{provider.name}/{provider.model}'. Add pricing or remove the cap."
            )
        return None, 0.0
    attempts = max(1, int(state.config.get("retry_attempts", 2) or 0) + 1)
    reservation = round(estimate * attempts, 6)
    with state.spend_budget["lock"]:
        budget = state.spend_budget
        projected = budget["spent"] + budget["reserved"] + reservation
        if limit is not None and projected > limit:
            raise AetherError(
                f"Estimated worst-case cost ${projected:.6f} exceeds costs.max_estimated_usd_per_turn={limit:.6f}. "
                "Reduce max_tokens, lower the limit guard, or use a local provider."
            )
        budget["reserved"] += reservation
    state.usage["preflight_estimate_usd"] = state.usage.get("preflight_estimate_usd", 0.0) + estimate
    return estimate, reservation


def _release_reservation(state: TurnState, reservation: float) -> None:
    if reservation <= 0:
        return
    with state.spend_budget["lock"]:
        state.spend_budget["reserved"] = max(0.0, state.spend_budget["reserved"] - reservation)


def _mark_failed(state: TurnState, provider, seconds: float, reason: str) -> None:
    manager = state.provider_manager
    try:
        accepts_reason = "reason" in inspect.signature(manager.mark_failed).parameters
    except (TypeError, ValueError):
        accepts_reason = False
    if accepts_reason:
        manager.mark_failed(provider.name, seconds, reason)
    else:
        manager.mark_failed(provider.name, seconds)
    reasons = getattr(manager, "_failure_reason", None)
    if isinstance(reasons, dict) and reason:
        reasons[provider.name] = reason[:500]


def _recover_context(state: TurnState, provider, error: str) -> dict:
    before = message_tokens(state.messages)
    preserved = [dict(item) for item in state.messages if item.get("role") == "tool" and item.get("tool_call_id")]
    try:
        supports_provider = "provider" in inspect.signature(state.context_manager.fit).parameters
    except (TypeError, ValueError):
        supports_provider = False
    if supports_provider:
        state.messages, fit = state.context_manager.fit(
            state.messages,
            provider=provider.name,
            model=provider.model,
            force=True,
        )
    else:
        state.messages, fit = state.context_manager.fit(state.messages)
    fitted_tool = {
        str(item.get("tool_call_id") or ""): item
        for item in state.messages
        if item.get("role") == "tool" and item.get("tool_call_id")
    }
    fitted_calls = set()
    for item in state.messages:
        if item.get("role") != "assistant":
            continue
        for call in item.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("id"):
                fitted_calls.add(str(call["id"]))
    max_tool_chars = int(state.config.get("tools.max_result_chars", 16000) or 16000)
    limit = int(fit.get("limit") or state.config.get("context_tokens", 8192) or 8192)
    remaining = max(0, limit - message_tokens(state.messages))

    def fit_content(raw: str, token_budget: int) -> str:
        char_limit = max_tool_chars
        content = truncate(raw, char_limit)
        while content and estimate_tokens(content) > token_budget and char_limit > 0:
            overage = estimate_tokens(content) - token_budget
            char_limit = max(0, char_limit - (overage * 4 + 40))
            content = truncate(raw, char_limit) if char_limit else ""
        return content

    restored = 0
    for item in preserved:
        call_id = str(item.get("tool_call_id") or "")
        if call_id not in fitted_calls:
            continue
        raw = str(item.get("content") or "")
        target = fitted_tool.get(call_id)
        if target is not None:
            existing = str(target.get("content") or "")
            allowance = remaining + estimate_tokens(existing)
            content = fit_content(raw, allowance)
            delta = max(0, estimate_tokens(content) - estimate_tokens(existing))
            if delta > remaining:
                continue
            target["content"] = content
            remaining -= delta
            if content != existing:
                restored += 1
            continue
        allowance = max(0, remaining - 4)
        content = fit_content(raw, allowance)
        delta = message_tokens([{**item, "content": content}])
        if delta > remaining:
            continue
        state.messages.append({**item, "content": content})
        remaining -= delta
        restored += 1
    recovery = {
        "provider": provider.name,
        "model": provider.model,
        "error": redact(error),
        "tokens_before": before,
        "tokens_after": message_tokens(state.messages),
        "removed": int(fit.get("removed") or 0),
        "repaired": int(fit.get("repaired") or 0),
        "restored_tool_results": restored,
    }
    state.context_recovery.append(recovery)
    state.status("context_recovered", **recovery)
    if state.on_delta:
        state.on_delta("\n[context compressed after overflow]\n", "status")
    return recovery


def _call_provider(state: TurnState, iteration: int):
    errors = []
    for index, provider in enumerate(state.provider_candidates):
        state.status("provider_call", provider=provider.name, model=provider.model, iteration=iteration)
        reservation = 0.0
        for attempt in (0, 1):
            try:
                _, reservation = _preflight_cost(state, provider)
                response = provider.chat(
                    state.messages,
                    tools=state.tools,
                    stream=bool(state.config.get("streaming", True)),
                    on_delta=state.on_delta,
                    options=_options(state),
                )
                state.usage["provider"] = provider.name
                state.usage["model"] = provider.model
                return response, provider, reservation
            except ContextOverflow as exc:
                _release_reservation(state, reservation)
                reservation = 0.0
                message = redact(str(exc))
                errors.append(f"{provider.name}: {message}")
                retrying = attempt == 0 and len(state.context_recovery) < 2
                state.status("context_overflow", provider=provider.name, error=message, retrying=retrying)
                if retrying:
                    _recover_context(state, provider, message)
                    continue
                _mark_failed(state, provider, 60, message)
                next_provider = next(iter(state.provider_candidates[index + 1 :]), None)
                if next_provider is not None:
                    state.status(
                        "routing_fallback",
                        **{"from": provider.name, "to": next_provider.name, "reason": message},
                    )
                break
            except ProviderError as exc:
                _release_reservation(state, reservation)
                reservation = 0.0
                message = redact(str(exc))
                errors.append(f"{provider.name}: {message}")
                state.status("provider_error", provider=provider.name, error=message, retryable=exc.retryable)
                _mark_failed(state, provider, 30 if exc.retryable else 300, message)
                next_provider = next(iter(state.provider_candidates[index + 1 :]), None)
                if next_provider is not None:
                    state.status(
                        "routing_fallback",
                        **{"from": provider.name, "to": next_provider.name, "reason": message},
                    )
                if state.on_delta:
                    state.on_delta("\n[provider switched after error]\n", "status")
                break
            except Exception:
                _release_reservation(state, reservation)
                raise
    raise AetherError("All providers failed. " + " | ".join(errors))


def _accumulate_usage(state: TurnState, response, provider, reservation: float = 0.0) -> None:
    usage = response.usage or {}
    if "prompt_tokens" in usage:
        prompt = int(usage.get("prompt_tokens") or 0)
    else:
        prompt = int(usage.get("input_tokens") or 0)
        prompt += int(usage.get("cache_read_input_tokens") or 0)
        prompt += int(usage.get("cache_creation_input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    reasoning = len(response.reasoning) if response.reasoning else 0
    cost = rough_cost(provider.name, provider.model, usage)
    with state.spend_budget["lock"]:
        budget = state.spend_budget
        budget["reserved"] = max(0.0, budget["reserved"] - reservation)
        shared = budget["usage"]
        for key, value in new_usage().items():
            shared.setdefault(key, value)
        shared["prompt_tokens"] += prompt
        shared["completion_tokens"] += completion
        shared["reasoning_chars"] += reasoning
        if cost is None:
            shared["unpriced_calls"] += 1
        else:
            shared["priced_calls"] += 1
            shared["estimated_cost"] = round(float(shared["estimated_cost"]) + cost, 6)
            budget["spent"] = shared["estimated_cost"]
    for key, value in (("prompt_tokens", prompt), ("completion_tokens", completion), ("reasoning_chars", reasoning)):
        state.usage[key] = int(state.usage.get(key, 0)) + value
    if cost is None:
        state.usage["unpriced_calls"] = int(state.usage.get("unpriced_calls", 0)) + 1
    else:
        state.usage["priced_calls"] = int(state.usage.get("priced_calls", 0)) + 1
        state.usage["estimated_cost"] = round(float(state.usage.get("estimated_cost", 0.0)) + cost, 6)
    _sync_usage(state)


def _mark_cancelled(state: TurnState) -> TurnState:
    _sync_usage(state)
    state.exit_reason = "cancelled"
    state.final_text = "Stopped: task was cancelled."
    assistant = {"role": "assistant", "content": state.final_text}
    state.messages.append(assistant)
    state.new_messages.append(assistant)
    return state


def run_turn_loop(state: TurnState) -> TurnState:
    for iteration in range(1, max(1, int(state.max_iterations)) + 1):
        if state.cancel_event.is_set():
            return _mark_cancelled(state)
        decision = state.routing_decision or {}
        try:
            supports_provider = "provider" in inspect.signature(state.context_manager.fit).parameters
        except (TypeError, ValueError):
            supports_provider = False
        if supports_provider:
            state.messages, fit = state.context_manager.fit(
                state.messages,
                provider=str(decision.get("provider") or "") or None,
                model=str(decision.get("model") or "") or None,
            )
        else:
            state.messages, fit = state.context_manager.fit(state.messages)
        if fit.get("changed"):
            state.status("context_compressed", **fit)
        try:
            response, provider, reservation = _call_provider(state, iteration)
        except AetherError as exc:
            _sync_usage(state)
            state.error = str(exc)
            state.exit_reason = "provider_error"
            state.final_text = f"I could not get a model response. {exc}"
            return state
        _accumulate_usage(state, response, provider, reservation)
        state.status("model_response", provider=provider.name, tool_calls=len(response.tool_calls), finish_reason=response.finish_reason)
        if state.cancel_event.is_set():
            return _mark_cancelled(state)
        if _over_cost_limit(state):
            _sync_usage(state)
            state.status("cost_limit", estimated_cost=state.usage.get("estimated_cost", 0.0), limit=_cost_limit(state))
            state.exit_reason = "cost_limit"
            state.final_text = (
                f"Stopped: estimated cost ${state.usage.get('estimated_cost', 0.0):.6f} reached the configured "
                "costs.max_estimated_usd_per_turn limit."
            )
            assistant = {"role": "assistant", "content": state.final_text}
            state.messages.append(assistant)
            state.new_messages.append(assistant)
            return state

        if response.tool_calls:
            assistant = {
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": [_as_tool_call(call) for call in response.tool_calls],
            }
            state.messages.append(assistant)
            state.new_messages.append(assistant)
            results = state.executor.execute_batch(response.tool_calls)
            for message, execution in results:
                state.messages.append(message)
                state.new_messages.append(message)
                record = execution.as_dict()
                state.tool_log.append(record)
                if state.execution_plan is not None and hasattr(state.execution_plan, "apply_tool_result"):
                    state.execution_plan.apply_tool_result(execution.name, execution.ok, record.get("result") or record.get("error") or "")
            if state.execution_plan is not None and hasattr(state.execution_plan, "summary"):
                state.status("plan_checkpoint", **state.execution_plan.summary())
            if state.cancel_event.is_set():
                return _mark_cancelled(state)
            continue

        final_text = str(response.content or "").strip()
        if not final_text and response.reasoning:
            final_text = str(response.reasoning).strip()
        assistant = {"role": "assistant", "content": final_text}
        state.messages.append(assistant)
        state.new_messages.append(assistant)
        state.final_text = final_text
        state.exit_reason = "complete"
        _sync_usage(state)
        return state

    _sync_usage(state)
    state.exit_reason = "max_iterations"
    state.final_text = state.final_text or "I reached the iteration limit before completing the task. The tool log shows what was done so far."
    state.messages.append({"role": "assistant", "content": state.final_text})
    state.new_messages.append({"role": "assistant", "content": state.final_text})
    return state
