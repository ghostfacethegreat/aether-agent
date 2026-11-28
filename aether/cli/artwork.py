"""Safe loading of user-supplied ANSI banner artwork.

Artwork is treated as text, never executed. Only Select Graphic Rendition (SGR)
color sequences are retained; cursor movement, OSC, and other terminal control
sequences are discarded.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

_MAX_BYTES = 32 * 1024
_MAX_LINES = 20
_MAX_WIDTH = 120


def _cell_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    if unicodedata.category(char) in {"Cf", "Cc", "Cs"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def sanitize_ansi_art(
    text: str,
    *,
    max_width: int = _MAX_WIDTH,
    max_lines: int = _MAX_LINES,
    allow_color: bool = True,
    allow_unicode: bool = True,
) -> str:
    """Return bounded printable art, retaining SGR color only."""
    max_width = max(1, min(int(max_width), _MAX_WIDTH))
    max_lines = max(1, min(int(max_lines), _MAX_LINES))
    output: list[str] = []
    line: list[str] = []
    width = 0
    has_sgr = False
    index = 0

    def finish_line() -> None:
        nonlocal line, width, has_sgr
        rendered = "".join(line)
        if has_sgr and allow_color:
            rendered += "\x1b[0m"
        output.append(rendered)
        line = []
        width = 0
        has_sgr = False

    while index < len(text) and len(output) < max_lines:
        char = text[index]
        if char == "\x1b":
            if index + 1 < len(text) and text[index + 1] == "[":
                end = index + 2
                while end < len(text) and not ("@" <= text[end] <= "~"):
                    end += 1
                if end < len(text):
                    final = text[end]
                    params = text[index + 2:end]
                    if final == "m" and len(params) <= 64 and all(c.isdigit() or c in ";:" for c in params) and allow_color:
                        line.append(text[index:end + 1])
                        has_sgr = True
                    index = end + 1
                    continue
                break
            if index + 1 < len(text) and text[index + 1] == "]":
                bel = text.find("\x07", index + 2)
                st = text.find("\x1b\\", index + 2)
                endings = [value for value in (bel, st) if value >= 0]
                if not endings:
                    break
                end = min(endings)
                index = end + (1 if end == bel else 2)
                continue
            index += 2 if index + 1 < len(text) else 1
            continue

        if char == "\r":
            if index + 1 < len(text) and text[index + 1] == "\n":
                index += 1
            finish_line()
            index += 1
            continue
        if char == "\n":
            finish_line()
            index += 1
            continue
        if char == "\t":
            char = " "
        cell_width = _cell_width(char)
        if cell_width == 0:
            index += 1
            continue
        if not allow_unicode and ord(char) > 127:
            return ""
        if width + cell_width > max_width:
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        line.append(char)
        width += cell_width
        index += 1

    if line and len(output) < max_lines:
        finish_line()
    return "\n".join(output).rstrip("\n")


def load_ansi_art(
    path: str | Path | None,
    *,
    max_width: int = _MAX_WIDTH,
    max_lines: int = _MAX_LINES,
    allow_color: bool = True,
    allow_unicode: bool = True,
) -> str | None:
    """Load a UTF-8 .ansi file, rejecting missing, oversized, or empty files."""
    if not path:
        return None
    try:
        candidate = Path(path).expanduser()
        if candidate.suffix.lower() not in {".ansi", ".txt"}:
            return None
        if candidate.stat().st_size > _MAX_BYTES:
            return None
        raw = candidate.read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > _MAX_BYTES:
            return None
        sanitized = sanitize_ansi_art(
            raw,
            max_width=max_width,
            max_lines=max_lines,
            allow_color=allow_color,
            allow_unicode=allow_unicode,
        )
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    if not sanitized.strip():
        return None
    return sanitized
