# Free AETHER development agent team

AETHER includes current OpenCode project configuration for a small, owner-controlled coding team. Agent metadata and permissions live in `opencode.json`; the system prompts live in `.opencode/agents/`. It is designed for a zero-upfront-cost workflow. OpenCode's hosted free-model availability and limits can change, so verify the model selector before relying on a specific model; local inference is the fallback.

## What is free, and what is limited

- OpenCode is open source and currently offers a selection of free hosted models without requiring an account. Free models have request limits and availability can change; the free model pool is not an uptime or unlimited-compute promise.
- OpenCode can also connect to GitHub Copilot using device OAuth. Copilot Free currently provides limited chat/agent usage; it does not include GitHub's cloud coding agent that takes an issue and opens a pull request for you. Review the current plan page before relying on it.
- Local Hugging Face models can run without hosted inference billing after you have downloaded the model, but they use your Mac's memory and compute. On an 8 GB Apple Silicon machine, treat small 1–2B quantized models as lightweight assistants, not frontier coding models.
- Hugging Face Inference Providers are not a dependable free inference backend: its current pricing page says Free accounts receive no monthly Inference Provider credits.

## Included agents

| Agent | Mode | Purpose |
| --- | --- | --- |
| `aether-lead` | Primary | Plans work and coordinates subagents |
| `architect` | Subagent | Read-only repository mapping and implementation design |
| `implementer` | Subagent | Scoped code and test changes; asks before risky shell operations |
| `qa` | Subagent | Runs checks and diagnoses regressions; cannot edit |
| `reviewer` | Subagent | Independent read-only final review |

The lead delegates only to the named roles. The current configuration denies repository edits to the lead, architect, QA, and reviewer; the implementer receives scoped edit permissions. Push, tag, and PR-merge commands are denied to the lead and implementer. Review the permission rules in `opencode.json` before broadening any authority. The agents are instructed not to publish, contact users, spend money, or change accounts. Parallel work should be limited to non-overlapping files; implementation and test/review stages should run sequentially when they touch the same area.

## Start

From the AETHER repository root:

```bash
opencode
```

The project config selects `aether-lead` as the default primary agent. OpenCode reads agent metadata from `opencode.json` and each agent's prompt from `.opencode/agents/`. In OpenCode, check the agent selector and select a model currently marked free, if one is offered in your region/account. Ask:

```text
Inspect the open AETHER roadmap. Delegate a read-only audit to architect.
Turn it into three independent work packages with file ownership and acceptance criteria.
Do not edit, commit, push, merge, tag, publish, or change settings until I approve a work package.
```

Once a package is approved, ask the lead to invoke `implementer` for that one package, then invoke `qa` and `reviewer` on the resulting change. Keep one implementer per overlapping file area. Use a feature branch and inspect `git diff` before accepting any change.

## Local Hugging Face model option for Apple Silicon

The MLX community hosts an Apache-2.0 quantized Qwen2.5-Coder-1.5B model (about 869 MB on the model card). It can run locally with MLX-LM:

```bash
uv tool install mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit
```

The server exposes an OpenAI-compatible local endpoint on port 8080 by default. If you use it with another compatible client, point that client at `http://127.0.0.1:8080/v1`. Download the model once; subsequent inference is local. The model is small enough to try on Apple Silicon, but expect weaker planning and tool-use reliability than larger hosted models. Keep AETHER's tests and independent review as the authority.

## Local soft voice option

For a natural local voice, use Kokoro-MLX (Kokoro-82M) on Apple Silicon. It runs on-device after model download, supports multiple voices and a speed multiplier, and does not require a paid speech API. A comfortable starting point is an English voice such as `af_bella` at a speed around `0.9`; tune it on the actual device.

```bash
python3.12 -m venv .venv-voice
source .venv-voice/bin/activate
python -m pip install "kokoro-mlx[audio]"
```

Kokoro-MLX currently requires macOS 14 or later, Apple Silicon, and Python 3.10–3.12. On older macOS versions, use the built-in `say` command as a zero-install fallback. AETHER does not yet include a finished speech interface. This is a local TTS component that can later be wired into the CLI; it does not add voice calling or phone messaging.

## Trust and income boundaries

These agents can help build software, research potential clients, prepare drafts, and track delivery. They cannot guarantee income, customers, stable employment, payments, or financial independence. Keep all client messages as drafts until a person approves them. Never store identity documents, bank/card credentials, customer passwords, or payment tokens in AETHER.

GitHub contributors are volunteers unless there is a separately agreed paid contract. Never advertise open-source volunteer work as paid employment.
