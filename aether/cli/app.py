import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from aether import __version__
from aether.config import Config, load_config, load_environment
from aether.core import Agent
from aether.core.planning import ExecutionPlan
from aether.errors import AetherError
from aether.home import aether_home, env_path
from aether.logging import get_logger, set_level
from aether.memory import LAYERS, LayeredMemory, MemoryStore
from aether.orchestration import ROLE_NAMES, Orchestrator, resolved_roles
from aether.persistence import Store
from aether.providers.catalog import PROVIDERS, provider_is_billable
from aether.routing import classify_task
from aether.tasks import Scheduler
from aether.utils import parse_bool, read_json, redact, redact_mapping, truncate, atomic_json_write

from . import render


SLASH_COMMANDS = [
    "/help", "/quit", "/exit", "/new", "/clear", "/status", "/provider", "/model",
    "/plan", "/tools", "/memory", "/skills", "/sessions", "/resume", "/history",
    "/tasks", "/agents", "/schedule", "/models", "/cost", "/doctor", "/export", "/feedback",
]


def build_parser():
    parser = argparse.ArgumentParser(prog="aether", description="Aether: local-first, provider-agnostic AI agent")
    parser.add_argument("--home", help="Override AETHER_HOME")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--workspace", help="Override AETHER_WORKSPACE")
    parser.add_argument("--provider", help="Use a provider for this session")
    parser.add_argument("--model", help="Use a model for this session")
    parser.add_argument("--session", help="Resume a stored session ID")
    parser.add_argument("--no-stream", action="store_true", help="Disable token streaming")
    parser.add_argument("--reasoning", action="store_true", help="Show model reasoning when available")
    parser.add_argument("--debug", action="store_true", help="Show debug logs and tracebacks")
    parser.add_argument("--confirm-paid", action="store_true", help="Allow billable providers for this process only")

    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="Create and explain local configuration")
    p_setup.set_defaults(func=cmd_setup)

    p_providers = sub.add_parser("providers", help="List providers with honest cost and limit notes")
    p_providers.set_defaults(func=cmd_providers)

    p_models = sub.add_parser("models", help="Inspect and explain model routing without calling a model")
    models = p_models.add_subparsers(dest="action", required=True)
    for name in ("list", "health", "performance"):
        models.add_parser(name).set_defaults(func=cmd_models)
    inspect = models.add_parser("inspect")
    inspect.add_argument("provider", nargs="?")
    inspect.add_argument("model", nargs="?")
    inspect.set_defaults(func=cmd_models)
    capabilities = models.add_parser("capabilities")
    capabilities.add_argument("provider", nargs="?")
    capabilities.add_argument("model", nargs="?")
    capabilities.set_defaults(func=cmd_models)
    for name in ("routing", "explain"):
        item = models.add_parser(name)
        item.add_argument("prompt", nargs="+")
        item.set_defaults(func=cmd_models)
    benchmark = models.add_parser("benchmark")
    benchmark.add_argument("--samples", type=int, default=5)
    benchmark.add_argument("--confirm-billable", action="store_true", help="Acknowledge any configured live benchmark costs")
    benchmark.set_defaults(func=cmd_models)

    p_status = sub.add_parser("status", help="Show active provider and session status")
    p_status.set_defaults(func=cmd_status)

    p_doctor = sub.add_parser("doctor", help="Check local environment and configuration")
    p_doctor.add_argument("--live", action="store_true", help="Probe configured provider endpoints")
    p_doctor.set_defaults(func=cmd_doctor)

    p_config = sub.add_parser("config", help="Inspect or edit config.json")
    cfg = p_config.add_subparsers(dest="action", required=True)
    p_cfg_get = cfg.add_parser("get")
    p_cfg_get.add_argument("key")
    p_cfg_get.set_defaults(func=cmd_config)
    p_cfg_set = cfg.add_parser("set")
    p_cfg_set.add_argument("key")
    p_cfg_set.add_argument("value")
    p_cfg_set.set_defaults(func=cmd_config)
    p_cfg_list = cfg.add_parser("list")
    p_cfg_list.set_defaults(func=cmd_config)

    p_sessions = sub.add_parser("sessions", help="Manage local sessions")
    sess = p_sessions.add_subparsers(dest="action", required=True)
    for name in ("list", "show", "delete", "export", "import"):
        item = sess.add_parser(name)
        if name in ("show", "delete", "export"):
            item.add_argument("id")
        if name == "import":
            item.add_argument("path")
        if name == "export":
            item.add_argument("path", nargs="?")
        item.set_defaults(func=cmd_sessions)

    p_memory = sub.add_parser("memory", help="Manage persistent memory files")
    mem = p_memory.add_subparsers(dest="action", required=True)
    mem_list = mem.add_parser("list")
    mem_list.add_argument("--user", action="store_true")
    mem_list.set_defaults(func=cmd_memory)
    mem_add = mem.add_parser("add")
    mem_add.add_argument("text")
    mem_add.add_argument("--category", default="general")
    mem_add.add_argument("--user", action="store_true")
    mem_add.set_defaults(func=cmd_memory)
    mem_search = mem.add_parser("search")
    mem_search.add_argument("query")
    mem_search.add_argument("--user", action="store_true")
    mem_search.set_defaults(func=cmd_memory)
    mem_delete = mem.add_parser("delete")
    mem_delete.add_argument("category")
    mem_delete.add_argument("index", type=int)
    mem_delete.add_argument("--user", action="store_true")
    mem_delete.set_defaults(func=cmd_memory)
    mem_clear = mem.add_parser("clear")
    mem_clear.add_argument("--user", action="store_true")
    mem_clear.set_defaults(func=cmd_memory)
    mem_export = mem.add_parser("export")
    mem_export.add_argument("path", nargs="?")
    mem_export.set_defaults(func=cmd_memory)
    mem_import = mem.add_parser("import")
    mem_import.add_argument("path")
    mem_import.add_argument("--replace", action="store_true")
    mem_import.set_defaults(func=cmd_memory)

    mem_layer = mem.add_parser("layer", help="Manage layered memory")
    layer = mem_layer.add_subparsers(dest="layer_action", required=True)
    layer_list = layer.add_parser("list")
    layer_list.add_argument("--layer", choices=LAYERS)
    layer_list.add_argument("--session")
    layer_list.set_defaults(func=cmd_memory)
    layer_add = layer.add_parser("add")
    layer_add.add_argument("content")
    layer_add.add_argument("--layer", choices=LAYERS, default="semantic")
    layer_add.add_argument("--subject", default="")
    layer_add.add_argument("--provenance", default="manual")
    layer_add.add_argument("--confidence", type=float)
    layer_add.add_argument("--session")
    layer_add.add_argument("--expires-days", type=float)
    layer_add.add_argument("--verified", action="store_true")
    layer_add.set_defaults(func=cmd_memory)
    layer_recall = layer.add_parser("recall")
    layer_recall.add_argument("query", nargs="?")
    layer_recall.add_argument("--layer", choices=LAYERS)
    layer_recall.add_argument("--session")
    layer_recall.add_argument("--limit", type=int)
    layer_recall.add_argument("--max-chars", type=int)
    layer_recall.set_defaults(func=cmd_memory)
    layer_context = layer.add_parser("context")
    layer_context.add_argument("task", nargs="*")
    layer_context.add_argument("--max-chars", type=int)
    layer_context.set_defaults(func=cmd_memory)
    layer_correct = layer.add_parser("correct")
    layer_correct.add_argument("id")
    layer_correct.add_argument("content")
    layer_correct.add_argument("--provenance", default="correction")
    layer_correct.add_argument("--confidence", type=float)
    layer_correct.set_defaults(func=cmd_memory)
    layer_delete = layer.add_parser("delete")
    layer_delete.add_argument("id")
    layer_delete.set_defaults(func=cmd_memory)
    layer_clear = layer.add_parser("clear")
    layer_clear.add_argument("--layer", choices=LAYERS)
    layer_clear.add_argument("--session")
    layer_clear.set_defaults(func=cmd_memory)
    for name in ("consolidate", "prune", "migrate", "counts"):
        layer.add_parser(name).set_defaults(func=cmd_memory)
    layer_export = layer.add_parser("export")
    layer_export.add_argument("path", nargs="?")
    layer_export.set_defaults(func=cmd_memory)
    layer_import = layer.add_parser("import")
    layer_import.add_argument("path")
    layer_import.add_argument("--replace", action="store_true")
    layer_import.set_defaults(func=cmd_memory)

    p_skills = sub.add_parser("skills", help="Manage reusable SKILL.md skills")
    skill = p_skills.add_subparsers(dest="action", required=True)
    skill_list = skill.add_parser("list")
    skill_list.set_defaults(func=cmd_skills)
    skill_view = skill.add_parser("view")
    skill_view.add_argument("name")
    skill_view.set_defaults(func=cmd_skills)
    skill_create = skill.add_parser("create")
    skill_create.add_argument("name")
    skill_create.add_argument("description")
    skill_create.add_argument("body", nargs="?")
    skill_create.set_defaults(func=cmd_skills)
    skill_edit = skill.add_parser("edit")
    skill_edit.add_argument("name")
    skill_edit.add_argument("body")
    skill_edit.set_defaults(func=cmd_skills)
    skill_discover = skill.add_parser("discover", help="Propose skills from verified experiences")
    skill_discover.add_argument("--limit", type=int)
    skill_discover.add_argument("--query", default="")
    skill_discover.set_defaults(func=cmd_skills)
    skill_proposals = skill.add_parser("proposals", help="List skill proposals and evidence")
    skill_proposals.add_argument("--status")
    skill_proposals.add_argument("--skill")
    skill_proposals.set_defaults(func=cmd_skills)
    skill_validate = skill.add_parser("validate", help="Validate a proposed skill")
    skill_validate.add_argument("skill")
    skill_validate.set_defaults(func=cmd_skills)
    skill_approve = skill.add_parser("approve", help="Approve and save a validated proposal")
    skill_approve.add_argument("proposal")
    skill_approve.add_argument("--yes", action="store_true", help="Confirm persistent skill change")
    skill_approve.set_defaults(func=cmd_skills)
    skill_reject = skill.add_parser("reject", help="Reject a proposal")
    skill_reject.add_argument("proposal")
    skill_reject.add_argument("--reason", default="")
    skill_reject.set_defaults(func=cmd_skills)
    skill_history = skill.add_parser("history", help="Show learning history for a skill")
    skill_history.add_argument("skill", nargs="?")
    skill_history.add_argument("--query", default="")
    skill_history.add_argument("--limit", type=int)
    skill_history.set_defaults(func=cmd_skills)
    skill_versions = skill.add_parser("versions", help="List stored skill versions")
    skill_versions.add_argument("skill")
    skill_versions.set_defaults(func=cmd_skills)
    skill_rollback = skill.add_parser("rollback", help="Activate a previous skill version")
    skill_rollback.add_argument("skill")
    skill_rollback.add_argument("version", type=int)
    skill_rollback.add_argument("--yes", action="store_true", help="Confirm rollback")
    skill_rollback.set_defaults(func=cmd_skills)
    skill_result = skill.add_parser("result", help="Record a verified skill execution result")
    skill_result.add_argument("skill")
    skill_result.add_argument("--success", action="store_true")
    skill_result.add_argument("--verified", action="store_true")
    skill_result.add_argument("--duration-ms", type=float, default=0.0)
    skill_result.add_argument("--tokens", type=int, default=0)
    skill_result.add_argument("--cost", type=float, default=0.0)
    skill_result.set_defaults(func=cmd_skills)

    p_learning = sub.add_parser("learning", help="Inspect learning state and record feedback")
    learning = p_learning.add_subparsers(dest="action", required=True)
    p_feedback = learning.add_parser("feedback", help="Record explicit user feedback")
    p_feedback.add_argument("verdict", choices=["verified", "failed", "neutral"])
    p_feedback.add_argument("text", nargs="+")
    p_feedback.add_argument("--experience")
    p_feedback.add_argument("--session")
    p_feedback.set_defaults(func=cmd_learning)
    p_pending = learning.add_parser("pending", help="List pending learning proposals")
    p_pending.set_defaults(func=cmd_learning)
    p_metrics = learning.add_parser("metrics", help="Show tracked skill performance")
    p_metrics.add_argument("skill", nargs="?")
    p_metrics.set_defaults(func=cmd_learning)

    p_tasks = sub.add_parser("tasks", help="Inspect delegated task ledger")
    tasks = p_tasks.add_subparsers(dest="action", required=True)
    tasks_list = tasks.add_parser("list")
    tasks_list.set_defaults(func=cmd_tasks)
    tasks_resume = tasks.add_parser("resume")
    tasks_resume.add_argument("id")
    tasks_resume.set_defaults(func=cmd_tasks)

    p_plan = sub.add_parser("plan", help="Inspect or resume adaptive execution plans")
    plan = p_plan.add_subparsers(dest="action", required=True)
    plan_list = plan.add_parser("list", help="List stored execution plans")
    plan_list.set_defaults(func=cmd_plan)
    plan_show = plan.add_parser("show", help="Show a stored execution plan")
    plan_show.add_argument("id")
    plan_show.set_defaults(func=cmd_plan)
    plan_status = plan.add_parser("status", help="Show the active or selected execution plan status")
    plan_status.add_argument("id", nargs="?")
    plan_status.set_defaults(func=cmd_plan)
    plan_checkpoints = plan.add_parser("checkpoints", help="List checkpoints for a stored plan")
    plan_checkpoints.add_argument("id", nargs="?")
    plan_checkpoints.set_defaults(func=cmd_plan)
    plan_resume = plan.add_parser("resume", help="Resume a stored execution plan")
    plan_resume.add_argument("id")
    plan_resume.set_defaults(func=cmd_plan)

    p_agents = sub.add_parser("agents", help="Inspect and run specialized agents")
    agents = p_agents.add_subparsers(dest="action", required=True)
    agents_list = agents.add_parser("list")
    agents_list.set_defaults(func=cmd_agents)
    agents_status = agents.add_parser("status")
    agents_status.set_defaults(func=cmd_agents)
    agents_run = agents.add_parser("run")
    agents_run.add_argument("role")
    agents_run.add_argument("task", nargs="+")
    agents_run.set_defaults(func=cmd_agents)
    agents_cancel = agents.add_parser("cancel")
    agents_cancel.add_argument("id")
    agents_cancel.set_defaults(func=cmd_agents)
    agents_resume = agents.add_parser("resume", help="Resume unfinished tasks from a stored run")
    agents_resume.add_argument("id")
    agents_resume.set_defaults(func=cmd_agents)

    p_schedule = sub.add_parser("schedule", help="Manage local scheduled jobs")
    sched = p_schedule.add_subparsers(dest="action", required=True)
    sched_list = sched.add_parser("list")
    sched_list.set_defaults(func=cmd_schedule)
    sched_add = sched.add_parser("add")
    sched_add.add_argument("prompt")
    sched_add.add_argument("schedule_time")
    sched_add.add_argument("--name", default="")
    sched_add.set_defaults(func=cmd_schedule)
    sched_remove = sched.add_parser("remove")
    sched_remove.add_argument("id")
    sched_remove.set_defaults(func=cmd_schedule)
    sched_cancel = sched.add_parser("cancel", help="Alias for remove")
    sched_cancel.add_argument("id")
    sched_cancel.set_defaults(func=cmd_schedule)
    sched_update = sched.add_parser("update")
    sched_update.add_argument("id")
    sched_update.add_argument("prompt", nargs="?", default=None)
    sched_update.add_argument("schedule_time", nargs="?", default=None)
    sched_update.add_argument("--name", default=None)
    sched_update.set_defaults(func=cmd_schedule)
    sched_pause = sched.add_parser("pause")
    sched_pause.add_argument("id")
    sched_pause.set_defaults(func=cmd_schedule)
    sched_resume = sched.add_parser("resume")
    sched_resume.add_argument("id")
    sched_resume.set_defaults(func=cmd_schedule)
    sched_tick = sched.add_parser("tick")
    sched_tick.set_defaults(func=cmd_schedule)

    p_run = sub.add_parser("run", help="Run one prompt and exit")
    p_run.add_argument("prompt", nargs="+")
    p_run.set_defaults(func=cmd_run)

    p_version = sub.add_parser("version", help="Print version")
    p_version.set_defaults(func=cmd_version)

    p_update = sub.add_parser("update", help="Pull the source repository and reinstall")
    p_update.add_argument("--yes", action="store_true")
    p_update.set_defaults(func=cmd_update)

    return parser


