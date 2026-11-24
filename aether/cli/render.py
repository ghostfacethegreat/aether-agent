import os
import sys
import threading
import time

NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


def paint(text, color):
    if NO_COLOR:
        return str(text)
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def banner(version):
    lines = [
        "",
        paint("  ╭──────────────────────────────────────────╮", "cyan"),
        paint("  │", "cyan") + paint("  A E T H E R   •   local-first agent  ", "bold") + paint(" │", "cyan"),
        paint("  ╰──────────────────────────────────────────╯", "cyan"),
        paint(f"  v{version}  ·  type /help for commands", "dim"),
        "",
    ]
    return "\n".join(lines)


def dashboard(status):
    kind = status.get("kind", "unknown")
    kind_color = {"local": "green", "free-tier": "cyan", "mixed": "yellow", "paid": "red", "custom": "magenta"}.get(kind, "dim")
    rows = [
        ("Provider", f"{status.get('provider')} ({paint(kind, kind_color)})"),
        ("Model", str(status.get("model"))),
        ("Session", str(status.get("session"))),
        ("Context", f"{status.get('messages')} messages · {status.get('tools')} tools · {status.get('skills')} skills"),
        ("Memory", f"{status.get('memories')} entries"),
        ("Workspace", str(status.get("workspace"))),
        ("Cost", str(status.get("cost"))),
    ]
    width = max(len(label) for label, _ in rows)
    output = [paint("  Status", "bold")]
    for label, value in rows:
        output.append(f"  {label.ljust(width)}  {value}")
    output.append(paint("  " + str(status.get("limits")), "dim"))
    return "\n".join(output)


def tool_line(execution):
    mark = paint("✓", "green") if execution.ok else paint("✗", "red")
    detail = execution.error if not execution.ok else f"{execution.duration:.2f}s"
    return f"  {mark} {paint('tool', 'magenta')} {execution.name}  {paint(detail, 'dim')}"


def status_line(payload):
    kind = payload.get("kind")
    if kind == "provider_call":
        return paint(f"  · calling {payload.get('provider')}/{payload.get('model')}", "dim")
    if kind == "provider_error":
        return paint(f"  ! {payload.get('provider')}: {payload.get('error')}", "red")
    if kind == "routing_decision":
        decision = payload.get("decision") or {}
        return paint(f"  · routed to {decision.get('provider')}/{decision.get('model')}", "dim")
    if kind == "routing_limitation":
        return paint("  ! no suitable configured model for this task", "yellow")
    if kind == "routing_fallback":
        return paint(f"  · fallback {payload.get('from')} → {payload.get('to')}", "yellow")
    if kind == "context_overflow":
        return paint(f"  ! context overflow on {payload.get('provider')}; recovering", "yellow")
    if kind == "context_recovered":
        return paint(f"  · context recovered ({payload.get('restored_tool_results')} tool results restored)", "yellow")
    if kind == "context_compressed":
        return paint(f"  · context compressed ({payload.get('removed')} messages)", "yellow")
    if kind == "model_response":
        count = payload.get("tool_calls", 0)
        return paint(f"  · response received ({count} tool call{'s' if count != 1 else ''})", "dim")
    return ""


def reason_line(text):
    return paint("[reasoning] ", "yellow") + str(text)


def error_line(message):
    return paint("error: ", "red") + str(message)


def success_line(message):
    return paint("ok: ", "green") + str(message)


def table(headers, rows):
    widths = [len(str(header)) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    lines = ["  ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)).rstrip()]
    lines.append("  ".join("-" * width for width in widths).rstrip())
    for row in rows:
        lines.append("  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)).rstrip())
    return "\n".join(lines)


class Spinner:
    def __init__(self, message="thinking"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None
        self.active = False

    def start(self):
        if self.active or not sys.stdout.isatty() or NO_COLOR:
            return
        self.active = True
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        def loop():
            index = 0
            while not self._stop.wait(0.1):
                sys.stdout.write(f"\r  {frames[index % len(frames)]} {self.message}")
                sys.stdout.flush()
                index += 1
            sys.stdout.write("\r" + " " * (len(self.message) + 6) + "\r")
            sys.stdout.flush()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        if not self.active:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        self.active = False
        self._thread = None
        self._stop = threading.Event()
