# AETHER launch and contributor growth plan

This is a practical launch plan for an independently maintained alpha project. The goal is to earn technical trust, attract a small group of useful contributors, and turn early users into repeat testers. Do not optimize for vanity stars at the expense of reliable software.

## 1. Positioning

### Primary positioning

**AETHER is a local-first, provider-agnostic AI agent for developers who want their agent's memory, plans, model choices, and tool permissions to be inspectable.**

Use this as the consistent one-sentence description across GitHub, social posts, demos, and community introductions.

### Supporting message

AETHER brings models you choose together with persistent local state, reusable skills, specialist agents, and a guarded coding workflow. Its differentiator is not the largest integration list. It is a lightweight, inspectable foundation with explicit permission, cost, and verification boundaries.

### What not to claim

- Do not claim that AETHER is a full Hermes replacement, has Hermes parity, or outperforms Hermes.
- Do not say every feature is production-ready. The project is alpha and some workflows remain partial.
- Do not claim the offline routing simulation is a task-quality benchmark.
- Do not imply hosted free tiers are unlimited or that AETHER bypasses provider restrictions.
- Do not call AETHER a security sandbox or imply that approval prompts eliminate all execution risk.
- Do not call the preview a stable release until the maintainer has made and documented that release decision.

### Competitive framing

AETHER should compete on a focused design choice: **local-first operation, minimal mandatory runtime dependencies, visible state, provider choice, and reviewable tool execution**.

Hermes Agent currently advertises a much broader surface area, including a large tool catalogue, multiple messaging channels, voice, MCP, desktop features, and remote execution backends. AETHER is not at equivalent breadth today. The credible story is that AETHER explores a smaller, inspectable, locally controlled alternative and is building toward broader capability with explicit evidence gates.

## 2. Launch gates

Before a broad launch:

- [ ] Review and merge PR #8 only after maintainers are satisfied with the current implementation and exact-head CI.
- [ ] Decide whether to publish a clearly labelled preview tag/artifact. This is a separate maintainer decision; do not imply it exists before it does.
- [ ] Ensure the default-branch README installation commands work from a clean checkout.
- [ ] Record a real local-model demo (not only the mock provider).
- [ ] Show a complete workflow: prompt → plan → inspect tool permission → preview a patch → approve the write → run a test → show verifier result.
- [ ] Record model, provider, hardware, Python version, settings, latency, and any cost for every performance claim.
- [ ] Keep known limitations and security language visible.
- [ ] Verify the first-contributor issue list and respond promptly to new issue/PR activity.

The CI checkpoint documented in the README is useful evidence, but it does not replace review of the current code or a task-quality benchmark.

## 3. The demo that sells the product

Make a 45–75 second terminal capture with captions. Avoid a long feature tour.

1. Start AETHER and show the product name and provider/model.
2. Ask it to inspect a tiny example repository and explain a bug.
3. Show the plan and the repository search result.
4. Show a proposed patch before any write.
5. Approve the patch explicitly.
6. Run the focused test.
7. Show the independent verifier's result and the exact evidence.

Use a real local model such as a supported Ollama model for the main demo. Show the model name and hardware. A separate 10-second mock-provider clip can demonstrate that the test/demo path works without credentials, but label it as a mock.

Include captions and a short plain-text transcript. Keep API keys, private file names, user paths, personal data, and unrelated terminal windows out of the capture.

## 4. Where to find the first users and developers

### GitHub

Treat the repository as the canonical source of truth. Keep the README, known limitations, contributor guide, issues, and CI in sync. Reply to every actionable bug report. A first-time contributor should be able to identify one task, run the tests, and open a focused PR without having to understand the entire architecture.

Start by inviting technical review of specific areas rather than asking people to “join the team” generically. Issue #13 is a first contribution focused on macOS CI. Issues #4, #6, #10, and #11 are larger workstreams and need coordination first.

### Hacker News