def prepare(args):
    if args.home:
        os.environ["AETHER_HOME"] = str(Path(args.home).expanduser().resolve())
    if args.workspace:
        os.environ["AETHER_WORKSPACE"] = str(Path(args.workspace).expanduser().resolve())
    load_environment()
    config = load_config(Path(args.config) if args.config else None, create=True)
    if getattr(args, "confirm_paid", False):
        os.environ["AETHER_CONFIRM_PAID"] = "1"
    if args.provider:
        previous = str(config.get("provider") or "")
        config.set("provider", args.provider)
        if args.model is None and previous != args.provider:
            spec = PROVIDERS.get(args.provider)
            if spec:
                config.set("model", spec.default_model)
    if args.model:
        config.set("model", args.model)
    if args.no_stream:
        config.set("streaming", False)
    get_logger("aether", config.get("logging", {}))
    if args.debug:
        set_level("DEBUG")
    return config, aether_home()


def make_approver():
    def approve(subject, reason, rule_key):
        print("\n" + render.paint(subject, "yellow"))
        print("  " + str(reason))
        print("  rule: " + str(rule_key))
        try:
            answer = input("  Allow? [y] once / [s] session / [a] always / [n] no: ").strip().lower()
        except EOFError:
            return "no"
        return {"y": "once", "yes": "once", "s": "session", "a": "always", "n": "no"}.get(answer, answer)

    return approve


