import json
from dataclasses import dataclass, field

from aether.errors import AetherError, ProviderError
from aether.utils import redact, utc_now


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
    usage: dict = field(default_factory=dict)
    final_text: str = ""
    exit_reason: str = ""
    error: str = ""
    plan: str = ""

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
        "reasoning_effort": state.config.get("reasoning_effort"),
    }


def _call_provider(state: TurnState, iteration: int):
    errors = []
    for provider in state.provider_candidates:
        state.status("provider_call", provider=provider.name, model=provider.model, iteration=iteration)
        try:
            return provider.chat(
                state.messages,
                tools=state.tools,
                stream=bool(state.config.get("streaming", True)),
                on_delta=state.on_delta,
                options=_options(state),
            ), provider
        except ProviderError as exc:
            message = redact(str(exc))
            errors.append(f"{provider.name}: {message}")
            state.status("provider_error", provider=provider.name, error=message, retryable=exc.retryable)
            state.provider_manager.mark_failed(provider.name, 30 if exc.retryable else 300)
            if state.on_delta:
                state.on_delta("\n[provider switched after error]\n", "status")
    raise AetherError("All providers failed. " + " | ".join(errors))


def _accumulate_usage(state: TurnState, response) -> None:
    usage = response.usage or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    state.usage["prompt_tokens"] = state.usage.get("prompt_tokens", 0) + prompt
    state.usage["completion_tokens"] = state.usage.get("completion_tokens", 0) + completion
    if response.reasoning:
        state.usage["reasoning_chars"] = state.usage.get("reasoning_chars", 0) + len(response.reasoning)


def run_turn_loop(state: TurnState) -> TurnState:
    for iteration in range(1, max(1, int(state.max_iterations)) + 1):
        state.messages, fit = state.context_manager.fit(state.messages)
        if fit.get("changed"):
            state.status("context_compressed", **fit)
        try:
            response, provider = _call_provider(state, iteration)
        except AetherError as exc:
            state.error = str(exc)
            state.exit_reason = "provider_error"
            state.final_text = f"I could not get a model response. {exc}"
            return state
        _accumulate_usage(state, response)
        state.status("model_response", provider=provider.name, tool_calls=len(response.tool_calls), finish_reason=response.finish_reason)

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
                state.tool_log.append(execution.as_dict())
            continue

        final_text = str(response.content or "").strip()
        if not final_text and response.reasoning:
            final_text = str(response.reasoning).strip()
        assistant = {"role": "assistant", "content": final_text}
        state.messages.append(assistant)
        state.new_messages.append(assistant)
        state.final_text = final_text
        state.exit_reason = "complete"
        return state

    state.exit_reason = "max_iterations"
    state.final_text = state.final_text or "I reached the iteration limit before completing the task. The tool log shows what was done so far."
    state.messages.append({"role": "assistant", "content": state.final_text})
    state.new_messages.append({"role": "assistant", "content": state.final_text})
    return state
