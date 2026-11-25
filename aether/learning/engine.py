import hashlib
import json
import re
from collections import defaultdict

from aether.errors import LearningError, SkillError
from aether.learning.models import Experience, SkillMetrics, SkillProposal, SkillVersion
from aether.skills import parse_skill_text
from aether.skills.engine import Skill, VALID_NAME
from aether.utils import make_id, redact, truncate, utc_now

STOPWORDS = {
    "about", "after", "again", "also", "check", "could", "from", "have", "into", "make", "need",
    "with", "that", "this", "then", "they", "using", "verify", "want", "were", "what", "when",
    "which", "will", "with", "work", "would", "your",
}
VERIFICATION_SOURCES = {"tests", "check", "deterministic", "verification", "user"}
VALID_PERMISSIONS = {"read", "write", "execute", "network"}
TOOL_PERMISSIONS = {
    "browser": "network",
    "delegate_task": "execute",
    "edit_file": "write",
    "git": "execute",
    "list_directory": "read",
    "memory": "write",
    "plan_tool": "write",
    "python": "execute",
    "read_file": "read",
    "session_search": "read",
    "skill": "write",
    "terminal": "execute",
    "todo": "write",
    "web_fetch": "network",
    "web_search": "network",
    "write_file": "write",
}
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile("s" + r"k-[A-Za-z0-9_-]{20,}"),
    re.compile("AI" + r"za[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?i)\b(?:password|secret|api[_-]?key|token)\s*[:=]\s*\S{8,}"),
)
INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions"),
    re.compile(r"(?i)(reveal|print|show)\s+(the\s+)?(system|developer)\s+prompt"),
    re.compile(r"(?i)bypass\s+(approval|permission|safety|policy)"),
    re.compile(r"(?i)self[-\s]?grant"),
    re.compile(r"(?i)exfiltrat"),
    re.compile(r"(?i)do\s+not\s+tell\s+(the\s+)?user"),
)