def make_agent(args, config, home, scheduler=None):
    return Agent(
        config,
        home=home,
        session_id=args.session,
        approve_callback=make_approver(),
        scheduler=scheduler,
        provider_name=getattr(args, "provider", None),
        model=getattr(args, "model", None),
    )


def stream_turn(agent, text, args=None, quiet=False):
    spinner = render.Spinner("thinking")
    first_content = [False]
    reasoning = []
    show_reasoning = bool(args and args.reasoning)
    debug = bool(args and args.debug)

    def on_delta(delta, kind="content"):
        if kind == "reasoning":
            reasoning.append(str(delta))
            if show_reasoning:
                if not first_content[0]:
                    spinner.stop()
                    first_content[0] = True
                sys.stdout.write(render.paint(str(delta), "yellow"))
                sys.stdout.flush()
            return
        if not first_content[0]:
            spinner.stop()
            first_content[0] = True
        if not quiet:
            sys.stdout.write(str(delta))
            sys.stdout.flush()

    def on_status(payload):
        line = render.status_line(payload)
        if line:
            if not first_content[0]:
                spinner.stop()
                first_content[0] = True
            print(line, flush=True)

    agent.executor.on_execute = lambda execution: print(render.tool_line(execution), flush=True)
    spinner.start()
    try:
        result = agent.run_turn(text, on_delta=on_delta, on_status=on_status)
    finally:
        spinner.stop()
    if not quiet:
        print()
        usage = result.usage
        detail = f"{usage.get('prompt_tokens', 0)} in / {usage.get('completion_tokens', 0)} out · {result.provider}/{result.model}"
        print(render.paint("  " + detail, "dim"))
        if debug:
            print(render.paint("  " + result.exit_reason + " · " + result.session_id, "dim"))
    return result


def setup_completer():
    try:
        import readline
    except ImportError:
        return
    readline.parse_and_bind("tab: complete")
    readline.set_completer(lambda text, state: [item for item in SLASH_COMMANDS if item.startswith(text)][state] if state < len([item for item in SLASH_COMMANDS if item.startswith(text)]) else None)


def _role_rows(config):
    roles = resolved_roles(config)
    rows = []
    for name in ROLE_NAMES:
        spec = roles.get(name, {})
        provider = spec.get("provider") or config.get("provider")
        model = spec.get("model") or config.get("model")
        tools = ", ".join(spec.get("allowed_tools", [])[:6])
        rows.append((name, f"{provider}/{model}", str(spec.get("max_iterations", 4)), truncate(tools, 70)))
    return rows


def print_agents_status(orchestrator):
    active = orchestrator.status()
    if not active:
        print("(no active agent runs)")
    for run in active:
        print(f"Run {run['id']} · {run['status']} · {run['mode']} · {truncate(run['objective'], 90)}")
        rows = [
            (
                truncate(task["id"], 12),
                task["role"],
                task["status"],
                str(task["attempts"]),
                truncate(str(task["model"]) or "-", 24),
                str(task["tokens"]),
                task["cost"],
                truncate(task["error"], 50),
            )
            for task in run["tasks"]
        ]
        print(render.table(["Task", "Role", "Status", "Tries", "Model", "Tokens", "Cost", "Error"], rows))
    runs = orchestrator.list_runs()
    if runs:
        print(render.table(["Stored run", "Status", "Objective", "Updated"], [(row["id"], row["status"], truncate(row["objective"], 70), row["updated_at"]) for row in runs]))


def _print_help():
    rows = [
        ("/help", "show this help"),
        ("/quit, /exit", "leave Aether"),
        ("/new, /clear", "start a fresh session"),
        ("/status", "show provider and workspace status"),
        ("/provider <name> [model]", "switch provider"),
        ("/model <model>", "switch model on active provider"),
        ("/plan [status|checkpoints|resume <id>|text]", "inspect, resume, or set the active plan"),
        ("/tools", "list enabled tools"),
        ("/memory [list|add|search|delete|layer]", "manage memory"),
        ("/skills [list|view|discover|proposals|validate|history|versions]", "inspect skills and learning state"),
        ("/feedback <verified|failed|neutral> <text>", "record explicit outcome feedback"),
        ("/sessions, /resume <id>", "list or resume sessions"),
        ("/history [query]", "search previous messages"),
        ("/tasks", "list delegated tasks"),
        ("/agents [list|run|status|cancel]", "coordinate specialized agents"),
        ("/models [list|inspect|capabilities|routing|explain|performance|health]", "inspect model routing without a model call"),
        ("/schedule list|add|remove", "manage scheduled jobs"),
        ("/cost", "show rough local cost and token totals"),
        ("/doctor", "run environment checks"),
        ("/export <path>", "export current session JSON"),
    ]
    print(render.table(["Command", "Meaning"], rows))


