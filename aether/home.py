import os
from pathlib import Path


def _restrict(path: Path) -> None:
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def aether_home() -> Path:
    raw = os.environ.get("AETHER_HOME")
    path = Path(raw).expanduser() if raw else Path.home() / ".aether"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    _restrict(path)
    for name in ("memories", "skills", "logs", "cron"):
        child = path / name
        child.mkdir(parents=True, exist_ok=True, mode=0o700)
        _restrict(child)
    return path


def config_path() -> Path:
    return aether_home() / "config.json"


def env_path() -> Path:
    return aether_home() / ".env"


def state_db_path() -> Path:
    return aether_home() / "state.db"


def workspace_root() -> Path:
    import os

    return Path(os.environ.get("AETHER_WORKSPACE", Path.cwd())).expanduser().resolve()
