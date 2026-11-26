# Local provider troubleshooting

This guide diagnoses local model connections without paid API keys. Commands below are intended for macOS and Linux shells. They do not upload diagnostics.

## Start with AETHER's offline path

Confirm that the installed command is the project version you expect:

```bash
aether --help
aether --provider mock run "Reply with exactly: AETHER mock provider works"
aether doctor
```

The mock provider is in-process and makes no model-provider network call. If the mock run fails, diagnose the AETHER installation first; do not troubleshoot Ollama, LM Studio, or llama.cpp yet.

List the provider catalog:

```bash
aether providers
```

For local provider health information:

```bash
aether models health
```

Health output is local diagnostic state. It does not guarantee a provider process is currently reachable.

## Ollama

### Confirm installation and the model

```bash
command -v ollama
ollama --version
ollama list
```

If Ollama is installed but the local server is not running, start it in a separate terminal:

```bash
ollama serve
```

The documented OpenAI-compatible default used by AETHER is `http://127.0.0.1:11434/v1`.

Check the local Ollama API:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags
```

Use the exact model tag shown by `ollama list`:

```bash
aether --provider ollama --model llama3.2:3b run "Say hello"
```

Replace `llama3.2:3b` if your installed model has a different tag. Do not assume a model is installed just because it appears in an example.

## LM Studio

1. Open LM Studio.
2. Download or select a model that fits your machine.
3. Load the model into memory.
4. Open the local server panel and start the OpenAI-compatible server.
5. Confirm the displayed host, port, and model identifier.

LM Studio commonly uses port `1234`, but the application may be configured differently. Use the exact base URL and model ID displayed by your server.

For a server configured on the common local port:

```bash
curl --fail --silent --show-error http://127.0.0.1:1234/v1/models
```

Then try:

```bash
aether --provider lmstudio --model local-model run "Say hello"
```

Replace `local-model` with the model identifier exposed by your server. If you changed the port or base URL, use the matching provider configuration in AETHER rather than copying the example unchanged.

## llama.cpp

Start `llama-server` with a model file and an explicit local port. For example:

```bash
llama-server --model /path/to/model.gguf --host 127.0.0.1 --port 8080
```

Keep the server terminal open while testing. In another terminal, inspect the OpenAI-compatible model endpoint:

```bash
curl --fail --silent --show-error http://127.0.0.1:8080/v1/models
```

Then:

```bash
aether --provider llamacpp --model local-model run "Say hello"
```

Replace the model path and model identifier with your actual values. If the server uses a different host or port, configure that exact local endpoint.

## Common errors

| Symptom | Likely cause | Safe next check |
|---|---|---|
| Connection refused | Provider server is stopped, listening on another port, or bound to another address | Check the app/server status and request `/v1/models` at its configured local URL |
| Model not found | Requested model ID differs from the loaded/installed ID | Compare `ollama list` or the server's `/v1/models` response with `--model` |
| 401 / unauthorized | An endpoint expects authentication or the configured key is wrong | Verify the provider's local auth setting; never paste the key into an issue |
| 404 / route not found | A non-OpenAI route or incorrect base URL was configured | Check the server's OpenAI-compatible endpoint and base URL |
| Out of memory / model unloads | Model, context, or concurrent work exceeds available memory | Try a smaller quantization/model, shorter context, or one request at a time |
| Slow first response | Model files are loading or initial compilation/warm-up is occurring | Retry once after the model reports ready; compare later requests |
| Rate limit / quota error | A hosted provider quota was reached | Check that provider's current limits; use a local model or mock provider instead |

## What to include in a bug report

Include only the minimum reproducible diagnostic information:

- AETHER version or Git commit.
- Operating system version and Python version.
- Provider name and the model identifier (not credentials).
- Whether the local `/v1/models` endpoint responds.
- The exact command used, with private paths replaced by `/path/to/model`.
- The complete error text after removing tokens, keys, email addresses, usernames, private hostnames, and unrelated local paths.

Never share:

- `.env` files, API keys, bearer tokens, cookies, or authorization headers.
- Full shell environment dumps such as `env` or `printenv`.
- Private model paths or personal directory names unless genuinely required.
- Customer media, project source, or private conversation logs.

A safe redaction example:

```text
Provider: lmstudio
Model: local-model
Base URL: http://127.0.0.1:1234/v1
Error: Connection refused
API key: [REDACTED — not shared]
```

## Still stuck?

1. Confirm the mock-provider command works.
2. Confirm the model server is running and its local `/v1/models` endpoint responds.
3. Compare the provider name, base URL, and exact model ID with AETHER's provider configuration.
4. Re-run the smallest failing command.
5. Open a GitHub issue with the redacted diagnostic details above.

Do not disable AETHER's permission checks or publish credentials as a troubleshooting shortcut.