def _model_command(agent, action: str, args: list[str]) -> None:
    registry = agent.model_router.registry
    manager = agent.provider_manager
    if action in ("list", "capabilities"):
        entries = registry.configured_entries(manager, role=agent.role or None)
        if args:
            provider = str(args[0] or "")
            model = str(args[1] or "") if len(args) > 1 else ""
            entries = [(provider, model)] if model else [(entry_provider, entry_model) for entry_provider, entry_model in entries if entry_provider == provider]
        rows = []
        for provider, model in entries:
            caps = registry.for_model(provider, model)
            window = caps.fact("context_window")
            price = caps.fact("input_pricing")
            rows.append(
                (
                    f"{provider}/{model}",
                    f"{window.value or 'unknown'} ({window.evidence})",
                    "yes" if caps.local else "no",
                    "yes" if caps.fact("credentials_configured").value else "no",
                    f"${price.value:.6f}" if isinstance(price.value, (int, float)) else "unknown",
                    truncate("; ".join(caps.restrictions), 60),
                )
            )
        print(render.table(["Model", "Context", "Local", "Ready", "Input price", "Notes"], rows) if rows else "(no configured models)")
        return
    if action == "inspect":
        provider = str(args[0] or manager.active_name)
        model = str(args[1] or manager.model)
        caps = registry.for_model(provider, model)
        payload = caps.to_dict()
        payload["health"] = (manager.health() or {}).get(provider, {"status": "unknown", "reason": ""})
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return
    if action in ("routing", "explain"):
        text = " ".join(args)
        requirements = classify_task(
            text,
            agent.config,
            agent.execution_plan,
            role=agent.role,
            explicit_provider=agent.explicit_provider,
            explicit_model=agent.explicit_model,
            avoid_models=list(agent.config.get("routing.avoid_models", []) or []),
        )
        decision = agent.model_router.route(requirements, manager, role=agent.role)
        if action == "explain":
            print(agent.model_router.explain(decision))
        else:
            print(json.dumps(decision.to_dict(), indent=2, ensure_ascii=False, default=str))
        return
    if action == "performance":
        rows = agent.store.list_model_performance(limit=None) or []
        print(
            render.table(
                ["Category", "Model", "Success", "Verified", "Samples", "Sources", "Cost known"],
                [
                    (
                        row["category"],
                        f"{row['provider']}/{row['model']}",
                        "yes" if row["success"] else "no",
                        "yes" if row["verified"] else "no",
                        str(row["tokens"]),
                        ",".join(row.get("sources") or []),
                        "yes" if row["cost_known"] else "no",
                    )
                    for row in rows
                ],
            )
            if rows
            else "(no recorded model performance)"
        )
        return
    if action == "health":
        health = manager.health() or {}
        print(
            render.table(
                ["Provider", "Status", "Retry in", "Reason"],
                [(name, item.get("status", ""), str(item.get("retry_after_seconds", 0)), truncate(str(item.get("reason") or ""), 80)) for name, item in health.items()],
            )
            if health
            else "(no provider health records)"
        )
        print(render.paint("Health is local state only; this command does not poll providers.", "dim"))
        return
    print(render.error_line("usage: /models list|inspect|capabilities|routing|explain|performance|health"))


