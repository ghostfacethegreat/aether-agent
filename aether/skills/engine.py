import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from aether.errors import SkillError
from aether.utils import atomic_json_write, atomic_write

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")
INJECTION = ("ignore previous", "ignore all previous", "system prompt:", "exfiltrate", "curl http")


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str = ""
    meta: dict = field(default_factory=dict)

    def summary(self) -> str:
        return f"- {self.name}: {self.description}"


def parse_skill_text(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        raise SkillError("SKILL.md must start with YAML-like frontmatter delimited by ---")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            value = [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]
        meta[key] = value
    return meta, match.group(2).strip()


class SkillEngine:
    def __init__(self, home: Path | str, builtin_dir: Path | None = None, enabled=True):
        self.home = Path(home)
        self.user_dir = self.home / "skills"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.builtin_dir = Path(builtin_dir) if builtin_dir else Path(__file__).parent / "builtin"
        self.usage_file = self.user_dir / ".usage.json"
        self.enabled = enabled

    def _roots(self) -> list[Path]:
        roots = []
        if self.builtin_dir.exists():
            roots.append(self.builtin_dir)
        roots.append(self.user_dir)
        return roots

    def discover(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        for root in self._roots():
            for path in sorted(root.rglob("SKILL.md")):
                try:
                    meta, body = parse_skill_text(path.read_text(encoding="utf-8"))
                except (OSError, SkillError):
                    continue
                name = str(meta.get("name") or path.parent.name)
                if not VALID_NAME.match(name):
                    continue
                if any(pattern in body.lower() for pattern in INJECTION):
                    continue
                skills[name] = Skill(name, str(meta.get("description") or ""), path, body, meta)
        return skills

    def list_skills(self) -> list[dict]:
        result = []
        usage = self._usage()
        for skill in self.discover().values():
            result.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "source": "user" if self.user_dir in skill.path.parents else "builtin",
                    "views": int(usage.get(skill.name, {}).get("views", 0)),
                }
            )
        return sorted(result, key=lambda item: item["name"])

    def view(self, name: str) -> Skill:
        skill = self.discover().get(name)
        if not skill:
            raise SkillError(f"Skill '{name}' not found")
        self.record(name, "views")
        return skill

    def context(self, max_chars=3000) -> str:
        if not self.enabled:
            return ""
        lines = ["Available skills (use the 'skill' tool with action=view to load one):"]
        for item in self.list_skills():
            lines.append(item["name"] + ": " + (item["description"] or "No description"))
        text = "\n".join(lines)
        return "<skills>\n" + text[:max_chars] + "\n</skills>"

    @staticmethod
    def _validate(name: str, description: str, body: str) -> None:
        if not VALID_NAME.match(name or ""):
            raise SkillError("Skill name must be lowercase letters, numbers, and hyphens (2-49 chars)")
        if not description.strip():
            raise SkillError("Skill description is required")
        if not body.strip():
            raise SkillError("Skill body is required")
        combined = (description + "\n" + body).lower()
        if any(pattern in combined for pattern in INJECTION):
            raise SkillError("Skill contains a blocked instruction pattern")

    def create(self, name: str, description: str, body: str) -> Path:
        self._validate(name, description, body)
        target_dir = self.user_dir / name
        if target_dir.exists():
            raise SkillError(f"Skill '{name}' already exists")
        target_dir.mkdir(parents=True)
        content = (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "version: 1.0\n"
            "---\n\n"
            f"{body.strip()}\n"
        )
        atomic_write(target_dir / "SKILL.md", content)
        return target_dir / "SKILL.md"

    def install(self, name: str, content: str, overwrite: bool = False) -> Path:
        meta, body = parse_skill_text(content)
        skill_name = str(meta.get("name") or name)
        description = str(meta.get("description") or "")
        self._validate(skill_name, description, body)
        target_dir = (self.user_dir / name).resolve()
        root = self.user_dir.resolve()
        if root != target_dir.parent:
            raise SkillError("Skill path must be directly inside the user skills directory")
        exists = (target_dir / "SKILL.md").exists()
        if exists and not overwrite:
            raise SkillError(f"Skill '{name}' already exists")
        target_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(target_dir / "SKILL.md", content.strip() + "\n")
        if exists:
            self.record(name, "edits")
        return target_dir / "SKILL.md"

    def edit(self, name: str, body: str, description: str | None = None) -> Path:
        skill = self.view(name)
        if self.user_dir not in skill.path.parents:
            raise SkillError("Built-in skills are read-only; create a user skill instead")
        self._validate(name, description or skill.description, body)
        if description:
            meta, _ = parse_skill_text(skill.path.read_text(encoding="utf-8"))
            meta["description"] = description
            header = "\n".join(f"{key}: {value}" for key, value in meta.items())
            content = f"---\n{header}\n---\n\n{body.strip()}\n"
        else:
            content = f"---\nname: {name}\ndescription: {skill.description}\nversion: 1.0\n---\n\n{body.strip()}\n"
        atomic_write(skill.path, content)
        self.record(name, "edits")
        return skill.path

    def _usage(self) -> dict:
        try:
            data = json.loads(self.usage_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def record(self, name: str, field_name: str) -> None:
        usage = self._usage()
        entry = usage.setdefault(name, {})
        entry[field_name] = int(entry.get(field_name, 0)) + 1
        atomic_json_write(self.usage_file, usage)