Use a Show HN only when a newcomer can actually run and evaluate the project. The official [Show HN guidelines](https://news.ycombinator.com/showhn.html) are explicit: the submission should be something people can try, not just a landing page or a request for feedback. The author should be personally involved in the work and available in the thread. Do not ask friends to upvote or comment.

Wait until the preview is merged or a clearly documented install path is available from the public default branch. Then post the repository with a reproducible demo and spend the day answering questions.

### Reddit / local-model communities

Do not post a bare promotional link. Share a useful technical write-up first: the local-first architecture, permission model, provider adapter design, or a reproducible result from a named model and machine. Disclose that you are the maintainer. Follow each community's current self-promotion rules and use designated project threads where required.

For a LocalLLaMA audience, bring actual measurements: hardware, model/quantization, RAM use, time-to-first-token, tokens/second, task result, context size, and whether any hosted service was used. Do not post benchmark claims until the same task and setup can be reproduced.

### Developer communities

Prioritize communities where people discuss Python CLIs, local inference, developer tools, and open-source agent architecture. Participate in existing technical discussions before sharing AETHER. Answer relevant questions even when AETHER is not the answer. A useful contribution to a discussion is better acquisition than repeated link drops.

## 5. Ready-to-adapt launch copy

### Show HN draft — publish only after the launch gates above

**Title:** Show HN: AETHER – a local-first, provider-agnostic Python AI agent

**Body:**

I built AETHER because I wanted an agent I could run from the terminal while keeping its model choice, memory, plans, and tool permissions inspectable.

AETHER is a Python CLI agent with local and hosted provider adapters, SQLite-backed sessions, editable memory and skills, specialist agents, and an approval-gated repository workflow. It can search a project, preview a patch, request approval before editing, run a bounded test command, and require a separate verifier to produce test evidence before work is marked verified.

The project is still alpha. I am not claiming Hermes parity, and I have not published a same-model task-quality comparison yet. Some integrations and release-hardening work remain on the roadmap.

The runtime currently targets Python 3.10+ and has no third-party runtime dependencies. You can try it with a local model; the mock provider is available for a no-key smoke test but is not an actual language model.

I would especially value feedback on first-run setup, the permission model, and whether the coding workflow is useful in a real repository. I built it and will be here to answer questions.

[Add the final public install command and a short real-model demo link before posting.]

### Reddit technical post draft — adapt to the community's rules

**Title:** I built a small local-first Python agent around inspectable state and approval-gated tools — architecture and test notes

**Body:**

I have been building AETHER, an independent Python CLI agent. The design trade-off is deliberate: keep ordinary local use lightweight, make provider selection and persistent state inspectable, and require explicit approval for sensitive tool actions.

The current preview includes local/hosted provider adapters, SQLite sessions and plans, layered memory, reusable skills, specialist agents, and a bounded repository-edit/test workflow. It is still alpha; I am not claiming broad feature parity with larger agent projects.

I am looking for technical review rather than promotion. The most useful feedback would be on [choose one concrete topic: permission inheritance / repository patching / memory provenance / provider routing]. I have included the exact test commands and limitations in the repository docs.

I maintain this project. If links are allowed in this community, the source is: https://github.com/ghostfacethegreat/aether-agent

[Add reproducible machine/model numbers or a code example before posting. Do not use this draft as a benchmark post without data.]

### Short social post

Building AETHER: a local-first, provider-agnostic Python agent focused on inspectable memory, specialist workflows, and approval-gated coding tools.

Still alpha, still proving itself. Looking for developers interested in local AI agents, CLI tooling, testing, and security-minded agent design.

Source: https://github.com/ghostfacethegreat/aether-agent

## 6. First 30 days

### Week 1 — make it easy to evaluate

- Finish PR review and make a separate release decision.
- Publish the terminal demo and transcript.
- Ask 3–5 developers for targeted technical feedback, each on one subsystem.
- Respond to every issue with a reproduction, next step, or explicit status.

### Week 2 — invite contributions

- Keep one or two genuinely small `good first issue` tickets available.
- Help newcomers get the test suite running before asking them to change code.
- Review outside PRs quickly and explain requested changes.
- Publish a brief development note describing what changed, what is still missing, and what evidence was collected.

### Week 3 — earn technical credibility

- Add reproducible coding, memory, tool-use, and orchestration tasks to the evaluation harness.
- Compare against other agents only with the same model, prompts, workspace, tool permissions, timeouts, and scoring rubric.
- Publish failures as well as successes. Include provider/model, machine, cost, and raw run artifacts.

### Week 4 — repeat what worked

- Review which posts led to real installs, actionable issues, repeat testers, and merged contributions.
- Prioritize those channels. Stop posting where engagement is only low-quality star exchanges.
- Thank contributors in release notes and the repository's contributor history.

## 7. Measure traction that matters

Track these weekly:

| Signal | Why it matters |
| --- | --- |
| Clean installs completed | Shows that new users can get started |
| Repeat users / returning testers | Indicates that AETHER is useful after the first try |
| Actionable bug reports | Reveals real-world gaps |
| First-time contributors and merged PRs | Measures developer onboarding |
| Reproducible benchmark coverage | Builds technical credibility |
| Stars and forks | Useful discovery signals, but not product validation on their own |

A first milestone is 5 external testers, 2 reproducible reports, and 1 merged external contribution—not an arbitrary star count.

## 8. Repository metadata to set

Suggested GitHub description:

> A local-first, provider-agnostic Python AI agent with inspectable memory, specialist workflows, and approval-gated coding tools.

Suggested GitHub topics:

`ai-agent`, `llm-agent`, `local-first`, `python`, `cli`, `ollama`, `multi-agent`, `developer-tools`, `agent-framework`, `provider-agnostic`.

Enable GitHub Discussions for design questions, usage patterns, and contributor introductions. Keep bugs and actionable work in Issues. Pin the README, contributing guide, and release/roadmap entry points.

## 9. Maintainer habits

- Be present after every launch post; do not publish and disappear.
- Do not ask for reciprocal stars, upvotes, or fake testimonials.
- Never invent testimonials, benchmark results, security claims, or contributor numbers.
- Thank people for useful bug reports even when they are not ready to contribute code.
- Keep the project welcoming to first-time contributors, but require tests and review for changes that affect permissions, persistence, provider billing, or execution.