def _agent_command(agent, parts):
    action = parts[0]
    args = parts[1:]
    if action in ("quit", "exit"):
        return True
    if action in ("new", "clear"):
        agent.clear_history()
        print(render.success_line("started a new session"))
        return False
    if action in ("help", "?"):
        _print_help()
        return False
    if action == "status":
        print(render.dashboard(agent.status_summary()))
        return False
    if action == "models":
        _model_command(agent, args[0] if args else "list", args[1:])
        return False
    if action == "provider" and args:
        provider = agent.switch_provider(args[0], args[1] if len(args) > 1 else None)
        agent.config.save()
        print(render.success_line(f"using {provider.name}/{provider.model}"))
        return False
    if action == "model" and args:
        provider = agent.switch_model(args[0])
        agent.config.save()
        print(render.success_line(f"using {provider.name}/{provider.model}"))
        return False
    if action == "plan":
        sub = args[0] if args else ""
        if sub == "status":
            if agent.execution_plan:
                print(json.dumps(agent.execution_plan.summary(), indent=2, ensure_ascii=False))
            else:
                print("(no active execution plan)")
        elif sub == "checkpoints":
            if agent.execution_plan:
                rows = agent.store.list_execution_checkpoints(agent.execution_plan.id)
                print(render.table(["ID", "Seq", "Phase", "Note", "Created"], [(row["id"], str(row["sequence"]), row["phase"], row["note"], row["created_at"]) for row in rows]) if rows else "(no checkpoints)")
            else:
                print("(no active execution plan)")
        elif sub == "resume" and len(args) > 1:
            row = agent.store.get_execution_plan(args[1])
            if not row:
                print(render.error_line(f"plan '{args[1]}' not found"))
                return False
            agent.execution_plan = ExecutionPlan.from_dict(row.get("plan") or {})
            agent.plan = agent.execution_plan.render()
            agent._refresh_executor_context()
            print(render.success_line(f"resumed plan {args[1]}"))
        elif args:
            agent.set_plan(" ".join(args))
            print(agent.plan or "(no active plan)")
        else:
            print(agent.execution_plan.render() if agent.execution_plan else (agent.plan or "(no active plan)"))
        return False
    if action == "tools":
        rows = [(name, tool.risk, "yes" if tool.parallel_safe else "no") for name, tool in agent.registry.tools.items()]
        print(render.table(["Tool", "Risk", "Parallel"], rows))
        return False
    if action == "memory":
        sub = args[0] if args else "list"
        user = "--user" in args
        if sub == "add":
            text = " ".join(item for item in args[1:] if item != "--user")
            agent.memory.add(text, user=user)
            print(render.success_line("memory saved"))
        elif sub == "search":
            query = " ".join(item for item in args[1:] if item != "--user")
            rows = agent.memory.search(query, user)
            print(render.table(["Category", "Entry"], rows) if rows else "(no matches)")
        elif sub == "list":
            rows = agent.memory.list(user)
            print(render.table(["Category", "Entry"], [(c, truncate(e, 100)) for c, e in rows]) if rows else "(empty)")
        elif sub == "layer" and len(args) >= 2:
            operation = args[1]
            layered = agent.layered_memory
            if operation == "list":
                rows = [
                    (item["id"][:12], item["layer"], item["subject"][:40], truncate(item["content"], 100))
                    for item in layered.list()
                ]
                print(render.table(["ID", "Layer", "Subject", "Content"], rows) if rows else "(empty)")
            elif operation == "add" and len(args) >= 4:
                item = layered.remember(args[2], " ".join(args[3:]), provenance="cli")
                print(render.success_line(item["id"]) if item else render.error_line("memory not saved"))
            elif operation in ("recall", "search") and len(args) >= 3:
                rows = [
                    (item["layer"], item["subject"][:40], truncate(item["content"], 120))
                    for item in layered.recall(" ".join(args[2:]))
                ]
                print(render.table(["Layer", "Subject", "Content"], rows) if rows else "(no matches)")
            elif operation == "counts":
                print(json.dumps(layered.counts(), indent=2))
            else:
                print(render.error_line("usage: /memory layer list|add <layer> <text>|recall <query>|counts"))
        elif sub == "delete" and len(args) >= 3:
            ok = agent.memory.delete(args[1], int(args[2]), user)
            print(render.success_line("deleted") if ok else render.error_line("no matching entry"))
        else:
            print(render.error_line("usage: /memory list|add <text>|search <query>|delete <category> <index>|layer ..."))
        return False
    if action == "skills":
        sub = args[0] if args else "list"
        if sub == "list":
            rows = [(item["name"], item["source"], item["description"][:80]) for item in agent.skills.list_skills()]
            print(render.table(["Skill", "Source", "Description"], rows))
        elif sub == "view" and len(args) > 1:
            skill = agent.skills.view(args[1])
            print(f"# {skill.name}\n\n{skill.body}")
        elif sub == "discover":
            proposals = agent.learning.discover(limit=5, query=" ".join(args[1:]))
            if not proposals:
                print("(no new skill proposals)")
            else:
                for proposal in proposals:
                    print(f"{proposal['skill_name']}: evidence={', '.join(proposal['evidence'][:5])}")
        elif sub == "proposals":
            rows = agent.learning.pending()
            print(render.table(
                ["ID", "Skill", "Kind", "Evidence"],
                [(row["id"][:16], row["skill_name"], row["kind"], str(len(row.get("evidence") or []))) for row in rows],
            ) if rows else "(no pending proposals)")
        elif sub == "validate" and len(args) > 1:
            validation = agent.learning.validate_proposal(args[1])
            print(json.dumps(validation, indent=2, ensure_ascii=False, default=str))
        elif sub == "history":
            history = agent.learning.history(skill_name=args[1] if len(args) > 1 else "", query=" ".join(args[2:]))
            print(json.dumps(history, indent=2, ensure_ascii=False, default=str)[:4000])
        elif sub == "versions" and len(args) > 1:
            rows = agent.learning.versions(args[1])
            print(render.table(
                ["Version", "Status", "Score"],
                [(str(row["version"]), row["status"], str(row["score"])) for row in rows],
            ) if rows else "(no stored versions)")
        else:
            print(render.error_line("usage: /skills list|view <name>|discover|proposals|validate <skill>|history [skill]|versions <skill>"))
        return False
    if action == "feedback" and args:
        result = agent.learning.record_feedback(" ".join(args[1:]), args[0], session_id=agent.session_id)
        print(render.success_line(f"recorded {result.get('verdict', args[0])} feedback") if result else render.error_line("learning is disabled"))
        return False
    if action == "sessions":
        rows = [(row["id"], row["title"][:40], row["provider"], row["updated_at"]) for row in agent.store.list_sessions()]
        print(render.table(["ID", "Title", "Provider", "Updated"], rows))
        return False
    if action == "resume" and args:
        session = agent.store.get_session(args[0])
        if not session:
            print(render.error_line(f"session '{args[0]}' not found"))
            return False
        agent.session_id = args[0]
        agent.history = agent._load_history()
        agent._refresh_executor_context()
        print(render.success_line(f"resumed {args[0]}"))
        return False
    if action == "history":
        query = " ".join(args)
        rows = agent.store.search_messages(query, limit=20) if query else []
        print(render.table(["Session", "Role", "Content"], [(r["session_id"], r["role"], truncate(r["content"], 100)) for r in rows]) if rows else "(no matches)")
        return False
    if action == "tasks":
        rows = [(row["id"], row["status"], row["title"][:70]) for row in agent.store.list_tasks()]
        print(render.table(["ID", "Status", "Title"], rows))
        return False
    if action == "agents":
        orchestrator = agent.orchestrator
        if orchestrator is None:
            print(render.error_line("orchestration is disabled in config"))
            return False
        sub = args[0] if args else "status"
        if sub == "list":
            print(render.table(["Role", "Provider/Model", "Iterations", "Tools"], _role_rows(agent.config)))
        elif sub == "status":
            print_agents_status(orchestrator)
        elif sub == "run" and len(args) >= 3:
            run = orchestrator.run(" ".join(args[2:]), roles=[args[1]])
            print(run.final_report)
            if run.status != "completed":
                print(render.error_line(f"run ended with status {run.status}"))
        elif sub == "cancel" and len(args) > 1:
            print(render.success_line("cancelled") if orchestrator.cancel(args[1]) else render.error_line("no matching task"))
        else:
            print(render.error_line("usage: /agents list|run <role> <task>|status|cancel <task-id>"))
        return False
    if action == "schedule":
        sub = args[0] if args else "list"
        if agent.scheduler is None:
            print(render.error_line("scheduler is disabled in config"))
        elif sub == "list":
            rows = [(job["id"], job["schedule"], job["next_run"], job["name"]) for job in agent.scheduler.list_jobs()]
            print(render.table(["ID", "Schedule", "Next", "Name"], rows))
        elif sub == "add" and len(args) >= 3:
            job = agent.scheduler.add_job(args[1], args[2], " ".join(args[3:]))
            print(render.success_line(f"added {job['id']}"))
        elif sub in ("remove", "cancel") and len(args) > 1:
            print(render.success_line("removed") if agent.scheduler.remove_job(args[1]) else render.error_line("no matching job"))
        elif sub == "pause" and len(args) > 1:
            job = agent.scheduler.set_enabled(args[1], False)
            print(render.success_line(f"paused {job['id']}") if job else render.error_line("no matching job"))
        elif sub == "resume" and len(args) > 1:
            job = agent.scheduler.set_enabled(args[1], True)
            print(render.success_line(f"resumed {job['id']}") if job else render.error_line("no matching job"))
        elif sub == "update" and len(args) >= 3:
            job = agent.scheduler.update_job(args[1], schedule=args[2])
            print(render.success_line(f"updated {job['id']}") if job else render.error_line("no matching job"))
        elif sub == "tick":
            print_schedule_summary(agent.scheduler.tick())
        else:
            print(render.error_line("usage: /schedule list|add <prompt> <schedule>|update <id> <schedule>|pause <id>|resume <id>|tick|remove <id>"))
        return False
    if action == "cost":
        usage = dict(agent.store.session_usage(agent.session_id))
        usage["estimated_cost"] = f"${float(usage['estimated_cost']):.6f} (estimate, not invoice)"
        usage["cost_known"] = "yes" if usage["cost_known"] else "no"
        usage["estimate_note"] = (
            "Includes unpriced calls excluded from the dollar estimate."
            if usage["unpriced_calls"]
            else "Rough estimate from local price table; verify provider billing."
        )
        print(render.table(["Metric", "Value"], [(key, str(value)) for key, value in usage.items()]))
        return False
    if action == "doctor":
        print(render_doctor(agent.config, Path(agent.home)))
        return False
    if action == "export":
        if not args:
            print(render.error_line("usage: /export <path>"))
            return False
        payload = agent.store.export_session(agent.session_id)
        atomic_json_write(Path(args[0]), payload)
        print(render.success_line(f"exported {args[0]}"))
        return False
    print(render.error_line(f"unknown command /{action}; try /help"))
    return False


def cmd_chat(args, config, home, scheduler=None):
    agent = make_agent(args, config, home, scheduler)
    print(render.banner(__version__))
    print(render.dashboard(agent.status_summary()))
    setup_completer()
    while True:
        try:
            raw = input(render.paint("aether> ", "cyan"))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        text = raw.strip()
        if not text:
            continue
        if text.startswith("/"):
            if _agent_command(agent, text[1:].split()):
                break
            continue
        stream_turn(agent, text, args)


def cmd_setup(args, config, home):
    config.save()
    print(render.success_line("Aether is configured"))
    rows = [
        ("Home", str(home)),
        ("Config", str(config.path)),
        ("Env", str(env_path())),
        ("Provider", str(config.get("provider"))),
        ("Model", str(config.get("model"))),
        ("Workspace", str(Path(os.environ.get("AETHER_WORKSPACE", Path.cwd())).resolve())),
    ]
    print(render.table(["Setting", "Value"], rows))
    print("\nNext steps:")
    print("  aether providers")
    print("  aether doctor")
    print("  aether run 'Say hello'")
    print("  ollama pull llama3.2:3b   # only if you choose local Ollama")
    return 0