class LearningEngine:
    def __init__(self, store, skills, layered_memory=None, config=None, known_tools=None):
        self.store = store
        self.skills = skills
        self.layered_memory = layered_memory
        self.config = config
        self.known_tools = set(str(item) for item in (known_tools or []))

    def _setting(self, key: str, default):
        if self.config is None:
            return default
        value = self.config.get(f"learning.{key}", default)
        return default if value is None else value

    @staticmethod
    def _clean(value, limit: int = 2000) -> str:
        text = redact(str(value or ""))
        text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
        return truncate(text.strip(), limit)

    @classmethod
    def _clean_value(cls, value, depth: int = 0):
        if depth > 4:
            return "[truncated]"
        if isinstance(value, dict):
            return {cls._clean(key, 100): cls._clean_value(item, depth + 1) for key, item in list(value.items())[:50]}
        if isinstance(value, (list, tuple)):
            return [cls._clean_value(item, depth + 1) for item in list(value)[:50]]
        if isinstance(value, bool) or isinstance(value, (int, float)):
            return value
        return cls._clean(value, 1000)

    @classmethod
    def _clean_list(cls, values, limit: int = 2000) -> list:
        return [cls._clean(item, limit) for item in (values or [])][:50]

    def _keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", str(text or "").lower())
        unique = []
        for word in words:
            if len(word) < 4 or word in STOPWORDS or word in unique:
                continue
            unique.append(word)
        return unique

    @staticmethod
    def _format_meta_value(value) -> str:
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(str(item) for item in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        return redact(str(value)).replace("\n", " ").strip()[:600]

    def _parse_content(self, content: str) -> tuple[dict, str]:
        try:
            return parse_skill_text(content)
        except SkillError as exc:
            raise LearningError(str(exc)) from exc

    def _set_meta(self, content: str, updates: dict) -> str:
        meta, body = self._parse_content(content)
        meta.update(updates)
        header = "\n".join(f"{key}: {self._format_meta_value(value)}" for key, value in meta.items())
        return f"---\n{header}\n---\n\n{body.strip()}\n"

    def _event(self, skill_name: str, event_type: str, payload: dict) -> dict:
        item = {
            "id": make_id("learn-event"),
            "skill_name": skill_name,
            "event_type": event_type,
            "payload": self._clean_value(payload),
            "created_at": utc_now(),
        }
        self.store.record_learning_event(item)
        return item

    def _verify_flags(self, verification: dict, feedback: dict, status: str) -> tuple[bool, dict]:
        sources = set(str(item) for item in (verification.get("sources") or []))
        explicit = str(verification.get("status") or "").lower() in {"verified", "passed", "success"}
        evidence = bool(sources & VERIFICATION_SOURCES)
        user_verified = str(feedback.get("source") or "") == "user" and str(feedback.get("verdict") or "") == "verified"
        verified = bool((explicit and evidence) or user_verified)
        normalized = {
            "status": "verified" if verified else "unverified",
            "sources": sorted(sources),
            "model_claim": str(verification.get("model_claim") or status or "")[:200],
        }
        return verified, normalized

    def record_experience(
        self,
        objective: str,
        *,
        plan=None,
        classification=None,
        agents=None,
        models=None,
        tools=None,
        errors=None,
        solution="",
        verification=None,
        feedback=None,
        outcome="",
        status="",
        provenance="agent-turn",
        session_id="",
        confidence=None,
        plan_id="",
    ) -> dict:
        if not bool(self._setting("enabled", True)):
            return {}
        plan = plan if isinstance(plan, dict) else {}
        plan_id = str(plan_id or plan.get("id") or "")
        verification = verification if isinstance(verification, dict) else {}
        feedback = feedback if isinstance(feedback, dict) else {}
        verified, verification = self._verify_flags(
            self._clean_value(verification),
            self._clean_value(feedback),
            status or outcome,
        )
        clean_tools = []
        for item in (tools or []):
            if not isinstance(item, dict):
                continue
            record = {
                "name": self._clean(item.get("name"), 120),
                "ok": bool(item.get("ok")),
                "duration": float(item.get("duration") or 0.0),
            }
            if item.get("error"):
                record["error"] = self._clean(item.get("error"), 500)
            clean_tools.append(record)
        payload = {
            "objective": self._clean(objective, 4000),
            "classification": self._clean_value(classification or {}),
            "plan_id": self._clean(plan_id, 120),
            "plan": self._clean_value(plan or {}),
            "agents": self._clean_list(agents),
            "models": self._clean_list(models),
            "tools": clean_tools,
            "errors": self._clean_list(errors, 1000),
            "solution": self._clean(solution, 4000),
            "verification": verification,
            "feedback": self._clean_value(feedback),
            "outcome": self._clean(outcome, 500),
            "status": self._clean(status or outcome, 200),
            "provenance": self._clean(provenance, 200) or "agent-turn",
            "confidence": float(confidence) if confidence is not None else (0.85 if verified else 0.5),
            "verified": verified,
            "session_id": self._clean(session_id, 120),
        }
        experience = Experience.from_dict(payload)
        experience.verified = verified
        self.store.save_experience(experience.to_dict())
        if self.layered_memory is not None:
            content = "\n".join(
                [
                    f"Objective: {experience.objective}",
                    f"Outcome: {experience.outcome or experience.status}",
                    f"Verified: {'yes' if verified else 'no'}",
                    f"Tools: {', '.join(item['name'] for item in clean_tools if item['name'])}",
                ]
            )
            self.layered_memory.remember(
                "episodic",
                content,
                subject=f"experience:{experience.id}",
                provenance=f"learning:{experience.provenance}",
                confidence=experience.confidence,
                session_id=experience.session_id,
                metadata={"experience_id": experience.id, "verified": verified},
                verified=verified,
            )
        self._event("", "experience_recorded", {"experience_id": experience.id, "verified": verified})
        return experience.to_dict()

    def record_feedback(self, text: str, verdict: str, experience_id: str = "", session_id: str = "") -> dict:
        verdict = str(verdict or "").strip().lower()
        if verdict not in {"verified", "failed", "neutral"}:
            raise LearningError("Feedback verdict must be verified, failed, or neutral")
        message = self._clean(text, 2000)
        row = self.store.get_experience(experience_id) if experience_id else None
        if row is None:
            rows = self.store.list_experiences(session_id=session_id or None, limit=1)
            row = rows[0] if rows else None
        if row is None:
            if self.layered_memory is not None:
                self.layered_memory.remember(
                    "user",
                    f"Feedback: {message}",
                    subject="feedback:latest",
                    provenance="user-feedback",
                    confidence=0.9,
                    session_id=session_id,
                )
            return {"stored": "user-memory", "verdict": verdict}
        experience = Experience.from_dict(row)
        experience.feedback = {"source": "user", "verdict": verdict, "text": message, "at": utc_now()}
        verification = dict(experience.verification or {})
        verification["sources"] = sorted(set(verification.get("sources") or []) | {"user"})
        if verdict == "verified":
            experience.verified = True
            experience.confidence = max(experience.confidence, 0.9)
            verification["status"] = "verified"
        elif verdict == "failed":
            experience.verified = False
            verification["status"] = "failed"
        else:
            verification["status"] = "neutral"
        experience.verification = verification
        self.store.save_experience(experience.to_dict())
        if hasattr(self.store, "mark_model_performance_verified"):
            self.store.mark_model_performance_verified(experience.id, verdict)
        self._event("", "user_feedback", {"experience_id": experience.id, "verdict": verdict})
        return experience.to_dict()

    def _skill_name(self, experiences: list[Experience], tools: list[str]) -> str:
        words = []
        for experience in experiences:
            for word in self._keywords(experience.objective):
                if word not in words:
                    words.append(word)
        parts = []
        for word in words[:2]:
            parts.append(word)
        for tool in tools[:2]:
            clean = re.sub(r"[^a-z0-9]+", "-", tool.lower()).strip("-")
            if clean and clean not in parts:
                parts.append(clean)
        if len(parts) < 2:
            parts.append("procedure")
        name = "-".join(parts).lower()
        name = re.sub(r"[^a-z0-9-]", "", name)[:49].strip("-")
        return name if len(name) >= 2 else "reusable-procedure"

    def _permissions_for_tools(self, tools: list[str]) -> list[str]:
        values = []
        for tool in tools:
            permission = TOOL_PERMISSIONS.get(tool, "execute")
            if permission not in values:
                values.append(permission)
        return values or ["read"]

    def _render_skill(self, meta: dict, body: str) -> str:
        header = "\n".join(f"{key}: {self._format_meta_value(value)}" for key, value in meta.items())
        return f"---\n{header}\n---\n\n{body.strip()}\n"

    def _proposal_from_experiences(self, experiences: list[Experience], fingerprint: str) -> SkillProposal:
        tools = []
        for experience in experiences:
            for item in experience.tools:
                name = str(item.get("name") or "")
                if name and name not in tools:
                    tools.append(name)
        evidence = [experience.id for experience in experiences]
        sources = sorted({source for experience in experiences for source in (experience.verification.get("sources") or [])})
        name = self._skill_name(experiences, tools)
        description = self._clean(
            "Reusable procedure discovered from " + str(len(evidence)) + " verified execution(s): " + experiences[0].objective,
            300,
        )
        steps = [
            "1. Confirm the task matches the purpose and preconditions.",
            "2. Use only the listed tools and follow the order observed in the supporting verified experience.",
            "3. Record the observed result and verify it before claiming completion.",
        ]
        meta = {
            "name": name,
            "description": description,
            "version": "1.0",
            "purpose": self._clean(experiences[0].objective, 400),
            "preconditions": "A matching task has the required tools and permissions available.",
            "required_tools": tools,
            "required_permissions": self._permissions_for_tools(tools),
            "verification": "Replay examples from verified experience: " + (", ".join(sources) or "recorded deterministic evidence"),
            "examples": evidence,
            "evidence": evidence,
            "fingerprint": fingerprint,
            "target_version": 1,
            "sources": sources,
        }
        body = "\n".join(
            [
                f"# {name}",
                "",
                "## Purpose",
                meta["purpose"],
                "",
                "## Preconditions",
                meta["preconditions"],
                "",
                "## Procedure",
                *steps,
                "",
                "## Verification",
                meta["verification"],
            ]
        )
        return SkillProposal(
            skill_name=name,
            kind="create",
            status="proposed",
            content=self._render_skill(meta, body),
            meta=meta,
            evidence=evidence,
        )

    def discover(self, limit: int | None = None, query: str = "") -> list[dict]:
        if not bool(self._setting("enabled", True)):
            return []
        count = int(limit if limit is not None else 10)
        min_experiences = max(2, int(self._setting("min_experiences", 2)))
        min_confidence = float(self._setting("min_confidence", 0.7))
        retention = int(self._setting("experience_retention", 500))
        rows = self.store.list_experiences(verified_only=True, limit=retention)
        query_text = self._clean(query, 500).lower()
        groups = defaultdict(list)
        for row in rows:
            experience = Experience.from_dict(row)
            if query_text and query_text not in f"{experience.objective} {experience.solution}".lower():
                continue
            tools = tuple(sorted({str(item.get("name") or "") for item in experience.tools if item.get("name") and item.get("ok")}))
            if not tools:
                continue
            keywords = tuple(self._keywords(experience.objective)[:3])
            groups[(tools, keywords)].append(experience)
        existing_rows = self.store.list_learning_proposals(limit=None) or []
        existing_names = {item["name"] for item in self.skills.list_skills()}
        fingerprints = {str((row.get("meta") or {}).get("fingerprint") or "") for row in existing_rows}
        created = []
        for signature, items in sorted(groups.items(), key=lambda entry: entry[0][0]):
            if len(items) < min_experiences:
                continue
            confidence = min(item.confidence for item in items)
            if confidence < min_confidence:
                continue
            key = json.dumps({"tools": list(signature[0]), "keywords": list(signature[1])}, sort_keys=True)
            fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            if fingerprint in fingerprints:
                self._event("", "duplicate_procedure", {"fingerprint": fingerprint})
                continue
            proposal = self._proposal_from_experiences(items, fingerprint)
            if proposal.skill_name in existing_names:
                self._event(proposal.skill_name, "duplicate_procedure", {"fingerprint": fingerprint})
                continue
            self.store.save_learning_proposal(proposal.to_dict())
            if self.layered_memory is not None:
                self.layered_memory.set_working(
                    f"active_improvement:{proposal.skill_name}",
                    f"Review proposed skill {proposal.skill_name} from {len(items)} verified experiences.",
                    provenance="learning:discovery",
                    confidence=confidence,
                )
            self._event(proposal.skill_name, "skill_proposed", {"proposal_id": proposal.id, "fingerprint": fingerprint})
            created.append(proposal.to_dict())
            fingerprints.add(fingerprint)
            if len(created) >= count:
                break
        return created

    def proposals(self, status: str | None = None, skill_name: str | None = None, limit: int | None = 50) -> list[dict]:
        return self.store.list_learning_proposals(skill_name=skill_name, status=status, limit=limit)

    def _find_proposal(self, target: str) -> dict:
        row = self.store.get_learning_proposal(target)
        if row is not None:
            return row
        rows = self.store.list_learning_proposals(skill_name=target, limit=1)
        if rows:
            return rows[0]
        raise LearningError(f"Learning proposal or skill '{target}' not found")

    def _content_for(self, target: str) -> tuple[str, dict]:
        proposal_row = self.store.get_learning_proposal(target)
        if proposal_row is not None:
            meta, _ = self._parse_content(proposal_row["content"])
            return proposal_row["content"], meta
        version = self.store.latest_skill_version(target)
        if version:
            meta, _ = self._parse_content(version["content"])
            return version["content"], meta
        skill = self.skills.discover().get(target)
        if skill is None:
            raise LearningError(f"Skill '{target}' not found")
        content = skill.path.read_text(encoding="utf-8")
        meta, _ = self._parse_content(content)
        return content, meta

    def test_skill(self, target: str, content: str | None = None, examples=None, known_tools=None) -> dict:
        source = content if content is not None else self._content_for(target)[0]
        meta, _ = self._parse_content(source)
        raw_examples = examples if examples is not None else meta.get("examples")
        if isinstance(raw_examples, str):
            raw_examples = [item.strip() for item in raw_examples.strip("[]").split(",") if item.strip()]
        if not isinstance(raw_examples, list) or not raw_examples:
            return {"passed": False, "score": 0.0, "cases": [], "reason": "no deterministic examples"}
        tools = meta.get("required_tools") or []
        if not isinstance(tools, list):
            tools = []
        known = set(known_tools if known_tools is not None else self.known_tools)
        cases = []
        for example in raw_examples:
            experience_id = str(example.get("id") if isinstance(example, dict) else example)
            row = self.store.get_experience(experience_id)
            if row is None:
                cases.append({"experience_id": experience_id, "passed": False, "reason": "experience not found"})
                continue
            experience = Experience.from_dict(row)
            actual = sorted({str(item.get("name") or "") for item in experience.tools if item.get("ok") and item.get("name")})
            expected = list(example.get("expected_tools") or []) if isinstance(example, dict) else list(tools)
            missing = [tool for tool in expected if tool not in actual]
            passed = bool(experience.verified and actual and not missing)
            if known and any(tool not in known for tool in expected):
                passed = False
                missing.append("unknown tool")
            cases.append(
                {
                    "experience_id": experience_id,
                    "expected_tools": expected,
                    "actual_tools": actual,
                    "missing": missing,
                    "passed": passed,
                }
            )
        passed_count = sum(1 for case in cases if case["passed"])
        return {
            "passed": bool(cases) and passed_count == len(cases),
            "score": round(passed_count / len(cases), 4) if cases else 0.0,
            "cases": cases,
        }

    def validate_proposal(self, proposal_id: str, known_tools=None) -> dict:
        proposal = SkillProposal.from_dict(self._find_proposal(proposal_id))
        meta, body = self._parse_content(proposal.content)
        name = str(meta.get("name") or proposal.skill_name)
        description = str(meta.get("description") or "")
        required_tools = meta.get("required_tools") or []
        required_permissions = meta.get("required_permissions") or []
        tools = [str(item) for item in required_tools] if isinstance(required_tools, list) else []
        permissions = [str(item) for item in required_permissions] if isinstance(required_permissions, list) else []
        known = set(known_tools if known_tools is not None else self.known_tools)
        checks = {
            "structure": bool(
                VALID_NAME.match(name)
                and description.strip()
                and body.strip()
                and all(meta.get(key) for key in ("purpose", "preconditions", "verification", "examples", "evidence"))
            ),
            "tools": bool(tools) and (not known or all(tool in known for tool in tools)),
            "permissions": bool(permissions) and all(item in VALID_PERMISSIONS for item in permissions),
            "secret_free": not any(pattern.search(proposal.content) for pattern in SECRET_PATTERNS),
            "injection_free": not any(pattern.search(proposal.content) for pattern in INJECTION_PATTERNS),
        }
        tests = self.test_skill(proposal.id, proposal.content, meta.get("examples"), known_tools)
        checks["examples"] = tests["passed"]
        details = {"example_tests": tests}
        if proposal.kind == "improve":
            previous = {"passed": False, "score": 0.0, "cases": []}
            try:
                previous = self.test_skill(proposal.skill_name, examples=meta.get("examples"), known_tools=known_tools)
            except LearningError:
                pass
            checks["regression"] = tests["score"] >= previous["score"] and tests["score"] > 0
            details["regression"] = {
                "candidate_score": tests["score"],
                "previous_score": previous["score"],
                "improved_or_equal": tests["score"] >= previous["score"],
            }
        passed = all(bool(value) for value in checks.values())
        proposal.validation = {"passed": passed, "checks": checks, "details": details}
        proposal.status = "validated" if passed else "rejected"
        self.store.save_learning_proposal(proposal.to_dict())
        self._event(proposal.skill_name, "skill_validated" if passed else "skill_rejected", {"proposal_id": proposal.id, "checks": checks})
        return proposal.validation

    def _authorize(self, authorized: bool, approver: str) -> None:
        if authorized or not bool(self._setting("require_approval", True)):
            return
        if bool(self._setting("allow_auto_approve", False)):
            return
        raise LearningError("Explicit approval is required for persistent skill changes")

    def _prepare_version(self, name: str) -> tuple[Skill | None, int]:
        skill = self.skills.discover().get(name)
        latest = self.store.latest_skill_version(name)
        if skill is not None and self.skills.user_dir.resolve() not in skill.path.resolve().parents:
            raise LearningError("Built-in skills are read-only")
        if skill is not None and latest is None:
            meta, _ = self._parse_content(skill.path.read_text(encoding="utf-8"))
            try:
                version = max(1, int(str(meta.get("version") or "1").split(".")[0]))
            except ValueError:
                version = 1
            self.store.save_skill_version(
                SkillVersion(skill_name=name, version=version, content=skill.path.read_text(encoding="utf-8"), status="archived").to_dict()
            )
            latest = self.store.latest_skill_version(name)
        if latest is not None and latest.get("status") != "archived":
            self.store.set_skill_version_status(name, int(latest["version"]), "archived")
        return skill, int(latest["version"]) + 1 if latest else 1

    def approve_proposal(self, proposal_id: str, authorized: bool = False, approver: str = "user") -> dict:
        if not bool(self._setting("enabled", True)):
            raise LearningError("Learning is disabled")
        self._authorize(authorized, approver)
        row = self._find_proposal(proposal_id)
        proposal = SkillProposal.from_dict(row)
        if proposal.status != "validated" or not proposal.validation.get("passed"):
            raise LearningError("Proposal must be validated before approval")
        skill, version = self._prepare_version(proposal.skill_name)
        content = self._set_meta(proposal.content, {"version": f"{version}.0", "target_version": version})
        self.skills.install(proposal.skill_name, content, overwrite=skill is not None)
        self.store.save_skill_version(
            SkillVersion(
                skill_name=proposal.skill_name,
                version=version,
                content=content,
                status="active",
                proposal_id=proposal.id,
                score=float(proposal.validation.get("details", {}).get("example_tests", {}).get("score") or 0.0),
            ).to_dict()
        )
        metrics = SkillMetrics.from_dict(self.store.get_skill_metrics(proposal.skill_name) or {})
        metrics.skill_name = proposal.skill_name
        metrics.active_version = version
        metrics.last_modified_at = utc_now()
        self.store.save_skill_metrics(metrics.to_dict())
        meta, body = self._parse_content(content)
        if self.layered_memory is not None:
            self.layered_memory.remember(
                "procedural",
                body,
                subject=f"skill:{proposal.skill_name}",
                provenance=f"learning:proposal:{proposal.id}",
                confidence=0.9,
                metadata={
                    "skill_name": proposal.skill_name,
                    "version": version,
                    "evidence": proposal.evidence,
                },
                verified=True,
            )
            self.layered_memory.forget(subject=f"active_improvement:{proposal.skill_name}")
        proposal.status = "approved"
        proposal.decided_at = utc_now()
        proposal.decided_by = approver
        self.store.save_learning_proposal(proposal.to_dict())
        self._event(proposal.skill_name, "skill_approved", {"proposal_id": proposal.id, "version": version, "approver": approver})
        return {"skill": proposal.skill_name, "version": version, "proposal_id": proposal.id}

    def reject_proposal(self, proposal_id: str, approver: str = "user", reason: str = "") -> dict:
        proposal = SkillProposal.from_dict(self._find_proposal(proposal_id))
        proposal.status = "rejected"
        proposal.decided_at = utc_now()
        proposal.decided_by = approver
        proposal.validation = {**proposal.validation, "rejection_reason": self._clean(reason, 500)}
        self.store.save_learning_proposal(proposal.to_dict())
        self._event(proposal.skill_name, "skill_rejected", {"proposal_id": proposal.id, "approver": approver, "reason": reason})
        return proposal.to_dict()

    def improve_skill(self, skill_name: str, failure: str, feedback: str = "", experience_ids=None) -> dict:
        if not bool(self._setting("enabled", True)):
            raise LearningError("Learning is disabled")
        skill = self.skills.discover().get(skill_name)
        if skill is None:
            raise LearningError(f"Skill '{skill_name}' not found")
        if self.skills.user_dir.resolve() not in skill.path.resolve().parents:
            raise LearningError("Built-in skills are read-only")
        latest = self.store.latest_skill_version(skill_name)
        if latest and latest.get("content"):
            content = latest["content"]
        else:
            content = skill.path.read_text(encoding="utf-8")
        meta, body = self._parse_content(content)
        rows = self.store.list_experiences(limit=int(self._setting("experience_retention", 500)))
        if experience_ids:
            selected = [self.store.get_experience(str(item)) for item in experience_ids]
            rows = [item for item in selected if item]
        successful = [row for row in rows if row.get("verified")][: int(self._setting("regression_limit", 6))]
        unsuccessful = [row for row in rows if not row.get("verified")][: int(self._setting("regression_limit", 6))]
        if not successful and not unsuccessful:
            raise LearningError("No execution history is available for this skill")
        evidence = [row["id"] for row in successful or unsuccessful]
        failure_text = self._clean(failure, 1000)
        feedback_text = self._clean(feedback, 1000)
        correction = "\n".join(
            [
                "## Learned correction",
                f"Observed failure: {failure_text}",
                f"User feedback: {feedback_text or 'not provided'}",
                "Check the failure condition before claiming completion and preserve a verified rollback point.",
            ]
        )
        updates = {
            "kind": "improve",
            "evidence": evidence,
            "examples": evidence,
            "target_version": int(latest["version"]) + 1 if latest else 2,
            "failure": failure_text,
            "sources": ["execution-history"],
        }
        proposal = SkillProposal(
            skill_name=skill_name,
            kind="improve",
            status="proposed",
            content=self._set_meta(content, updates) + "\n" + correction + "\n",
            meta={**meta, **updates},
            evidence=evidence,
        )
        self.store.save_learning_proposal(proposal.to_dict())
        if self.layered_memory is not None:
            self.layered_memory.set_working(
                f"active_improvement:{skill_name}",
                f"Revision proposed after failure: {failure_text}",
                provenance="learning:improvement",
            )
        self._event(skill_name, "improvement_proposed", {"proposal_id": proposal.id, "failure": failure_text})
        return proposal.to_dict()

    def rollback_skill(self, skill_name: str, version: int, authorized: bool = False, approver: str = "user") -> dict:
        if not bool(self._setting("enabled", True)):
            raise LearningError("Learning is disabled")
        self._authorize(authorized, approver)
        row = self.store.get_skill_version(skill_name, int(version))
        if row is None:
            raise LearningError(f"Version {version} of skill '{skill_name}' not found")
        skill = self.skills.discover().get(skill_name)
        if skill is None:
            raise LearningError(f"Skill '{skill_name}' not found")
        if self.skills.user_dir.resolve() not in skill.path.resolve().parents:
            raise LearningError("Built-in skills are read-only")
        self.skills.install(skill_name, row["content"], overwrite=True)
        for item in self.store.list_skill_versions(skill_name):
            status = "active" if int(item["version"]) == int(version) else "archived"
            self.store.set_skill_version_status(skill_name, int(item["version"]), status)
        metrics = SkillMetrics.from_dict(self.store.get_skill_metrics(skill_name) or {})
        metrics.skill_name = skill_name
        metrics.active_version = int(version)
        metrics.last_modified_at = utc_now()
        self.store.save_skill_metrics(metrics.to_dict())
        self._event(skill_name, "skill_rolled_back", {"version": int(version), "approver": approver})
        return {"skill": skill_name, "active_version": int(version)}

    def record_skill_result(self, skill_name: str, success: bool, verified: bool = False, duration_ms: float = 0.0, tokens: int = 0, cost: float = 0.0) -> dict:
        if not bool(self._setting("enabled", True)):
            return {}
        metrics = SkillMetrics.from_dict(self.store.get_skill_metrics(skill_name) or {})
        metrics.skill_name = skill_name
        metrics.execution_count += 1
        metrics.success_count += 1 if success else 0
        metrics.verification_count += 1 if verified else 0
        metrics.total_duration_ms += max(0.0, float(duration_ms))
        metrics.total_tokens += max(0, int(tokens))
        metrics.estimated_cost = round(metrics.estimated_cost + max(0.0, float(cost)), 6)
        if success:
            metrics.last_success_at = utc_now()
        self.store.save_skill_metrics(metrics.to_dict())
        self._event(skill_name, "skill_result", {"success": bool(success), "verified": bool(verified)})
        return metrics.to_dict()

    def metrics(self, skill_name: str | None = None) -> list[dict]:
        if skill_name:
            row = self.store.get_skill_metrics(skill_name)
            return [SkillMetrics.from_dict(row).to_dict()] if row else []
        return [SkillMetrics.from_dict(row).to_dict() for row in self.store.list_skill_metrics()]

    def versions(self, skill_name: str) -> list[dict]:
        return self.store.list_skill_versions(skill_name)

    def history(self, skill_name: str = "", query: str = "", limit: int | None = 50) -> dict:
        events = self.store.list_learning_events(skill_name=skill_name or None, limit=limit)
        experiences = self.store.list_experiences(query=query, limit=limit)
        return {"events": events, "experiences": experiences}

    def pending(self) -> list[dict]:
        return self.store.list_learning_proposals(status="proposed", limit=None) or []

    def context(self, query: str = "") -> str:
        if not bool(self._setting("enabled", True)):
            return ""
        try:
            budget = int(self._setting("max_context_chars", 1200))
        except (TypeError, ValueError):
            budget = 1200
        if budget <= 0:
            return ""
        lines = ["<learning-context>"]
        if self.layered_memory is not None:
            active = []
            for row in self.layered_memory.list(layer="working", limit=50):
                subject = str(row.get("subject") or "")
                if subject.startswith("active_improvement:"):
                    active.append(f"Active improvement {subject.split(':', 1)[1]}: {self._clean(row.get('content'), 300)}")
            for item in active[:3]:
                lines.append(item)
            for row in self.layered_memory.recall(query, limit=3):
                lines.append(f"Relevant memory [{row.get('layer')}:{row.get('subject')}]: {self._clean(row.get('content'), 300)}")
        for item in self.metrics()[:5]:
            lines.append(
                f"Skill quality {item['skill_name']}: success={item['success_rate']}, verified={item['verification_rate']}"
            )
        text = "\n".join(lines + ["</learning-context>"])
        return truncate(text, budget) if len(text) > budget else text
