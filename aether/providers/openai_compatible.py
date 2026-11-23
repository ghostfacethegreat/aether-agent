import json
import time
import urllib.error
import urllib.request

from aether.errors import AuthenticationError, ProviderError, RateLimitError
from aether.utils import redact, redact_mapping

from .base import BaseProvider, ModelResponse, ToolCall


def _content_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts)
    return str(value)


def _arguments(value, raw=None) -> tuple[dict, str]:
    if isinstance(value, dict):
        return value, json.dumps(value, ensure_ascii=False)
    text = raw if raw is not None else value
    if text is None:
        return {}, ""
    text = str(text)
    try:
        parsed = json.loads(text) if text.strip() else {}
        if not isinstance(parsed, dict):
            return {}, text
        return parsed, text
    except (ValueError, TypeError):
        return {}, text


class OpenAICompatibleProvider(BaseProvider):
    api_mode = "openai"

    def __init__(self, config, model=None, spec=None, base_url="", api_key=""):
        super().__init__(config, model, spec)
        self.base_url = self._normalize_base_url(base_url)
        self.api_key = api_key or ""
        if self.spec:
            self.name = self.spec.name
            self.label = self.spec.label
            self.kind = self.spec.kind
            self.cost = self.spec.cost
            self.limits = self.spec.limits
            self.default_model = self.spec.default_model

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        url = (url or "").strip().rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]
        return url

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        if self.base_url.endswith("/v1") and path.startswith("v1/"):
            path = path[3:]
        return f"{self.base_url}/{path}"

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "aether-agent/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, path: str, payload=None, method="GET", stream=False):
        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self._url(path), data=data, headers=self._headers(), method=method)
        last_error = None
        for attempt in range(self.retry_attempts + 1):
            try:
                return urllib.request.urlopen(request, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                try:
                    body = exc.read(4096).decode("utf-8", "replace")
                except OSError:
                    body = ""
                summary = redact(body[:400])
                if exc.code in (401, 403):
                    raise AuthenticationError(
                        f"{self.label} rejected the API key (HTTP {exc.code}). Check the key in your environment. "
                        f"Response: {summary}",
                        provider=self.name,
                        status_code=exc.code,
                        payload={"body": summary},
                    ) from exc
                if exc.code == 429:
                    last_error = RateLimitError(
                        f"{self.label} rate limit (HTTP 429). {summary}",
                        provider=self.name,
                        status_code=429,
                        retryable=True,
                    )
                elif exc.code >= 500:
                    last_error = ProviderError(
                        f"{self.label} server error (HTTP {exc.code}). {summary}",
                        provider=self.name,
                        status_code=exc.code,
                        retryable=True,
                    )
                else:
                    raise ProviderError(
                        f"{self.label} request failed (HTTP {exc.code}). {summary}",
                        provider=self.name,
                        status_code=exc.code,
                        payload={"body": summary},
                    ) from exc
            except urllib.error.URLError as exc:
                last_error = ProviderError(
                    f"Cannot reach {self.label} at {self.base_url}: {redact(exc.reason)}. "
                    "Start the local server or check base_url.",
                    provider=self.name,
                    retryable=True,
                )
            if attempt < self.retry_attempts:
                time.sleep(min(2 ** attempt, 4))
        raise last_error or ProviderError(f"{self.label} request failed", provider=self.name)

    def list_models(self) -> list[str]:
        try:
            with self._request("models") as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
            return [str(item.get("id")) for item in data.get("data", []) if item.get("id")]
        except (ProviderError, OSError, ValueError):
            return []

    def _payload(self, messages, tools, stream, options):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": bool(stream),
            "temperature": float((options or {}).get("temperature", self.config.get("temperature", 0.2))),
        }
        max_tokens = (options or {}).get("max_tokens", self.config.get("max_tokens", 2048))
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        effort = (options or {}).get("reasoning_effort", self.config.get("reasoning_effort"))
        if effort:
            payload["reasoning_effort"] = effort
        extra = self.config.get(f"providers.{self.name}.extra_body", {}) or {}
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    def chat(self, messages, tools=None, stream=False, on_delta=None, options=None) -> ModelResponse:
        payload = self._payload(messages, tools, stream, options)
        response = self._request("chat/completions", payload, method="POST", stream=stream)
        if stream:
            return self._read_stream(response, on_delta)
        with response:
            raw = json.loads(response.read().decode("utf-8", "replace"))
        return self._normalize(raw)

    def _normalize(self, raw) -> ModelResponse:
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            args, raw_args = _arguments(function.get("arguments"))
            tool_calls.append(
                ToolCall(id=str(call.get("id") or ""), name=str(function.get("name") or ""), arguments=args, raw_arguments=raw_args)
            )
        reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
        return ModelResponse(
            content=_content_text(message.get("content")),
            tool_calls=tool_calls,
            reasoning=str(reasoning or ""),
            usage=raw.get("usage") or {},
            finish_reason=choice.get("finish_reason") or "stop",
            raw=raw,
        )

    def _read_stream(self, response, on_delta) -> ModelResponse:
        content_parts = []
        reasoning_parts = []
        calls = {}
        usage = {}
        finish_reason = "stop"
        with response:
            for raw_line in response:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                if chunk.get("usage"):
                    usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
                delta = choice.get("delta") or {}
                text = _content_text(delta.get("content"))
                if text:
                    content_parts.append(text)
                    if on_delta:
                        on_delta(text, "content")
                reason = delta.get("reasoning") or delta.get("reasoning_content") or ""
                if reason:
                    reason_text = str(reason)
                    reasoning_parts.append(reason_text)
                    if on_delta:
                        on_delta(reason_text, "reasoning")
                for index, call in enumerate(delta.get("tool_calls") or []):
                    key = int(call.get("index", index))
                    entry = calls.setdefault(key, {"id": "", "name": "", "args": ""})
                    if call.get("id"):
                        entry["id"] = str(call["id"])
                    function = call.get("function") or {}
                    if function.get("name"):
                        entry["name"] = str(function["name"])
                    if function.get("arguments"):
                        entry["args"] += str(function["arguments"])
        tool_calls = []
        for key in sorted(calls):
            entry = calls[key]
            args, raw_args = _arguments(entry["args"])
            tool_calls.append(ToolCall(id=entry["id"] or f"call_{key}", name=entry["name"], arguments=args, raw_arguments=raw_args))
        return ModelResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            reasoning="".join(reasoning_parts),
            usage=usage,
            finish_reason=finish_reason,
        )

    def describe(self) -> dict:
        result = super().describe()
        result["base_url"] = self.base_url
        result["api_key"] = "set" if self.api_key else "not set"
        result["headers"] = redact_mapping(self.config.get(f"providers.{self.name}.extra_headers", {}) or {})
        return result