def cmd_models(args, config, home):
    if args.action == "benchmark":
        from benchmarks.model_routing.runner import run_benchmark

        result = run_benchmark(config, samples=max(1, int(args.samples or 1)))
        result["billable_live_calls"] = False
        result["notice"] = "Offline deterministic benchmark; no model or network calls were made."
        if getattr(args, "confirm_billable", False):
            result["notice"] += " --confirm-billable acknowledged but no live calls are performed."
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    agent = make_agent(args, config, home)
    raw = getattr(args, "prompt", None) or [getattr(args, "provider", ""), getattr(args, "model", "")]
    values = [str(item) for item in raw if item]
    _model_command(agent, args.action, values)
    return 0


def cmd_providers(args, config, home):
    active = str(config.get("provider"))
    rows = []
    for name, spec in PROVIDERS.items():
        marker = "*" if name == active else ""
        rows.append((marker, name, spec.kind, spec.default_model, spec.cost, spec.limits))
    print(render.table(["", "Name", "Kind", "Default model", "Cost", "Limits"], rows))
    print(render.paint("\n* active. Models with :free are usually no-charge but rate-limited.", "dim"))
    return 0


def cmd_status(args, config, home):
    agent = make_agent(args, config, home)
    print(render.dashboard(agent.status_summary()))
    return 0


def render_doctor(config, home):
    lines = [render.paint("Aether doctor", "bold")]
    version = sys.version_info
    ok = version >= (3, 10)
    lines.append((render.success_line if ok else render.error_line)(f"Python {version.major}.{version.minor}.{version.micro}"))
    warnings = config.validate()
    if warnings:
        lines.extend(render.error_line(warning) for warning in warnings)
    else:
        lines.append(render.success_line("configuration valid"))
    lines.append(render.success_line(f"home writable: {home}"))
    try:
        store = Store(home / "state.db")
        lines.append(render.success_line(f"state database ok: {len(store.list_sessions())} sessions"))
    except Exception as exc:
        lines.append(render.error_line(f"state database failed: {exc}"))
    memory = MemoryStore(home, config.get("memory.char_limit", 4000))
    lines.append(render.success_line(f"memory entries: {len(memory.list()) + len(memory.list(True))}"))
    for binary in ("ollama", "git", "python3"):
        found = shutil.which(binary)
        lines.append((render.success_line if found else render.error_line)(f"{binary}: {found or 'not found'}"))
    provider = str(config.get("provider"))
    spec = PROVIDERS.get(provider)
    if spec:
        lines.append(render.success_line(f"selected provider: {provider} ({spec.kind})"))
        lines.append(render.paint("  " + spec.cost, "dim"))
        lines.append(render.paint("  " + spec.limits, "dim"))
    else:
        lines.append(render.error_line(f"unknown provider: {provider}"))
    return "\n".join(lines)


def cmd_doctor(args, config, home):
    print(render_doctor(config, home))
    if args.live:
        from urllib.request import urlopen

        spec = PROVIDERS.get(str(config.get("provider")))
        if not spec or not spec.base_url:
            print(render.error_line("no probeable base URL for active provider"))
            return 0
        if spec.api_mode == "mock":
            print(render.success_line("mock provider needs no network probe"))
            return 0
        try:
            with urlopen(spec.base_url + "/models", timeout=4) as response:
                print(render.success_line(f"endpoint responded: HTTP {response.status}"))
        except Exception as exc:
            print(render.error_line(f"endpoint probe failed: {redact(exc)}"))
    return 0


def cmd_config(args, config, home):
    if args.action == "get":
        value = config.get(args.key)
        print(json.dumps(redact_mapping({args.key: value})[args.key], indent=2, ensure_ascii=False))
    elif args.action == "set":
        try:
            value = json.loads(args.value)
        except ValueError:
            value = args.value
        config.set(args.key, value)
        config.save()
        print(render.success_line(f"set {args.key}"))
    else:
        print(json.dumps(redact_mapping(config.as_dict()), indent=2, ensure_ascii=False))
    return 0


def cmd_sessions(args, config, home):
    store = Store(home / "state.db")
    if args.action == "list":
        rows = [(row["id"], row["title"][:40], row["provider"], row["message_count"], row["updated_at"]) for row in store.list_sessions()]
        print(render.table(["ID", "Title", "Provider", "Msgs", "Updated"], rows))
    elif args.action == "show":
        payload = store.export_session(args.id)
        print(json.dumps(redact_mapping(payload), indent=2, ensure_ascii=False))
    elif args.action == "delete":
        print(render.success_line("deleted") if store.delete_session(args.id) else render.error_line("session not found"))
    elif args.action == "export":
        payload = store.export_session(args.id)
        if not payload:
            print(render.error_line("session not found"))
            return 1
        path = Path(args.path) if args.path else home / "exports" / f"{args.id}.json"
        atomic_json_write(path, payload)
        print(render.success_line(str(path)))
    else:
        payload = read_json(Path(args.path), {})
        if not isinstance(payload, dict):
            print(render.error_line("import file must contain a JSON object"))
            return 1
        print(render.success_line(store.import_session(payload)))
    return 0


def cmd_memory(args, config, home):
    if args.action == "layer":
        return cmd_memory_layer(args, config, home)
    store = MemoryStore(home, config.get("memory.char_limit", 4000))
    user = bool(getattr(args, "user", False))
    if args.action == "list":
        rows = store.list(user)
        print(render.table(["Category", "Entry"], [(c, truncate(e, 120)) for c, e in rows]) if rows else "(empty)")
    elif args.action == "add":
        store.add(args.text, args.category, user)
        print(render.success_line("memory saved"))
    elif args.action == "search":
        rows = store.search(args.query, user)
        print(render.table(["Category", "Entry"], rows) if rows else "(no matches)")
    elif args.action == "delete":
        print(render.success_line("deleted") if store.delete(args.category, args.index, user) else render.error_line("no matching entry"))
    elif args.action == "clear":
        store.clear(user)
        print(render.success_line("memory cleared"))
    elif args.action == "export":
        payload = store.export()
        path = Path(args.path) if args.path else home / "exports" / "memory.json"
        atomic_json_write(path, payload)
        print(render.success_line(str(path)))
    else:
        payload = read_json(Path(args.path), {})
        store.import_data(payload, merge=not args.replace)
        print(render.success_line("memory imported"))
    return 0


