import os
import shutil
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
    "bright_blue": "\033[94m",
    "bright_cyan": "\033[96m",
    "bright_magenta": "\033[95m",
}

_THEME = "acid-blue"
_USE_UNICODE = True
_SHOW_BANNER = True
_SHOW_DASHBOARD = True
_SHOW_RESPONSE_LABELS = True


def configure(settings=None):
    """Configure presentation without changing agent behavior or global terminal settings."""
    global _THEME, _USE_UNICODE, _SHOW_BANNER, _SHOW_DASHBOARD, _SHOW_RESPONSE_LABELS

    settings = settings if isinstance(settings, dict) else {}
    theme = str(settings.get("theme", "acid-blue")).strip().lower()
    _THEME = theme if theme in {"acid-blue", "classic", "mono"} else "acid-blue"
    _USE_UNICODE = settings.get("unicode", True) is not False
    if os.environ.get("AETHER_ASCII", "").strip().lower() in {"1", "true", "yes", "on"}:
        _USE_UNICODE = False
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "█░─".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        _USE_UNICODE = False
    _SHOW_BANNER = settings.get("show_banner", True) is not False
    _SHOW_DASHBOARD = settings.get("show_dashboard", True) is not False
    _SHOW_RESPONSE_LABELS = settings.get("show_response_labels", True) is not False


def paint(text, color):
    value = str(text)
    if NO_COLOR or _THEME == "mono":
        return value
    code = COLORS.get(color, "")
    if not code:
        return value
    if _THEME == "acid-blue":
        code = {"blue": COLORS["bright_blue"], "cyan": COLORS["bright_cyan"]}.get(color, code)
    return f"{code}{value}{COLORS['reset']}"


def terminal_width(default=80):
    try:
        return max(32, shutil.get_terminal_size((default, 24)).columns)
    except (OSError, ValueError):
        return default


def _clip(value, width):
    text = str(value)
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 1] + "…"


def _glyph_rows():
    glyphs = {
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
        "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    }
    word = "AETHER"
    filled = "█" if _USE_UNICODE else "#"
    rows = []
    for row_index in range(7):
        pieces = []
        for letter in word:
            pieces.append("".join(filled if bit == "1" else " " for bit in glyphs[letter][row_index]))
        rows.append(" ".join(pieces))
    return rows


def banner(version):
    if not _SHOW_BANNER:
        return ""
    width = terminal_width()
    if width >= 48:
        rows = _glyph_rows()
        logo = []
        for row in rows:
            line = "  " + row
            if _USE_UNICODE:
                line += paint(" ░", "cyan")
            logo.append(paint(line, "bright_blue"))
        if _USE_UNICODE:
            logo.append(paint("   " + "░" * min(len(rows[0]), max(8, width - 12)), "blue"))
    else:
        logo = [paint("  AETHER", "bright_blue" if _THEME != "classic" else "cyan")]

    dot = " · " if _USE_UNICODE else " | "
    tagline = _clip("  LOCAL-FIRST AGENT" + dot + "MEMORY / TOOLS / LEARNING", max(12, width - 4))
    divider = "─" if _USE_UNICODE else "-"
    footer = _clip(f"  v{version}  {dot.strip()}  /help for commands", max(12, width - 4))
    rule = paint("  " + divider * min(58, max(24, width - 4)), "blue")
    return "\n".join(["", *logo, paint(tagline, "cyan"), paint(footer, "dim"), rule, ""])


def dashboard(status):
    if not _SHOW_DASHBOARD:
        return ""
    kind = status.get("kind", "unknown")
    rows = [
        ("PROVIDER", f"{status.get('provider')} ({kind})"),
        ("MODEL", str(status.get("model"))),
        ("SESSION", str(status.get("session"))),
        ("CONTEXT", f"{status.get('messages')} messages · {status.get('tools')} tools · {status.get('skills')} skills"),
        ("MEMORY", f"{status.get('memories')} entries"),
        ("WORKSPACE", str(status.get("workspace"))),
        ("COST", str(status.get("cost"))),
    ]
    limits = status.get("limits")
    if limits:
        rows.append(("LIMITS", str(limits)))

    width = min(76, terminal_width() - 4)
    label_width = 9
    value_width = width - 16
    if width < 48:
        compact_width = max(12, terminal_width() - 15)
        return "\n".join(
            "  " + label.ljust(label_width) + " " + _clip(value, compact_width)
            for label, value in rows
        )

    if _USE_UNICODE:
        top_left, horizontal, top_right = "┌", "─", "┐"
        vertical, bottom_left, bottom_right = "│", "└", "┘"
    else:
        top_left, horizontal, top_right = "+", "-", "+"
        vertical, bottom_left, bottom_right = "|", "+", "+"

    lines = [
        paint("  SESSION OVERVIEW", "bold"),
        "  " + top_left + horizontal * (width - 4) + top_right,
    ]
    for label, value in rows:
        visible = _clip(value, value_width)
        line = "  " + vertical + " " + paint(label.ljust(label_width), "bright_cyan") + " " + visible.ljust(value_width) + " " + vertical
        lines.append(line)
    lines.append("  " + bottom_left + horizontal * (width - 4) + bottom_right)
    return "\n".join(lines)


def hint_line():
    dot = " · " if _USE_UNICODE else " | "
    return paint("  /help commands" + dot + "/status runtime" + dot + "/new session", "dim")


def prompt():
    marker = "❯" if _USE_UNICODE else ">"
    sigil = "◈" if _USE_UNICODE else "*"
    return paint("  " + sigil, "bright_blue") + " " + paint("aether", "bold") + " " + paint(marker + " ", "cyan")


def assistant_prefix():
    if not _SHOW_RESPONSE_LABELS:
        return ""
    marker = "◆" if _USE_UNICODE else "*"
    rule = "─" if _USE_UNICODE else "-"
    return "\n" + paint(f"  {marker} AETHER", "bright_blue") + " " + paint(rule * 14, "dim") + "\n  "


def reasoning_prefix():
    if not _SHOW_RESPONSE_LABELS:
        return ""
    marker = "◇" if _USE_UNICODE else "+"
    return "\n" + paint(f"  {marker} REASONING", "yellow") + "\n  "


def dashboard_separator():
    char = "─" if _USE_UNICODE else "-"
    return paint("  " + char * min(58, max(24, terminal_width() - 4)), "dim")


def tool_line(execution):
    if _USE_UNICODE:
        mark = paint("✓", "green") if execution.ok else paint("✗", "red")
    else:
        mark = paint("+", "green") if execution.ok else paint("x", "red")
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
        arrow = "→" if _USE_UNICODE else "->"
        return paint(f"  · fallback {payload.get('from')} {arrow} {payload.get('to')}", "yellow")
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
        if self.active or not sys.stdout.isatty():
            return
        self.active = True
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" if _USE_UNICODE else "|/-\\"

        def loop():
            index = 0
            while not self._stop.wait(0.1):
                frame = frames[index % len(frames)]
                sys.stdout.write(f"\r  {paint(frame, 'bright_cyan')} {self.message}")
                sys.stdout.flush()
                index += 1
            sys.stdout.write("\r" + " " * (len(self.message) + 8) + "\r")
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
