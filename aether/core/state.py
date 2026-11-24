from dataclasses import dataclass, field

from aether.utils import make_id, utc_now

from .planning import ExecutionPlan


@dataclass
class ExecutionCheckpoint:
    id: str
    plan_id: str
    sequence: int
    phase: str
    note: str
    payload: dict
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "sequence": int(self.sequence),
            "phase": self.phase,
            "note": self.note,
            "payload": self.payload,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionCheckpoint":
        payload = data.get("payload")
        return cls(
            id=str(data.get("id") or make_id("checkpoint")),
            plan_id=str(data.get("plan_id") or ""),
            sequence=int(data.get("sequence") or 0),
            phase=str(data.get("phase") or ""),
            note=str(data.get("note") or ""),
            payload=dict(payload) if isinstance(payload, dict) else {},
            created_at=str(data.get("created_at") or utc_now()),
        )


def make_checkpoint(plan: ExecutionPlan, note: str = "", sequence: int = 0) -> ExecutionCheckpoint:
    return ExecutionCheckpoint(
        id=make_id("checkpoint"),
        plan_id=plan.id,
        sequence=int(sequence),
        phase=plan.phase,
        note=str(note or ""),
        payload=plan.to_dict(),
    )


def restore_plan(checkpoint: ExecutionCheckpoint) -> ExecutionPlan:
    return ExecutionPlan.from_dict(checkpoint.payload)