def cmd_memory_layer(args, config, home):
    markdown = MemoryStore(home, config.get("memory.char_limit", 4000))
    store = Store(home / "state.db")
    layered = LayeredMemory(markdown, store, config=config, persist=True)
    action = str(args.layer_action)
    if action == "list":
        rows = layered.list(layer=getattr(args, "layer", None), session_id=getattr(args, "session", None))
        rendered = [(row["id"][:12], row["layer"], row["subject"][:40], truncate(row["content"], 100), row["provenance"][:30]) for row in rows]
        print(render.table(["ID", "Layer", "Subject", "Content", "Source"], rendered) if rendered else "(empty)")
    elif action == "add":
        item = layered.remember(
            args.layer,
            args.content,
            subject=args.subject,
            provenance=args.provenance,
            confidence=args.confidence,
            session_id=args.session,
            expires_days=getattr(args, "expires_days", None),
            verified=bool(getattr(args, "verified", False)),
        )
        print(render.success_line(item["id"]) if item else render.error_line("memory not saved"))
    elif action == "recall":
        rows = layered.recall(
            getattr(args, "query", "") or "",
            limit=args.limit,
            layers=[args.layer] if getattr(args, "layer", None) else None,
            session_id=getattr(args, "session", None),
            max_chars=getattr(args, "max_chars", None),
        )
        rendered = [(row["layer"], row["subject"][:40], truncate(row["content"], 120), f"{float(row['confidence']):.2f}") for row in rows]
        print(render.table(["Layer", "Subject", "Content", "Confidence"], rendered) if rendered else "(no matches)")
    elif action == "context":
        context = layered.context(" ".join(args.task), max_chars=getattr(args, "max_chars", None))
        print(context or "(empty)")
    elif action == "correct":
        item = layered.correct(args.id, args.content, provenance=args.provenance, confidence=args.confidence)
        print(render.success_line(item["id"]) if item else render.error_line("no matching item"))
    elif action == "delete":
        print(render.success_line("deleted") if layered.delete(args.id) else render.error_line("no matching item"))
    elif action == "clear":
        print(render.success_line(f"cleared {layered.clear(layer=getattr(args, 'layer', None), session_id=getattr(args, 'session', None))}"))
    elif action == "consolidate":
        print(json.dumps(layered.consolidate(), indent=2))
    elif action == "prune":
        print(json.dumps({"expired": layered.prune_expired()}, indent=2))
    elif action == "migrate":
        print(json.dumps({"migrated": layered.migrate_markdown()}, indent=2))
    elif action == "counts":
        print(json.dumps(layered.counts(), indent=2))
    elif action == "export":
        path = Path(args.path) if args.path else home / "exports" / "memory-layers.json"
        atomic_json_write(path, layered.export_data())
        print(render.success_line(str(path)))
    else:
        payload = read_json(Path(args.path), {})
        print(render.success_line(f"imported {layered.import_data(payload, merge=not args.replace)}"))
    return 0


def _learning_components(config, home):
    from aether.learning import LearningEngine
    from aether.memory import LayeredMemory, MemoryStore
    from aether.skills import SkillEngine
    from aether.tools import default_registry

    store = Store(home / "state.db")
    skill_engine = SkillEngine(home, enabled=bool(config.get("skills.enabled", True)))
    memory = MemoryStore(home, int(config.get("memory.char_limit", 4000)))
    layered = LayeredMemory(memory, store, config=config, session_id="cli-learning")
    engine = LearningEngine(
        store,
        skill_engine,
        layered,
        config,
        list(default_registry(int(config.get("tools.max_result_chars", 16000))).tools),
    )
    return engine, skill_engine


def _show_proposal(proposal: dict) -> None:
    print(f"Proposal {proposal['id']}: {proposal['skill_name']} ({proposal['kind']}, {proposal['status']})")
    print("Evidence: " + ", ".join(str(item) for item in (proposal.get("evidence") or [])))
    print(truncate(proposal.get("content", ""), 1200))


def cmd_skills(args, config, home):
    engine, skill_engine = _learning_components(config, home)
    if args.action == "list":
        rows = [(item["name"], item["source"], item["views"], item["description"][:80]) for item in skill_engine.list_skills()]
        print(render.table(["Name", "Source", "Views", "Description"], rows))
        return 0
    if args.action == "view":
        skill = skill_engine.view(args.name)
        print(f"# {skill.name}\n\n{skill.body}")
        return 0
    if args.action == "create":
        skill_engine.create(args.name, args.description, args.body or "TODO: describe the procedure.")
        print(render.success_line(f"created {args.name}"))
        return 0
    if args.action == "edit":
        skill_engine.edit(args.name, args.body)
        print(render.success_line(f"updated {args.name}"))
        return 0
    if args.action == "discover":
        proposals = engine.discover(limit=args.limit, query=args.query)
        if not proposals:
            print("(no new skill proposals)")
            return 0
        for proposal in proposals:
            _show_proposal(proposal)
        return 0
    if args.action == "proposals":
        rows = engine.proposals(status=args.status, skill_name=args.skill)
        if not rows:
            print("(no proposals)")
            return 0
        print(render.table(
            ["ID", "Skill", "Kind", "Status", "Evidence"],
            [(row["id"][:16], row["skill_name"], row["kind"], row["status"], str(len(row.get("evidence") or []))) for row in rows],
        ))
        return 0
    if args.action == "validate":
        validation = engine.validate_proposal(args.skill)
        print(json.dumps(validation, indent=2, ensure_ascii=False, default=str))
        return 0 if validation.get("passed") else 1
    if args.action == "approve":
        proposal = next((row for row in engine.proposals() if row["id"] == args.proposal), None)
        if proposal is None:
            print(render.error_line(f"proposal '{args.proposal}' not found"))
            return 1
        _show_proposal(proposal)
        if not args.yes:
            print(render.error_line("approval not granted; rerun with --yes to save this skill"))
            return 1
        result = engine.approve_proposal(args.proposal, authorized=True, approver="cli-user")
        print(render.success_line(f"approved {result['skill']} version {result['version']}"))
        return 0
    if args.action == "reject":
        result = engine.reject_proposal(args.proposal, approver="cli-user", reason=args.reason)
        print(render.success_line(f"rejected {result['skill_name']}"))
        return 0
    if args.action == "history":
        history = engine.history(skill_name=args.skill or "", query=args.query, limit=args.limit)
        print(json.dumps(history, indent=2, ensure_ascii=False, default=str)[:8000])
        return 0
    if args.action == "versions":
        rows = engine.versions(args.skill)
        print(render.table(
            ["Version", "Status", "Score", "Proposal", "Created"],
            [(str(row["version"]), row["status"], str(row["score"]), row["proposal_id"][:16], row["created_at"]) for row in rows],
        ) if rows else "(no stored versions)")
        return 0
    if args.action == "rollback":
        row = next((item for item in engine.versions(args.skill) if int(item["version"]) == args.version), None)
        if row is None:
            print(render.error_line(f"version {args.version} of '{args.skill}' not found"))
            return 1
        print(truncate(row["content"], 1200))
        if not args.yes:
            print(render.error_line("approval not granted; rerun with --yes to activate this version"))
            return 1
        result = engine.rollback_skill(args.skill, args.version, authorized=True, approver="cli-user")
        print(render.success_line(f"active version is now {result['active_version']}"))
        return 0
    if args.action == "result":
        metrics = engine.record_skill_result(
            args.skill,
            success=args.success,
            verified=args.verified,
            duration_ms=args.duration_ms,
            tokens=args.tokens,
            cost=args.cost,
        )
        print(json.dumps(metrics, indent=2))
        return 0
    print(render.error_line(f"unknown skills action '{args.action}'"))
    return 1


def cmd_learning(args, config, home):
    engine, _ = _learning_components(config, home)
    if args.action == "feedback":
        result = engine.record_feedback(
            " ".join(args.text),
            args.verdict,
            experience_id=args.experience or "",
            session_id=args.session or "cli-learning",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:4000])
        return 0
    if args.action == "pending":
        rows = engine.pending()
        print(render.table(
            ["ID", "Skill", "Kind", "Created", "Evidence"],
            [(row["id"][:16], row["skill_name"], row["kind"], row["created_at"], str(len(row.get("evidence") or []))) for row in rows],
        ) if rows else "(no pending proposals)")
        return 0
    rows = engine.metrics(args.skill)
    print(json.dumps(rows, indent=2, ensure_ascii=False) if rows else "(no tracked skills)")
    return 0


