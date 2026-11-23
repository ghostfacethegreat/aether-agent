import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aether.errors import SchedulerError
from aether.utils import atomic_json_write, parse_bool, read_json

INTERVAL = re.compile(r"^(?:every\s+)?(\d+)\s*(s|m|h|d)$", re.I)


def parse_schedule(value: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    text = str(value or "").strip()
    match = INTERVAL.match(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        return now + timedelta(seconds=amount * seconds)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchedulerError(f"Invalid schedule '{value}'. Use 'every 30m', '1h', or an ISO timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class Scheduler:
    def __init__(self, config, home: Path | str, runner=None):
        self.config = config
        self.path = Path(home) / "cron" / "jobs.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self._thread = None
        self._stop = threading.Event()
        self.jobs = self._load()

    def _load(self) -> list[dict]:
        data = read_json(self.path, [])
        return data if isinstance(data, list) else []

    def _save(self) -> None:
        atomic_json_write(self.path, self.jobs)

    def add_job(self, prompt: str, schedule: str, name: str = "") -> dict:
        if not str(prompt).strip():
            raise SchedulerError("Scheduled job prompt is required")
        next_run = parse_schedule(schedule)
        job = {
            "id": f"job_{int(time.time() * 1000)}",
            "name": name or str(prompt)[:48],
            "prompt": prompt,
            "schedule": schedule,
            "next_run": next_run.isoformat(),
            "last_run": None,
            "enabled": True,
        }
        self.jobs.append(job)
        self._save()
        return job

    def list_jobs(self) -> list[dict]:
        return list(self.jobs)

    def remove_job(self, job_id: str) -> bool:
        before = len(self.jobs)
        self.jobs = [job for job in self.jobs if str(job.get("id")) != str(job_id)]
        if len(self.jobs) != before:
            self._save()
        return len(self.jobs) != before

    def due_jobs(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        due = []
        for job in self.jobs:
            if not job.get("enabled", True):
                continue
            try:
                when = datetime.fromisoformat(str(job.get("next_run") or ""))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when <= now:
                due.append(job)
        return due

    def tick(self) -> list[dict]:
        executed = []
        for job in self.due_jobs():
            try:
                if self.runner:
                    job["last_result"] = str(self.runner(job.get("prompt", "")))[:4000]
            except Exception as exc:
                job["last_result"] = f"Scheduler runner failed: {type(exc).__name__}: {exc}"
            job["last_run"] = datetime.now(timezone.utc).isoformat()
            try:
                job["next_run"] = parse_schedule(job["schedule"]).isoformat()
            except SchedulerError:
                job["enabled"] = False
            executed.append(job)
        if executed:
            self._save()
        return executed

    def start(self) -> None:
        if not parse_bool(self.config.get("scheduler.enabled"), False) or self._thread:
            return
        interval = max(5, int(self.config.get("scheduler.tick_seconds", 30)))

        def loop():
            while not self._stop.wait(interval):
                try:
                    self.tick()
                except Exception:
                    continue

        self._thread = threading.Thread(target=loop, name="aether-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
