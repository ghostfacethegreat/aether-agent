# Free AETHER development agent team

AETHER includes current OpenCode project configuration for a small, owner-controlled coding team. Agent metadata and permissions live in `opencode.json`; the system prompts live in `.opencode/agents/`. It is designed for a zero-upfront-cost workflow. OpenCode's hosted free-model availability and limits can change, so verify the model selector before relying on a specific model; local inference is the fallback.

## What is free, and what is limited

- OpenCode's official model catalogue currently lists some zero-price models, but several are explicitly limited-time offers and the catalogue changes. The OpenCode provider may require signing in to OpenCode Console; do not assume anonymous access. In the model picker, choose only a model showing a $0 input and output price, check its current provider/usage limits, and do not add credits or select a paid model. Free means no model charge while that offer is available, not unlimited use or guaranteed uptime.
- OpenCode can also connect to GitHub Copilot using device OAuth. Copilot Free currently provides limited chat/agent usage; it does not include GitHub's cloud coding agent that takes an issue and opens a pull request for you. Review the current plan page before relying on it.
- Local Hugging Face models can run without hosted inference billing after you have downloaded the model, but they use your Mac's memory and compute. On an 8 GB Apple Silicon machine, treat small 1–2B quantized models as lightweight assistants, not frontier coding models.
- Hugging Face Inference Providers are not a dependable free inference backend: its current pricing page says Free accounts receive no monthly Inference Provider credits.

## Included agents

The current OpenCode configuration defines **13 profiles: one primary lead and 12 specialist subagents**. These are reusable role configurations, not 13 workers already running. They run only when the owner starts OpenCode locally and asks the lead to delegate. All inherit the session's chosen model unless a model is explicitly configured; the default is intentionally not pinned to a paid provider.

| Agent | Mode | Purpose | Default authority |
| --- | --- | --- | --- |
| `aether-lead` | Primary | Plans work, delegates and reconciles results | Coordinate; no direct edits |
| `architect` | Subagent | Repository mapping and implementation design | Read-only |
| `implementer` | Subagent | Scoped code and test changes | Scoped edits; command approvals |
| `qa` | Subagent | Runs checks and diagnoses regressions | No edits |
| `reviewer` | Subagent | Independent final code review | Read-only |
| `income-scout` | Subagent | Finds current paid coding/service work | Public research only; no applications or messages |
| `payment-pathfinder` | Subagent | Checks official payment and wallet requirements | Public research only; no account access or money movement |
| `coding-triager` | Subagent | Analyses bug reports and reproduction evidence | Read-only; no untrusted code execution |
| `proposal-writer` | Subagent | Drafts tailored proposals and client messages | Drafts only; never sends |
| `offer-strategist` | Subagent | Defines offer scope, exclusions and price assumptions | Read-only planning |
| `rights-reviewer` | Subagent | Checks commercial-use rights and platform rules | Public research only; blocks uncertain sources |
| `bookkeeper` | Subagent | Summarizes owner-entered VentureOps ledger data | Read-only; no account connections or transfers |
| `customer-success` | Subagent | Drafts status, delivery and renewal messages | Drafts only; never sends |

The lead may invoke only these named subagents. Every new business specialist is deny-by-default and receives read-only permissions; research roles additionally receive web search/fetch. The existing implementer is the only role with scoped repository edits. Push, tag, merge, outbound communication, applications, uploads, publishing, account changes, financial transactions and purchases remain blocked or require separate owner approval. Parallelize independent read-only research; do not fan out overlapping edits. Implementation, QA and final review should be staged sequentially.

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
