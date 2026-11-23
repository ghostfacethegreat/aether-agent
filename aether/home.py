from pathlib import Path


def aether_home() -> Path:
    import os

    raw = os.environ.get("AETHER_HOME")
    path = Path(raw).expanduser() if raw else Path.home() / ".aether"
    path.mkdir(parents=True, exist_ok=True)
    for name in ("memories", "skills", "logs", "cron"):
        (path / name).mkdir(parents=True, exist_ok=True)
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
