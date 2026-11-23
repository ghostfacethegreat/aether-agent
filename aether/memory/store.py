import re
from pathlib import Path

from aether.utils import atomic_write, truncate

SECTION = re.compile(r"^## (.+)$")
SEPARATOR = "\n§\n"


class MemoryStore:
    def __init__(self, home: Path | str, char_limit=4000):
        self.home = Path(home)
        self.dir = self.home / "memories"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.dir / "MEMORY.md"
        self.user_file = self.dir / "USER.md"
        self.char_limit = int(char_limit)
        for path, title in ((self.memory_file, "Aether Memory"), (self.user_file, "User Profile")):
            if not path.exists():
                atomic_write(path, f"# {title}\n\n")

    def _read(self, user=False) -> dict[str, list[str]]:
        path = self.user_file if user else self.memory_file
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return {}
        sections: dict[str, list[str]] = {}
        current = "general"
        buffer: list[str] = []

        def flush():
            chunk = "\n".join(buffer).strip()
            buffer.clear()
            if chunk:
                sections.setdefault(current, []).append(chunk)

        for line in text.splitlines():
            match = SECTION.match(line.strip())
            if match:
                flush()
                current = match.group(1).strip() or "general"
            elif line.strip() == "§":
                flush()
            elif not line.startswith("# "):
                buffer.append(line)
        flush()
        return sections

    def _write(self, sections: dict[str, list[str]], user=False) -> None:
        path = self.user_file if user else self.memory_file
        title = "User Profile" if user else "Aether Memory"
        parts = [f"# {title}\n"]
        for section, entries in sections.items():
            parts.append(f"## {section}\n")
            parts.append((SEPARATOR + "\n").join(entries) + "\n")
        atomic_write(path, "\n".join(parts))

    def add(self, text, category="general", user=False) -> None:
        text = str(text).strip()
        if not text:
            return
        sections = self._read(user)
        entries = sections.setdefault(category, [])
        if text not in entries:
            entries.append(text)
        self._write(sections, user)

    def list(self, user=False) -> list[tuple[str, str]]:
        sections = self._read(user)
        return [(section, entry) for section, entries in sections.items() for entry in entries]

    def search(self, query, user=False) -> list[tuple[str, str]]:
        needle = str(query).lower()
        return [(section, entry) for section, entry in self.list(user) if needle in entry.lower() or needle in section.lower()]

    def delete(self, category: str, index: int, user=False) -> bool:
        sections = self._read(user)
        entries = sections.get(category) or []
        if index < 0 or index >= len(entries):
            return False
        entries.pop(index)
        if not entries:
            sections.pop(category, None)
        self._write(sections, user)
        return True

    def replace(self, category: str, index: int, text: str, user=False) -> bool:
        sections = self._read(user)
        entries = sections.get(category) or []
        if index < 0 or index >= len(entries):
            return False
        entries[index] = str(text).strip()
        self._write(sections, user)
        return True

    def clear(self, user=False) -> None:
        self._write({}, user)

    def export(self) -> dict:
        return {
            "version": 1,
            "memory": self._read(False),
            "user": self._read(True),
        }

    def import_data(self, data: dict, merge=True) -> None:
        if not isinstance(data, dict):
            raise ValueError("Memory import must be a JSON object")
        for key, user in (("memory", False), ("user", True)):
            incoming = data.get(key) or {}
            if not isinstance(incoming, dict):
                continue
            sections = self._read(user) if merge else {}
            for section, entries in incoming.items():
                current = sections.setdefault(section, [])
                for entry in entries if isinstance(entries, list) else [str(entries)]:
                    if entry not in current:
                        current.append(str(entry))
            self._write(sections, user)

    def context(self, include_user=True) -> str:
        sections = self._read(False)
        if include_user:
            for key, value in self._read(True).items():
                sections.setdefault(f"user:{key}", []).extend(value)
        lines = []
        used = 0
        for section, entries in sections.items():
            for entry in entries:
                line = f"- [{section}] {entry}"
                if used + len(line) > self.char_limit:
                    break
                lines.append(line)
                used += len(line) + 1
        if not lines:
            return ""
        return "<memory>\n" + truncate("\n".join(lines), self.char_limit) + "\n</memory>"
