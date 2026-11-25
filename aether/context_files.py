from pathlib import Path

DEFAULT_FILENAMES = (
    "AGENTS.md", "AETHER.md", ".aether.md", "CLAUDE.md",
    "SOUL.md", ".cursorrules", ".hermes.md",
)


def _setting(config, key, default):
    try:
        return config.get("context_files." + key, default)
    except (AttributeError, TypeError):
        return default


def _bounded_int(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def load_project_context(workspace, config) -> str:
    """Load bounded, root-only project guidance; never recurse or access the network."""
    if _setting(config, "enabled", True) is False:
        return ""
    try:
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            return ""
    except (OSError, RuntimeError, TypeError, ValueError):
        return ""

    filenames = _setting(config, "filenames", DEFAULT_FILENAMES)
    if not isinstance(filenames, (list, tuple)):
        filenames = DEFAULT_FILENAMES
    max_files = _bounded_int(_setting(config, "max_files", 8), 8, 0, 32)
    max_file_bytes = _bounded_int(_setting(config, "max_file_bytes", 32768), 32768, 1, 262144)
    max_total_chars = _bounded_int(_setting(config, "max_total_chars", 12000), 12000, 0, 50000)
    if not max_files or not max_total_chars:
        return ""

    sections = []
    total_chars = 0
    seen = set()
    for raw_name in filenames:
        if len(sections) >= max_files or total_chars >= max_total_chars:
            break
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name or name in seen or name in (".", "..") or "/" in name or "\\" in name:
            continue
        seen.add(name)
        candidate = root / name
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve(strict=True)
            if resolved.parent != root or resolved.stat().st_size > max_file_bytes:
                continue
            raw = resolved.read_bytes()
            if len(raw) > max_file_bytes or b"\\x00" in raw:
                continue
            body = raw.decode("utf-8-sig").strip()
        except (OSError, RuntimeError, UnicodeDecodeError, ValueError):
            continue
        if not body:
            continue
        remaining = max_total_chars - total_chars
        section = f"--- project context: {name} ---\\n{body[:remaining].rstrip()}"
        sections.append(section)
        total_chars += len(section)
    return "\\n\\n".join(sections)