def cmd_tasks(args, config, home):
    store = Store(home / "state.db")
    if args.action == "list":
        rows = [(row["id"], row["status"], row["title"][:80], row["updated_at"]) for row in store.list_tasks()]
        print(render.table(["ID", "Status", "Title", "Updated"], rows))
        return 0
    print(render.error_line("resume requires an interactive agent; use /resume <session> or delegate_task"))
    return 1


def cmd_plan(args, config, home):
    store = Store(home / "state.db")
    if args.action == "list":
        rows = [(row["id"], row["status"], row["complexity"], truncate(row["objective"], 70), row["updated_at"]) for row in store.list_execution_plans(limit=20)]
        print(render.table(["ID", "Status", "Complexity", "Objective", "Updated"], rows))
        return 0
    plan_id = getattr(args, "id", None)
    row = store.get_execution_plan(plan_id) if plan_id else None
    if row is None:
        rows = store.list_execution_plans(limit=1)
        row = rows[0] if rows else None
    if row is None:
        print(render.error_line("no execution plan found"))
        return 1
    plan = ExecutionPlan.from_dict(row.get("plan") or {})
    if args.action == "show":
        print(plan.render())
        return 0
    if args.action == "status":
        print(json.dumps(plan.summary(), indent=2, ensure_ascii=False))
        return 0
    if args.action == "checkpoints":
        rows = store.list_execution_checkpoints(plan.id)
        print(render.table(["ID", "Seq", "Phase", "Note", "Created"], [(item["id"], str(item["sequence"]), item["phase"], item["note"], item["created_at"]) for item in rows]) if rows else "(no checkpoints)")
        return 0
    if plan.session_id and not getattr(args, "session", None):
        args.session = plan.session_id
    agent = make_agent(args, config, home)
    agent.execution_plan = plan
    agent.plan = plan.render()
    agent._refresh_executor_context()
    result = stream_turn(agent, "resume", args)
    return 0 if result.exit_reason not in ("provider_error", "cost_limit") else 1


def cmd_agents(args, config, home, scheduler=None):
    store = Store(home / "state.db")
    orchestrator = Orchestrator(None, config, store=store)
    if args.action == "list":
        print(render.table(["Role", "Provider/Model", "Iterations", "Tools"], _role_rows(config)))
        return 0
    if args.action == "status":
        print_agents_status(orchestrator)
        return 0
    if args.action == "cancel":
        print(render.success_line("cancelled") if orchestrator.cancel(args.id) else render.error_line("no matching task"))
        return 0
    agent = make_agent(args, config, home, scheduler)
    if agent.orchestrator is None:
        print(render.error_line("orchestration is disabled in config"))
        return 1
    if args.action == "run":
        run = agent.orchestrator.run(" ".join(args.task), roles=[args.role])
        print(run.final_report)
        return 0 if run.status == "completed" else 1
    run = agent.orchestrator.resume(args.id)
    if run is None:
        print(render.error_line(f"run '{args.id}' not found"))
        return 1
    print(run.final_report)
    return 0 if run.status == "completed" else 1


def scheduled_runner(config, home):
    def run(prompt):
        provider = str(config.get("provider") or "unknown")
        model = str(config.get("model") or "")
        allow_paid = parse_bool(config.get("scheduler.allow_paid"), False) or parse_bool(os.environ.get("AETHER_CONFIRM_PAID"), False)
        if provider_is_billable(provider, model) and not allow_paid:
            raise RuntimeError(
                f"Scheduled execution with billable provider '{provider}' is disabled by default; "
                "set scheduler.allow_paid=true"
            )
        run_config = Config(config.as_dict())
        run_config.set("costs.confirm_paid", not allow_paid)
        run_config.set("orchestrator.allow_paid", False)
        run_config.set("orchestrator.enabled", False)
        run_config.set("tool_permissions.allow_tools", None)
        agent = Agent(
            run_config,
            home=home,
            persist=False,
            approve_callback=None,
            enable_subagents=False,
            enable_orchestrator=False,
        )
        result = agent.run_turn(prompt)
        if result.exit_reason in ("provider_error", "cost_limit"):
            raise RuntimeError(f"scheduled run stopped: {result.exit_reason}")
        return result.text

    return run


def print_schedule_summary(summary):
    rows = [[summary["due"], summary["executed"], summary["skipped"], summary["failed"]]]
    print(render.table(["Due", "Executed", "Skipped", "Failed"], rows))
    for outcome in summary["outcomes"]:
        detail = outcome.get("error") or outcome.get("reason") or outcome.get("result") or ""
        label = outcome.get("status", "unknown")
        suffix = f": {truncate(detail, 160)}" if detail else ""
        print(f"- {label} {outcome.get('job_id', '')}{suffix}")


def cmd_schedule(args, config, home):
    scheduler = Scheduler(config, home, runner=scheduled_runner(config, home))
    if args.action == "list":
        rows = [
            (job["id"], job["name"], job["schedule"], job["next_run"], str(job.get("enabled")), str(job.get("last_status") or "-"))
            for job in scheduler.list_jobs()
        ]
        print(render.table(["ID", "Name", "Schedule", "Next", "Enabled", "Last"], rows))
    elif args.action == "add":
        job = scheduler.add_job(args.prompt, args.schedule_time, args.name)
        print(render.success_line(job["id"]))
    elif args.action in ("remove", "cancel"):
        print(render.success_line("removed") if scheduler.remove_job(args.id) else render.error_line("job not found"))
    elif args.action == "update":
        job = scheduler.update_job(args.id, args.prompt, args.schedule_time, args.name)
        print(render.success_line(f"updated {job['id']}") if job else render.error_line("job not found"))
    elif args.action in ("pause", "resume"):
        job = scheduler.set_enabled(args.id, args.action == "resume")
        print(render.success_line(f"{args.action}d {job['id']}") if job else render.error_line("job not found"))
    else:
        print_schedule_summary(scheduler.tick())
    return 0


def cmd_run(args, config, home, scheduler=None):
    agent = make_agent(args, config, home, scheduler)
    result = stream_turn(agent, " ".join(args.prompt), args)
    return 0 if result.exit_reason not in ("provider_error", "cost_limit") else 1


def cmd_version(args, config, home):
    print(__version__)
    return 0


def cmd_update(args, config, home):
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        print(render.error_line("Aether was not installed from a git checkout"))
        return 1
    if not args.yes:
        print("This runs: git pull --ff-only && python3 -m pip install -e .")
        try:
            answer = input("Continue? [y/N] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("y", "yes"):
            return 0
    for command in (["git", "pull", "--ff-only"], [sys.executable, "-m", "pip", "install", "-e", "."]):
        completed = subprocess.run(command, cwd=str(root), check=False)
        if completed.returncode:
            print(render.error_line(f"command failed: {' '.join(command)}"))
            return completed.returncode
    print(render.success_line("update complete"))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config, home = prepare(args)
        scheduler = None
        if getattr(args, "command", None) not in ("version", "update") and parse_bool(config.get("scheduler.enabled"), False):
            scheduler = Scheduler(config, home, runner=scheduled_runner(config, home))
            if getattr(args, "func", None) in (cmd_chat, cmd_run, cmd_agents):
                scheduler.start()
        try:
            if getattr(args, "func", None) is None:
                return cmd_chat(args, config, home, scheduler)
            if args.func in (cmd_chat, cmd_run, cmd_agents):
                return args.func(args, config, home, scheduler)
            return args.func(args, config, home)
        finally:
            if scheduler:
                scheduler.stop()
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130
    except AetherError as exc:
        print(render.error_line(redact(exc)), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        if getattr(args, "debug", False):
            traceback.print_exc()
        print(render.error_line(redact(exc)), file=sys.stderr)
        return 1
