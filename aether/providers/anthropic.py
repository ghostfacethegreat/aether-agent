import json

from .base import ModelResponse, ToolCall
from .openai_compatible import OpenAICompatibleProvider, _arguments, _content_text


class AnthropicProvider(OpenAICompatibleProvider):
    api_mode = "anthropic"

    def __init__(self, config, model=None, spec=None, base_url="", api_key=""):
        super().__init__(config, model, spec, base_url, api_key)
        self.headers_extra = {"anthropic-version": "2023-06-01"}

    def _headers(self) -> dict:
        headers = super()._headers()
        headers["x-api-key"] = self.api_key
        headers.pop("Authorization", None)
        headers.update(self.headers_extra)
        return headers

    def list_models(self) -> list[str]:
        return list(self.spec.sample_models) if self.spec else []

    def _convert_messages(self, messages):
        system_parts = []
        converted = []
        pending_tools = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role == "system":
                system_parts.append(_content_text(content))
                continue
            if role == "tool":
                pending_tools.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": str(message.get("tool_call_id") or ""),
                        "content": _content_text(content),
                    }
                )
                continue
            blocks = []
            if pending_tools:
                blocks.extend(pending_tools)
                pending_tools = []
            if role == "assistant":
                text = _content_text(content)
                if text:
                    blocks.append({"type": "text", "text": text})
                for call in message.get("tool_calls") or []:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": str(call.get("id") or ""),
                            "name": str(call.get("name") or ""),
                            "input": call.get("arguments") or {},
                        }
                    )
                if not blocks:
                    blocks.append({"type": "text", "text": ""})
                converted.append({"role": "assistant", "content": blocks})
            else:
                if not blocks:
                    text = _content_text(content)
                    blocks.append({"type": "text", "text": text})
                converted.append({"role": "user", "content": blocks})
        if pending_tools:
            converted.append({"role": "user", "content": pending_tools})
        return "\n\n".join(part for part in system_parts if part), converted

    @staticmethod
    def _convert_tools(tools):
        result = []
        for tool in tools or []:
            function = tool.get("function") if tool.get("type") == "function" else tool
            if not function:
                continue
            result.append(
                {
                    "name": str(function.get("name") or ""),
                    "description": str(function.get("description") or ""),
                    "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return result

    def _payload(self, messages, tools, stream, options):
        system, converted = self._convert_messages(messages)
        payload = {
            "model": self.model,
            "messages": converted,
            "max_tokens": int((options or {}).get("max_tokens", self.config.get("max_tokens", 2048)) or 2048),
            "stream": bool(stream),
        }
        if system:
            payload["system"] = system
        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools
        effort = (options or {}).get("reasoning_effort", self.config.get("reasoning_effort"))
        if effort:
            payload["thinking"] = {"type": "enabled", "budget_tokens": 1024 if effort in ("low", "medium") else 2048}
            payload["max_tokens"] = max(int(payload["max_tokens"]), 4096)
        return payload

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None):
        payload = self._payload(messages, tools, stream, options)
        response = self._request("messages", payload, method="POST", stream=stream)
        if stream:
            return self._read_stream(response, on_delta)
        with response:
            raw = json.loads(response.read().decode("utf-8", "replace"))
        return self._normalize(raw)

    def _normalize(self, raw) -> ModelResponse:
        texts = []
        tool_calls = []
        reasoning = []
        for block in raw.get("content") or []:
            kind = block.get("type")
            if kind == "text":
                texts.append(str(block.get("text") or ""))
            elif kind == "thinking":
                reasoning.append(str(block.get("thinking") or ""))
            elif kind == "tool_use":
                args, raw_args = _arguments(block.get("input") or {})
                tool_calls.append(
                    ToolCall(
                        id=str(block.get("id") or ""),
                        name=str(block.get("name") or ""),
                        arguments=args,
                        raw_arguments=raw_args,
                    )
                )
        stop = raw.get("stop_reason") or "end_turn"
        finish = {"end_turn": "stop", "tool_use": "tool_calls", "max_tokens": "length", "stop_sequence": "stop"}.get(stop, stop)
        return ModelResponse(
            content="".join(texts),
            tool_calls=tool_calls,
            reasoning="".join(reasoning),
            usage=raw.get("usage") or {},
            finish_reason=finish,
            raw=raw,
        )

    def _read_stream(self, response, on_delta) -> ModelResponse:
        texts = []
        reasoning = []
        calls = {}
        usage = {}
        finish = "stop"
        with response:
            for raw_line in response:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("event:"):
                    continue
                event = line[6:].strip()
                data_text = ""
                while True:
                    chunk = response.readline()
                    if not chunk:
                        break
                    decoded = chunk.decode("utf-8", "replace").strip()
                    if not decoded:
                        break
                    if decoded.startswith("data:"):
                        data_text += decoded[5:].strip()
                if not data_text:
                    continue
                try:
                    data = json.loads(data_text)
                except ValueError:
                    continue
                if event == "message_start":
                    usage.update((data.get("message") or {}).get("usage") or {})
                elif event == "message_delta":
                    usage.update(data.get("usage") or {})
                    reason = (data.get("delta") or {}).get("stop_reason")
                    if reason:
                        finish = {"end_turn": "stop", "tool_use": "tool_calls", "max_tokens": "length"}.get(reason, reason)
                elif event == "content_block_start":
                    block = data.get("content_block") or {}
                    if block.get("type") == "tool_use":
                        calls[int(data.get("index", 0))] = {
                            "id": str(block.get("id") or ""),
                            "name": str(block.get("name") or ""),
                            "args": "",
                        }
                elif event == "content_block_delta":
                    delta = data.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        text = str(delta.get("text") or "")
                        if text:
                            texts.append(text)
                            if on_delta:
                                on_delta(text, "content")
                    elif delta.get("type") == "input_json_delta":
                        entry = calls.get(int(data.get("index", 0)))
                        if entry is not None:
                            entry["args"] += str(delta.get("partial_json") or "")
                    elif delta.get("type") == "thinking_delta":
                        text = str(delta.get("thinking") or "")
                        if text:
                            reasoning.append(text)
                            if on_delta:
                                on_delta(text, "reasoning")
                elif event == "message_stop":
                    break
        tool_calls = []
        for key in sorted(calls):
            entry = calls[key]
            args, raw_args = _arguments(entry["args"])
            tool_calls.append(ToolCall(id=entry["id"] or f"call_{key}", name=entry["name"], arguments=args, raw_arguments=raw_args))
        return ModelResponse(content="".join(texts), tool_calls=tool_calls, reasoning="".join(reasoning), usage=usage, finish_reason=finish)
