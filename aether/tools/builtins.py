import json
import os
import shlex
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from aether.errors import ToolError

from .registry import Tool


def _workspace(context) -> Path:
    return Path(context.get("workspace") or Path.cwd()).resolve()


def _path(context, raw) -> Path:
    path = Path(str(raw or "")).expanduser()
    return path if path.is_absolute() else (_workspace(context) / path)


def _text(result) -> str:
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            if "result__a" in str(attrs.get("class", "")) or attrs.get("data-testid") == "result-title-a":
                self._anchor = {"title": "", "url": attrs.get("href", "")}

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            if self._anchor["title"].strip():
                self.links.append(self._anchor)
            self._anchor = None


def _fetch_url(url: str, max_bytes=262144, timeout=15, headers=None) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ToolError("Only http and https URLs are supported")
    if parsed.username or parsed.password:
        raise ToolError("URLs with embedded credentials are not allowed")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Aether/0.1 (research assistant)", "Accept": "text/html,text/plain,*/*", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes)
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "replace")


def _html_to_text(html: str) -> str:
    class Extractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self.skip += 1
            if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript") and self.skip:
                self.skip -= 1

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    parser = Extractor()
    parser.feed(html)
    lines = [line.strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def list_directory(args, context):
    path = _path(context, args.get("path") or ".")
    if not path.exists():
        raise ToolError(f"Directory does not exist: {path}")
    if not path.is_dir():
        raise ToolError(f"Not a directory: {path}")
    entries = []
    for item in sorted(path.iterdir(), key=lambda item: item.name)[:500]:
        kind = "dir" if item.is_dir() else "file"
        try:
            size = item.stat().st_size if item.is_file() else 0
        except OSError:
            size = 0
        entries.append(f"{kind} {item.name} {size}")
    return "\n".join(entries) or "(empty)"


def read_file(args, context):
    path = _path(context, args.get("path"))
    if not path.exists():
        raise ToolError(f"File does not exist: {path}")
    if not path.is_file():
        raise ToolError(f"Not a file: {path}")
    raw = path.read_bytes()[: 4 * 1024 * 1024]
    if b"\x00" in raw:
        raise ToolError("Refusing to read a binary file")
    lines = raw.decode("utf-8", "replace").splitlines()
    offset = max(0, int(args.get("offset", 0)))
    limit = min(5000, max(1, int(args.get("limit", 2000))))
    selected = lines[offset : offset + limit]
    numbered = [f"{index + offset + 1}: {line}" for index, line in enumerate(selected)]
    return "\n".join(numbered) or "(empty file)"


def write_file(args, context):
    path = _path(context, args.get("path"))
    content = str(args.get("content") or "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}"


def edit_file(args, context):
    path = _path(context, args.get("path"))
    if not path.is_file():
        raise ToolError(f"File does not exist: {path}")
    old = str(args.get("old") or "")
    new = str(args.get("new") or "")
    if not old:
        raise ToolError("edit_file requires a non-empty 'old' string")
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if not count:
        raise ToolError("The requested text was not found in the file")
    if args.get("replace_all"):
        updated = text.replace(old, new)
    else:
        updated = text.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return f"Replaced {count if args.get('replace_all') else 1} occurrence(s) in {path}"


def terminal(args, context):
    command = str(args.get("command") or "").strip()
    if not command:
        raise ToolError("terminal requires a command")
    timeout = min(600, int(args.get("timeout") or context["config"].get("tools.timeout", 30)))
    cwd = _path(context, args.get("cwd") or ".") if args.get("cwd") else _workspace(context)
    if not cwd.is_dir():
        raise ToolError(f"Working directory does not exist: {cwd}")
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"Command timed out after {timeout}s") from None
    output = (completed.stdout or "") + (completed.stderr or "")
    return _text({"exit_code": completed.returncode, "output": output.strip() or "(no output)"})


def git(args, context):
    subcommand = str(args.get("subcommand") or "status").strip()
    allowed = {"status", "diff", "log", "add", "commit", "branch"}
    if subcommand not in allowed:
        raise ToolError(f"Unsupported git subcommand '{subcommand}'. Use: {', '.join(sorted(allowed))}")
    repo = _path(context, args.get("path") or ".")
    if not repo.is_dir():
        raise ToolError(f"Repository path does not exist: {repo}")
    command = ["git", "-C", str(repo), subcommand]
    if subcommand == "add":
        targets = args.get("paths") or ["."]
        command.extend(shlex.split(" ".join(str(item) for item in targets)))
    elif subcommand == "commit":
        message = str(args.get("message") or "").strip()
        if not message:
            raise ToolError("git commit requires a message")
        command.extend(["-m", message])
    elif subcommand == "log":
        command.extend(["--oneline", "-n", str(min(100, int(args.get("limit", 20))))])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"git {subcommand} failed: {exc}") from exc
    return _text(
        {
            "exit_code": completed.returncode,
            "output": ((completed.stdout or "") + (completed.stderr or "")).strip() or "(no output)",
        }
    )


def python_run(args, context):
    if not context["config"].get("tools.python_enabled", True):
        raise ToolError("Python execution is disabled in config")
    code = str(args.get("code") or "").strip()
    if not code:
        raise ToolError("python requires code")
    timeout = min(120, int(args.get("timeout") or context["config"].get("tools.timeout", 30)))
    try:
        completed = subprocess.run(
            ["python3", "-c", code],
            cwd=str(_workspace(context)),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"python execution failed: {exc}") from exc
    return _text(
        {
            "exit_code": completed.returncode,
            "output": ((completed.stdout or "") + (completed.stderr or "")).strip() or "(no output)",
        }
    )


def web_fetch(args, context):
    url = str(args.get("url") or "")
    max_bytes = int(context["config"].get("integrations.web_fetch.max_bytes", 262144))
    content = _fetch_url(url, max_bytes=max_bytes)
    if args.get("raw"):
        return content
    return _html_to_text(content)


def web_search(args, context):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolError("web_search requires a query")
    settings = context["config"].get("integrations.web_search", {}) or {}
    provider = str(settings.get("provider") or "duckduckgo")
    limit = min(10, max(1, int(args.get("limit", 5))))
    if provider in ("brave", "serper"):
        key = os.environ.get(str(settings.get("api_key_env") or ("BRAVE_API_KEY" if provider == "brave" else "SERPER_API_KEY")), "")
        if not key:
            raise ToolError(f"{provider} search requires an API key; configure api_key_env or use provider=duckduckgo")
        if provider == "brave":
            url = "https://api.search.brave.com/res/v1/web/search?q=" + urllib.parse.quote(query)
            rows = json.loads(_fetch_url(url, headers={"X-Subscription-Token": key})).get("web", {}).get("results", [])[:limit]
            return _text([{"title": row.get("title"), "url": row.get("url"), "snippet": row.get("description")} for row in rows])
        request = urllib.request.Request(
            "https://google.serper.dev/search",
            data=json.dumps({"q": query, "num": limit}).encode(),
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            rows = json.loads(response.read().decode()).get("organic", [])[:limit]
        return _text([{"title": row.get("title"), "url": row.get("link"), "snippet": row.get("snippet")} for row in rows])
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        html = _fetch_url(url)
    except (urllib.error.URLError, OSError, ToolError) as exc:
        raise ToolError(f"Web search is unavailable: {exc}. Provide a keyed search provider in config for reliability.") from exc
    parser = _LinkParser()
    parser.feed(html)
    return _text([{"title": item["title"], "url": urllib.parse.unquote(item["url"])} for item in parser.links[:limit]])


def browser(args, context):
    settings = context["config"].get("integrations.browser", {}) or {}
    command = str(settings.get("command") or "").strip()
    if not settings.get("enabled") or not command:
        raise ToolError(
            "Browser automation is disabled. Configure integrations.browser.enabled=true and a command template in config. "
            "Aether does not bundle or pay for a browser service."
        )
    url = str(args.get("url") or "")
    action = str(args.get("action") or "open")
    rendered = command.replace("{url}", shlex.quote(url)).replace("{action}", shlex.quote(action))
    try:
        completed = subprocess.run(rendered, shell=True, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"Browser command failed: {exc}") from exc
    return _text(
        {
            "exit_code": completed.returncode,
            "output": ((completed.stdout or "") + (completed.stderr or "")).strip() or "(no output)",
        }
    )


def memory_tool(args, context):
    store = context["memory"]
    action = str(args.get("action") or "list").lower()
    user = bool(args.get("user"))
    if action == "add":
        store.add(str(args.get("text") or ""), str(args.get("category") or "general"), user)
        return "Memory saved"
    if action == "list":
        return _text([{"category": category, "entry": entry} for category, entry in store.list(user)])
    if action == "search":
        return _text([{"category": category, "entry": entry} for category, entry in store.search(str(args.get("query") or ""), user)])
    if action == "replace":
        ok = store.replace(
            str(args.get("category") or "general"),
            int(args.get("index", -1)),
            str(args.get("text") or ""),
            user,
        )
        return "Memory updated" if ok else "No matching memory entry"
    if action == "delete":
        ok = store.delete(str(args.get("category") or "general"), int(args.get("index", -1)), user)
        return "Memory deleted" if ok else "No matching memory entry"
    if action == "export":
        return _text(store.export())
    if action == "import":
        data = args.get("data")
        if args.get("path"):
            data = json.loads(_path(context, args["path"]).read_text(encoding="utf-8"))
        store.import_data(data, merge=not args.get("replace"))
        return "Memory imported"
    raise ToolError(f"Unknown memory action '{action}'")


def skill_tool(args, context):
    engine = context["skills"]
    action = str(args.get("action") or "list").lower()
    if action == "list":
        return _text(engine.list_skills())
    if action == "view":
        skill = engine.view(str(args.get("name") or ""))
        return f"# {skill.name}\n\n{skill.body}"
    if action == "create":
        path = engine.create(
            str(args.get("name") or ""),
            str(args.get("description") or ""),
            str(args.get("body") or ""),
        )
        return f"Created skill at {path}"
    if action == "edit":
        path = engine.edit(str(args.get("name") or ""), str(args.get("body") or ""))
        return f"Updated skill at {path}"
    raise ToolError(f"Unknown skill action '{action}'")


def delegate_task(args, context):
    manager = context.get("subagents")
    if manager is None:
        raise ToolError("Subagent execution is not available in this context")
    tasks = args.get("tasks")
    if tasks is None:
        tasks = [{"goal": args.get("goal") or "", "context": args.get("context") or ""}]
    return _text(manager.run(tasks, context))


def todo_tool(args, context):
    text = str(args.get("plan") or args.get("text") or "").strip()
    callback = context.get("set_plan")
    if callback:
        callback(text)
    if context.get("store") and args.get("title"):
        task_id = context["store"].create_task(str(args["title"]), context.get("session_id", ""), context.get("parent_id", ""))
        if args.get("status"):
            context["store"].update_task(task_id, str(args["status"]), text)
    return f"Plan updated: {text or '(cleared)'}"


def session_search(args, context):
    store = context.get("store")
    if not store:
        raise ToolError("Session storage is not available")
    rows = store.search_messages(str(args.get("query") or ""), int(args.get("limit", 10)))
    return _text(rows)


def scheduler_tool(args, context):
    scheduler = context.get("scheduler")
    if not scheduler:
        raise ToolError("Scheduler is not available")
    action = str(args.get("action") or "list").lower()
    if action == "list":
        return _text(scheduler.list_jobs())
    if action == "add":
        job = scheduler.add_job(str(args.get("prompt") or ""), str(args.get("schedule") or ""), str(args.get("name") or ""))
        return _text(job)
    if action == "remove":
        return "Removed" if scheduler.remove_job(str(args.get("id") or "")) else "No matching job"
    raise ToolError(f"Unknown scheduler action '{action}'")


TOOLS = [
    Tool(
        "list_directory",
        "List files and directories. Use before reading unknown paths.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": []},
        list_directory,
        "read",
        True,
    ),
    Tool(
        "read_file",
        "Read a UTF-8 text file with line numbers and optional pagination.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
            "required": ["path"],
        },
        read_file,
        "read",
        True,
    ),
    Tool(
        "write_file",
        "Create or overwrite a text file. Parent directories are created automatically.",
        {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
        write_file,
        "write",
    ),
    Tool(
        "edit_file",
        "Replace text in an existing file. Prefer this over rewriting whole files.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old", "new"],
        },
        edit_file,
        "write",
    ),
    Tool(
        "terminal",
        "Run a shell command in the workspace. Destructive commands require user approval.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["command"],
        },
        terminal,
        "execute",
    ),
    Tool(
        "git",
        "Run a safe git subcommand: status, diff, log, branch, add, or commit.",
        {
            "type": "object",
            "properties": {
                "subcommand": {"type": "string"},
                "path": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "message": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["subcommand"],
        },
        git,
        "execute",
    ),
    Tool(
        "python",
        "Execute Python code in a short-lived subprocess. Not a security sandbox.",
        {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["code"]},
        python_run,
        "execute",
    ),
    Tool(
        "web_fetch",
        "Fetch a public HTTP(S) URL and convert HTML to readable text.",
        {"type": "object", "properties": {"url": {"type": "string"}, "raw": {"type": "boolean"}}, "required": ["url"]},
        web_fetch,
        "network",
        True,
    ),
    Tool(
        "web_search",
        "Search the web. Uses DuckDuckGo HTML by default; optional keyed providers are supported.",
        {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        web_search,
        "network",
        True,
    ),
    Tool(
        "browser",
        "Open a URL through a configured local browser command. Disabled by default.",
        {
            "type": "object",
            "properties": {"action": {"type": "string"}, "url": {"type": "string"}},
            "required": ["action", "url"],
        },
        browser,
        "network",
    ),
    Tool(
        "memory",
        "Manage persistent memory: add, list, search, replace, delete, export, import.",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "text": {"type": "string"},
                "category": {"type": "string"},
                "query": {"type": "string"},
                "index": {"type": "integer"},
                "user": {"type": "boolean"},
                "path": {"type": "string"},
                "data": {},
                "replace": {"type": "boolean"},
            },
            "required": ["action"],
        },
        memory_tool,
        "write",
    ),
    Tool(
        "skill",
        "Discover, view, create, and edit reusable skills (SKILL.md files).",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["action"],
        },
        skill_tool,
        "write",
    ),
    Tool(
        "delegate_task",
        "Run independent tasks in parallel subagents with isolated conversations and read-only tools.",
        {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"goal": {"type": "string"}, "context": {"type": "string"}, "role": {"type": "string"}},
                        "required": ["goal"],
                    },
                },
            },
            "required": [],
        },
        delegate_task,
        "execute",
    ),
    Tool(
        "todo",
        "Record or clear the active plan shown to the user and included in system context.",
        {"type": "object", "properties": {"plan": {"type": "string"}, "title": {"type": "string"}, "status": {"type": "string"}}, "required": []},
        todo_tool,
        "low",
        True,
    ),
    Tool(
        "session_search",
        "Search previous conversations stored locally.",
        {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        session_search,
        "read",
        True,
    ),
    Tool(
        "scheduler",
        "List, add, or remove local scheduled jobs.",
        {
            "type": "object",
            "properties": {"action": {"type": "string"}, "prompt": {"type": "string"}, "schedule": {"type": "string"}, "name": {"type": "string"}, "id": {"type": "string"}},
            "required": ["action"],
        },
        scheduler_tool,
        "write",
    ),
]


def default_registry(max_result_chars=16000) -> "ToolRegistry":
    from .registry import ToolRegistry

    registry = ToolRegistry(max_result_chars)
    for tool in TOOLS:
        registry.register(tool)
    return registry
