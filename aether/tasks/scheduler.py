import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aether.errors import SchedulerError
from aether.utils import atomic_json_write, atomic_write, make_id, parse_bool, read_json, redact

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
        self.executions_path = Path(home) / "cron" / "executions.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.jobs = self._load()

    def _load(self) -> list[dict]:
        data = read_json(self.path, [])
        return data if isinstance(data, list) else []

    def _save(self) -> None:
        atomic_json_write(self.path, self.jobs)

    @staticmethod
    def _is_recurring(schedule) -> bool:
        return bool(INTERVAL.match(str(schedule or "").strip()))

    def _find(self, job_id: str) -> dict | None:
        for job in self.jobs:
            if str(job.get("id")) == str(job_id):
                return job
        return None

    def _record_execution(self, entry: dict) -> None:
        with self.executions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        try:
            lines = [line for line in self.executions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            return
        if len(lines) > 1000:
            atomic_write(self.executions_path, "\n".join(lines[-1000:]) + "\n")

    def add_job(self, prompt: str, schedule: str, name: str = "") -> dict:
        prompt = str(prompt).strip()
        if not prompt:
            raise SchedulerError("Scheduled job prompt is required")
        with self._lock:
            next_run = parse_schedule(schedule)
            job = {
                "id": f"job_{int(time.time() * 1000)}_{make_id('cron')[4:8]}",
                "name": str(name).strip() or prompt[:48],
                "prompt": prompt,
                "schedule": str(schedule),
                "next_run": next_run.isoformat(),
                "last_run": None,
                "last_status": None,
                "last_result": "",
                "last_error": "",
                "enabled": True,
            }
            self.jobs.append(job)
            self._save()
            return dict(job)

    def update_job(self, job_id: str, prompt=None, schedule=None, name=None) -> dict | None:
        with self._lock:
            job = self._find(job_id)
            if job is None:
                return None
            if prompt is not None:
                text = str(prompt).strip()
                if not text:
                    raise SchedulerError("Scheduled job prompt is required")
                job["prompt"] = text
            if name is not None:
                job["name"] = str(name).strip() or str(job.get("prompt", ""))[:48]
            if schedule is not None:
                job["schedule"] = str(schedule)
                job["next_run"] = parse_schedule(job["schedule"]).isoformat()
                job["enabled"] = True
                job["last_error"] = ""
            self._save()
            return dict(job)

    def set_enabled(self, job_id: str, enabled: bool) -> dict | None:
        with self._lock:
            job = self._find(job_id)
            if job is None:
                return None
            job["enabled"] = bool(enabled)
            self._save()
            return dict(job)

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [dict(job) for job in self.jobs]

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            before = len(self.jobs)
            self.jobs = [job for job in self.jobs if str(job.get("id")) != str(job_id)]
            changed = len(self.jobs) != before
            if changed:
                self._save()
            return changed

    def _due_jobs(self, now: datetime) -> list[dict]:
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

    def due_jobs(self, now: datetime | None = None) -> list[dict]:
        with self._lock:
            return [dict(job) for job in self._due_jobs(now or datetime.now(timezone.utc))]

    def execution_history(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(1000, int(limit)))
        try:
            lines = [line for line in self.executions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            return []
        history = []
        for line in lines[-limit:]:
            try:
                history.append(json.loads(line))
            except ValueError:
                continue
        return history

    def tick(self) -> dict:
        with self._lock:
            due = self._due_jobs(datetime.now(timezone.utc))
            summary = {"due": len(due), "executed": 0, "skipped": 0, "failed": 0, "outcomes": []}
            for job in due:
                outcome = {"job_id": job.get("id", ""), "name": job.get("name", "")}
                if not callable(self.runner):
                    reason = "no runner configured"
                    job["last_status"] = "skipped"
                    job["last_error"] = reason
                    self._save()
                    self._record_execution(
                        {
                            "run_id": "",
                            "job_id": outcome["job_id"],
                            "status": "skipped",
                            "reason": reason,
                            "started_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    summary["skipped"] += 1
                    outcome.update({"status": "skipped", "reason": reason})
                    summary["outcomes"].append(outcome)
                    continue
                try:
                    next_run = parse_schedule(job.get("schedule", "")).isoformat()
                except SchedulerError as exc:
                    reason = str(exc)
                    job["enabled"] = False
                    job["last_status"] = "skipped"
                    job["last_error"] = redact(reason)
                    self._save()
                    self._record_execution(
                        {
                            "run_id": "",
                            "job_id": outcome["job_id"],
                            "status": "skipped",
                            "reason": reason,
                            "started_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    summary["skipped"] += 1
                    outcome.update({"status": "skipped", "reason": reason})
                    summary["outcomes"].append(outcome)
                    continue
                run_id = make_id("sched")
                started_at = datetime.now(timezone.utc).isoformat()
                job["last_run"] = started_at
                job["next_run"] = next_run
                job["last_status"] = "running"
                job["last_error"] = ""
                job["enabled"] = self._is_recurring(job.get("schedule"))
                self._save()
                try:
                    result = str(self.runner(str(job.get("prompt", ""))))
                    status = "executed"
                    summary["executed"] += 1
                    job["last_status"] = status
                    job["last_result"] = result[:4000]
                    outcome["result"] = result[:1000]
                except Exception as exc:
                    status = "failed"
                    summary["failed"] += 1
                    error = redact(f"{type(exc).__name__}: {exc}")
                    job["last_status"] = status
                    job["last_result"] = ""
                    job["last_error"] = error[:1000]
                    outcome["error"] = error[:1000]
                self._save()
                self._record_execution(
                    {
                        "run_id": run_id,
                        "job_id": outcome["job_id"],
                        "status": status,
                        "started_at": started_at,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "result": outcome.get("result", ""),
                        "error": outcome.get("error", ""),
                    }
                )
                outcome["status"] = status
                outcome["run_id"] = run_id
                summary["outcomes"].append(outcome)
            return summary

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

        self._stop.clear()
        self._thread = threading.Thread(target=loop, name="aether-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
