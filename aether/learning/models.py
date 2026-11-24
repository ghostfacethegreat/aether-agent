from dataclasses import asdict, dataclass, field

from aether.utils import make_id, utc_now


@dataclass
class Experience:
    id: str = field(default_factory=lambda: make_id("exp"))
    session_id: str = ""
    objective: str = ""
    classification: dict = field(default_factory=dict)
    plan_id: str = ""
    plan: dict = field(default_factory=dict)
    agents: list = field(default_factory=list)
    models: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    solution: str = ""
    verification: dict = field(default_factory=dict)
    feedback: dict = field(default_factory=dict)
    outcome: str = ""
    status: str = ""
    provenance: str = "agent-turn"
    confidence: float = 0.5
    verified: bool = False
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Experience":
        data = data if isinstance(data, dict) else {}
        return cls(
            id=str(data.get("id") or make_id("exp")),
            session_id=str(data.get("session_id") or ""),
            objective=str(data.get("objective") or ""),
            classification=data.get("classification") if isinstance(data.get("classification"), dict) else {},
            plan_id=str(data.get("plan_id") or ""),
            plan=data.get("plan") if isinstance(data.get("plan"), dict) else {},
            agents=list(data.get("agents") or []),
            models=list(data.get("models") or []),
            tools=list(data.get("tools") or []),
            errors=list(data.get("errors") or []),
            solution=str(data.get("solution") or ""),
            verification=data.get("verification") if isinstance(data.get("verification"), dict) else {},
            feedback=data.get("feedback") if isinstance(data.get("feedback"), dict) else {},
            outcome=str(data.get("outcome") or ""),
            status=str(data.get("status") or ""),
            provenance=str(data.get("provenance") or "agent-turn"),
            confidence=float(data.get("confidence", 0.5)),
            verified=bool(data.get("verified")),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass
class SkillProposal:
    id: str = field(default_factory=lambda: make_id("proposal"))
    skill_name: str = ""
    kind: str = "create"
    status: str = "proposed"
    content: str = ""
    meta: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    decided_at: str = ""
    decided_by: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillProposal":
        data = data if isinstance(data, dict) else {}
        return cls(
            id=str(data.get("id") or make_id("proposal")),
            skill_name=str(data.get("skill_name") or ""),
            kind=str(data.get("kind") or "create"),
            status=str(data.get("status") or "proposed"),
            content=str(data.get("content") or ""),
            meta=data.get("meta") if isinstance(data.get("meta"), dict) else {},
            evidence=list(data.get("evidence") or []),
            validation=data.get("validation") if isinstance(data.get("validation"), dict) else {},
            created_at=str(data.get("created_at") or utc_now()),
            decided_at=str(data.get("decided_at") or ""),
            decided_by=str(data.get("decided_by") or ""),
        )


@dataclass
class SkillVersion:
    id: str = field(default_factory=lambda: make_id("version"))
    skill_name: str = ""
    version: int = 1
    content: str = ""
    status: str = "candidate"
    proposal_id: str = ""
    score: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillVersion":
        data = data if isinstance(data, dict) else {}
        return cls(
            id=str(data.get("id") or make_id("version")),
            skill_name=str(data.get("skill_name") or ""),
            version=max(1, int(data.get("version") or 1)),
            content=str(data.get("content") or ""),
            status=str(data.get("status") or "candidate"),
            proposal_id=str(data.get("proposal_id") or ""),
            score=float(data.get("score") or 0.0),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass
class SkillMetrics:
    skill_name: str = ""
    active_version: int = 0
    execution_count: int = 0
    success_count: int = 0
    verification_count: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    last_success_at: str = ""
    last_modified_at: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["success_rate"] = self.success_rate()
        data["failure_rate"] = self.failure_rate()
        data["verification_rate"] = self.verification_rate()
        data["average_execution_time_ms"] = self.average_execution_time()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SkillMetrics":
        data = data if isinstance(data, dict) else {}
        return cls(
            skill_name=str(data.get("skill_name") or ""),
            active_version=max(0, int(data.get("active_version") or 0)),
            execution_count=max(0, int(data.get("execution_count") or 0)),
            success_count=max(0, int(data.get("success_count") or 0)),
            verification_count=max(0, int(data.get("verification_count") or 0)),
            total_duration_ms=max(0.0, float(data.get("total_duration_ms") or 0.0)),
            total_tokens=max(0, int(data.get("total_tokens") or 0)),
            estimated_cost=max(0.0, float(data.get("estimated_cost") or 0.0)),
            last_success_at=str(data.get("last_success_at") or ""),
            last_modified_at=str(data.get("last_modified_at") or ""),
        )

    def success_rate(self) -> float:
        return round(self.success_count / self.execution_count, 4) if self.execution_count else 0.0

    def failure_rate(self) -> float:
        return round(1.0 - self.success_rate(), 4) if self.execution_count else 0.0

    def verification_rate(self) -> float:
        return round(self.verification_count / self.execution_count, 4) if self.execution_count else 0.0

    def average_execution_time(self) -> float:
        return round(self.total_duration_ms / self.execution_count, 2) if self.execution_count else 0.0
