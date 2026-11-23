import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from aether import __version__
from aether.config import load_config, load_environment
from aether.core import Agent
from aether.errors import AetherError
from aether.home import aether_home, env_path
from aether.logging import get_logger, set_level
from aether.memory import MemoryStore
from aether.persistence import Store
from aether.providers.catalog import PROVIDERS, provider_spec
from aether.tasks import Scheduler
from aether.utils import parse_bool, read_json, redact, redact_mapping, truncate, atomic_json_write

from . import render


SLASH_COMMANDS = [
    "/help", "/quit", "/exit", "/new", "/clear", "/status", "/provider", "/model",
    "/plan", "/tools", "/memory", "/skills", "/sessions", "/resume", "/history",
    "/tasks", "/schedule", "/cost", "/doctor", "/export",
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

    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="Create and explain local configuration")
    p_setup.set_defaults(func=cmd_setup)

    p_providers = sub.add_parser("providers", help="List providers with honest cost and limit notes")
    p_providers.set_defaults(func=cmd_providers)

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

    p_tasks = sub.add_parser("tasks", help="Inspect delegated task ledger")
    tasks = p_tasks.add_subparsers(dest="action", required=True)
    tasks_list = tasks.add_parser("list")
    tasks_list.set_defaults(func=cmd_tasks)
    tasks_resume = tasks.add_parser("resume")
    tasks_resume.add_argument("id")
    tasks_resume.set_defaults(func=cmd_tasks)

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


def _print_help():
    rows = [
        ("/help", "show this help"),
        ("/quit, /exit", "leave Aether"),
        ("/new, /clear", "start a fresh session"),
        ("/status", "show provider and workspace status"),
        ("/provider <name> [model]", "switch provider"),
        ("/model <model>", "switch model on active provider"),
        ("/plan [text]", "show or set the active plan"),
        ("/tools", "list enabled tools"),
        ("/memory [list|add|search|delete]", "manage memory"),
        ("/skills [list|view]", "inspect skills"),
        ("/sessions, /resume <id>", "list or resume sessions"),
        ("/history [query]", "search previous messages"),
        ("/tasks", "list delegated tasks"),
        ("/schedule list|add|remove", "manage scheduled jobs"),
        ("/cost", "show local usage totals"),
        ("/doctor", "run environment checks"),
        ("/export <path>", "export current session JSON"),
    ]
    print(render.table(["Command", "Meaning"], rows))


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
        if args:
            agent.set_plan(" ".join(args))
        print(agent.plan or "(no active plan)")
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
        elif sub == "delete" and len(args) >= 3:
            ok = agent.memory.delete(args[1], int(args[2]), user)
            print(render.success_line("deleted") if ok else render.error_line("no matching entry"))
        else:
            print(render.error_line("usage: /memory list|add <text>|search <query>|delete <category> <index>"))
        return False
    if action == "skills":
        sub = args[0] if args else "list"
        if sub == "list":
            rows = [(item["name"], item["source"], item["description"][:80]) for item in agent.skills.list_skills()]
            print(render.table(["Skill", "Source", "Description"], rows))
        elif sub == "view" and len(args) > 1:
            skill = agent.skills.view(args[1])
            print(f"# {skill.name}\n\n{skill.body}")
        else:
            print(render.error_line("usage: /skills list|view <name>"))
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
        usage = agent.store.session_usage(agent.session_id)
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


def cmd_skills(args, config, home):
    from aether.skills import SkillEngine

    engine = SkillEngine(home, enabled=bool(config.get("skills.enabled", True)))
    if args.action == "list":
        rows = [(item["name"], item["source"], item["views"], item["description"][:80]) for item in engine.list_skills()]
        print(render.table(["Name", "Source", "Views", "Description"], rows))
    elif args.action == "view":
        skill = engine.view(args.name)
        print(f"# {skill.name}\n\n{skill.body}")
    elif args.action == "create":
        engine.create(args.name, args.description, args.body or "TODO: describe the procedure.")
        print(render.success_line(f"created {args.name}"))
    else:
        engine.edit(args.name, args.body)
        print(render.success_line(f"updated {args.name}"))
    return 0


def cmd_tasks(args, config, home):
    store = Store(home / "state.db")
    if args.action == "list":
        rows = [(row["id"], row["status"], row["title"][:80], row["updated_at"]) for row in store.list_tasks()]
        print(render.table(["ID", "Status", "Title", "Updated"], rows))
        return 0
    print(render.error_line("resume requires an interactive agent; use /resume <session> or delegate_task"))
    return 1


def scheduled_runner(config, home):
    spec = provider_spec(str(config.get("provider") or ""))
    blocked = ""
    if (spec is None or spec.kind not in ("local", "free-tier")) and not parse_bool(config.get("scheduler.allow_paid"), False):
        provider = str(config.get("provider") or "unknown")
        blocked = f"Scheduled execution with provider '{provider}' is disabled by default; set scheduler.allow_paid=true"

    def run(prompt):
        if blocked:
            raise RuntimeError(blocked)
        agent = Agent(config, home=home, persist=False, approve_callback=None)
        result = agent.run_turn(prompt)
        if result.exit_reason == "provider_error":
            raise RuntimeError("provider error during scheduled run")
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
    return 0 if result.exit_reason != "provider_error" else 1


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
            if getattr(args, "func", None) in (cmd_chat, cmd_run):
                scheduler.start()
        try:
            if getattr(args, "func", None) is None:
                return cmd_chat(args, config, home, scheduler)
            if args.func in (cmd_chat, cmd_run):
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
