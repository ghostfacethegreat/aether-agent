import re
from datetime import datetime, timedelta, timezone

from aether.utils import make_id, truncate, utc_now

LAYERS = ("working", "episodic", "semantic", "procedural", "user")

DEFAULT_CONFIDENCE = {
    "working": 0.60,
    "episodic": 0.55,
    "semantic": 0.75,
    "procedural": 0.85,
    "user": 0.90,
}

LAYER_WEIGHT = {
    "working": 0.60,
    "episodic": 0.10,
    "semantic": 0.35,
    "procedural": 0.30,
    "user": 0.45,
}

_WORD = re.compile(r"\w+", re.UNICODE)


def _normalize(text) -> str:
    return " ".join(_WORD.findall(str(text or "").lower()))


def _expiry(days) -> str:
    try:
        amount = float(days)
    except (TypeError, ValueError):
        return ""
    return (datetime.now(timezone.utc) + timedelta(days=amount)).isoformat(timespec="seconds")


class LayeredMemory:
    def __init__(self, markdown_store, store, config=None, persist=True, session_id=""):
        self.markdown = markdown_store
        self.store = store
        self.config = config
        self.persist = bool(persist)
        self.session_id = str(session_id or "")
        self.enabled = bool(self._setting("memory.layered.enabled", True)) and self.persist
        if self.enabled:
            self.migrate_markdown()

    def _setting(self, key: str, default):
        if self.config is None:
            return default
        return self.config.get(key, default)

    def _exact_exists(self, layer: str, subject: str, content: str, session_id: str) -> bool:
        wanted_subject = _normalize(subject)
        wanted_content = _normalize(content)
        for row in self.store.list_memory_items(layer=layer, status="active"):
            if row["session_id"] != session_id:
                continue
            if _normalize(row["subject"]) == wanted_subject and _normalize(row["content"]) == wanted_content:
                return True
        return False

    def remember(
        self,
        layer: str,
        content,
        subject="",
        provenance="manual",
        confidence=None,
        session_id=None,
        metadata=None,
        expires_days=None,
        verified=False,
        item_id=None,
    ) -> dict | None:
        if not self.enabled:
            return None
        name = str(layer or "").strip().lower()
        if name not in LAYERS:
            raise ValueError(f"Unknown memory layer '{layer}'")
        text = str(content or "").strip()
        if not text:
            return None
        details = dict(metadata) if isinstance(metadata, dict) else {}
        if name == "procedural" and not (verified or details.get("verified")):
            raise ValueError("Procedural memory requires verified evidence")
        sid = str(session_id if session_id is not None else self.session_id)
        if expires_days is None and name == "working":
            expires_days = self._setting("memory.layered.working_days", 1)
        expires_at = _expiry(expires_days) if expires_days is not None else ""
        for row in self.store.list_memory_items(layer=name, status="active"):
            if row["session_id"] != sid:
                continue
            if _normalize(row["subject"]) == _normalize(subject) and _normalize(row["content"]) == _normalize(text):
                row["provenance"] = str(provenance)
                row["confidence"] = float(confidence if confidence is not None else row["confidence"])
                row["metadata"] = details or row["metadata"]
                row["expires_at"] = expires_at or row["expires_at"]
                row["updated_at"] = utc_now()
                self.store.save_memory_item(row)
                return row
        item = {
            "id": str(item_id or make_id("memory")),
            "session_id": sid,
            "layer": name,
            "subject": str(subject or ""),
            "content": text,
            "provenance": str(provenance),
            "confidence": float(confidence if confidence is not None else DEFAULT_CONFIDENCE[name]),
            "status": "active",
            "metadata": details,
            "supersedes": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "expires_at": expires_at,
        }
        self.store.save_memory_item(item)
        return item

    def add(self, *args, **kwargs) -> dict | None:
        return self.remember(*args, **kwargs)

    def set_working(self, subject: str, content, session_id=None, provenance="turn", confidence=None) -> dict | None:
        if not self.enabled:
            return None
        sid = str(session_id if session_id is not None else self.session_id)
        for row in self.store.list_memory_items(layer="working", session_id=sid, status="active"):
            row["status"] = "superseded"
            row["metadata"] = dict(row.get("metadata") or {})
            row["metadata"]["superseded_by_working_update"] = True
            row["updated_at"] = utc_now()
            self.store.save_memory_item(row)
        return self.remember(
            "working",
            content,
            subject=subject,
            provenance=provenance,
            confidence=confidence,
            session_id=sid,
        )

    def _score(self, row: dict, query_tokens: set[str], session_id: str, index: int) -> float:
        content_tokens = set(_WORD.findall(f"{row.get('subject', '')} {row.get('content', '')}".lower()))
        overlap = len(query_tokens & content_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
        try:
            confidence = float(row.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        score = overlap * 4.0 + confidence + LAYER_WEIGHT.get(row.get("layer", ""), 0.0)
        if row.get("session_id") == session_id:
            score += 0.15
        if row.get("layer") == "working":
            score += 0.50
        score += max(0.0, 0.03 - index * 0.001)
        return score

    def _line(self, row: dict) -> str:
        layer = str(row.get("layer") or "memory")
        subject = str(row.get("subject") or "general").replace("\n", " ")
        content = truncate(str(row.get("content") or "").replace("\n", " "), 500)
        source = str(row.get("provenance") or "unknown").replace("\n", " ")
        try:
            confidence = float(row.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        return f"- [{layer}:{subject}] {content} (source: {source}; confidence: {confidence:.2f})"

    def recall(
        self,
        query="",
        limit=None,
        max_chars=None,
        layers=None,
        session_id=None,
    ) -> list[dict]:
        if not self.enabled:
            return []
        sid = str(session_id if session_id is not None else self.session_id)
        try:
            count = int(limit if limit is not None else self._setting("memory.layered.recall_limit", 12))
        except (TypeError, ValueError):
            count = 12
        count = max(0, count)
        if not count:
            return []
        text = str(query or "")
        wanted_layers = set(layers or [])
        rows = (
            self.store.search_memory_items(text, limit=max(count * 4, 20))
            if text.strip()
            else self.store.list_memory_items(limit=max(count * 4, 20))
        )
        query_tokens = set(_WORD.findall(text.lower()))
        candidates = []
        seen = set()
        for index, row in enumerate(rows):
            item_id = str(row.get("id") or "")
            if not item_id or item_id in seen:
                continue
            if wanted_layers and row.get("layer") not in wanted_layers:
                continue
            if row.get("layer") == "working" and row.get("session_id") != sid:
                continue
            seen.add(item_id)
            candidates.append((self._score(row, query_tokens, sid, index), index, row))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        selected = []
        used = 0
        for _, _, row in candidates:
            line = self._line(row)
            if max_chars is not None and used + len(line) > max_chars:
                continue
            selected.append(row)
            used += len(line) + 1
            if len(selected) >= count:
                break
        return selected

    def search(self, query, **kwargs) -> list[dict]:
        return self.recall(query, **kwargs)

    def context(self, task="", max_chars=None) -> str:
        if not self.enabled:
            return ""
        try:
            budget = int(max_chars if max_chars is not None else self._setting("memory.layered.context_chars", 1800))
        except (TypeError, ValueError):
            budget = 1800
        if budget <= 0:
            return ""
        items = self.recall(task, max_chars=budget)
        if not items:
            return ""
        body = "\n".join(self._line(item) for item in items)
        overhead = len("<layered-memory>") + len("</layered-memory>") + 2
        if len(body) + overhead > budget:
            body = truncate(body, max(0, budget - overhead))
        if not body:
            return ""
        return "<layered-memory>\n" + body + "\n</layered-memory>"

    def list(
        self,
        layer=None,
        session_id=None,
        status="active",
        include_expired=False,
        limit=None,
    ) -> list[dict]:
        if not self.enabled:
            return []
        return self.store.list_memory_items(
            layer=layer,
            session_id=session_id,
            status=status,
            include_expired=include_expired,
            limit=limit,
        )

    def get(self, item_id: str) -> dict | None:
        if not self.enabled:
            return None
        return self.store.get_memory_item(item_id)

    def delete(self, item_id: str) -> bool:
        if not self.enabled:
            return False
        return self.store.delete_memory_item(item_id)

    def forget(self, subject=None, layer=None, session_id=None) -> int:
        if not self.enabled:
            return 0
        removed = 0
        for row in self.list(layer=layer, session_id=session_id):
            if subject is not None and row.get("subject") != subject:
                continue
            if self.delete(str(row["id"])):
                removed += 1
        return removed

    def clear(self, layer=None, session_id=None) -> int:
        if not self.enabled:
            return 0
        removed = 0
        for row in self.list(layer=layer, session_id=session_id):
            if self.delete(str(row["id"])):
                removed += 1
        return removed

    def correct(
        self,
        item_id: str,
        content,
        provenance="correction",
        confidence=None,
        session_id=None,
    ) -> dict | None:
        if not self.enabled:
            return None
        old = self.store.get_memory_item(item_id)
        if not old:
            return None
        new = self.remember(
            old.get("layer", "semantic"),
            content,
            subject=old.get("subject", ""),
            provenance=provenance,
            confidence=confidence,
            session_id=session_id if session_id is not None else old.get("session_id", ""),
            metadata={"corrected_from": item_id},
        )
        if new is None:
            return None
        metadata = dict(old.get("metadata") or {})
        metadata["corrected_by"] = new["id"]
        old["status"] = "superseded"
        old["metadata"] = metadata
        old["updated_at"] = utc_now()
        self.store.save_memory_item(old)
        return new

    def contradictions(self) -> list[dict]:
        if not self.enabled:
            return []
        groups = {}
        for row in self.store.list_memory_items(layer="semantic", status="active"):
            groups.setdefault(_normalize(row.get("subject")), []).append(row)
        result = []
        for rows in groups.values():
            for index, left in enumerate(rows):
                for right in rows[index + 1 :]:
                    if _normalize(left.get("content")) == _normalize(right.get("content")):
                        continue
                    result.append({"left": left, "right": right, "subject": left.get("subject", "")})
        return result

    def resolve_contradiction(self, winner_id: str, loser_id: str) -> bool:
        if not self.enabled or winner_id == loser_id:
            return False
        winner = self.store.get_memory_item(winner_id)
        loser = self.store.get_memory_item(loser_id)
        if not winner or not loser or winner.get("layer") != "semantic" or loser.get("layer") != "semantic":
            return False
        winner_metadata = dict(winner.get("metadata") or {})
        winner_metadata["contradiction_resolved_with"] = loser_id
        winner["metadata"] = winner_metadata
        loser_metadata = dict(loser.get("metadata") or {})
        loser_metadata["contradiction_resolved_with"] = winner_id
        loser["status"] = "contradicted"
        loser["metadata"] = loser_metadata
        loser["updated_at"] = utc_now()
        self.store.save_memory_item(winner)
        self.store.save_memory_item(loser)
        return True

    def prune_expired(self) -> int:
        if not self.enabled:
            return 0
        now = utc_now()
        pruned = 0
        for row in self.store.list_memory_items(status="active", include_expired=True):
            expires_at = str(row.get("expires_at") or "")
            if not expires_at or expires_at > now:
                continue
            row["status"] = "expired"
            row["updated_at"] = now
            self.store.save_memory_item(row)
            pruned += 1
        return pruned

    def consolidate(self) -> dict:
        if not self.enabled:
            return {"expired": 0, "duplicates": 0}
        expired = self.prune_expired()
        groups = {}
        for row in self.store.list_memory_items(status="active"):
            key = (row.get("layer", ""), _normalize(row.get("subject")), _normalize(row.get("content")))
            groups.setdefault(key, []).append(row)
        duplicates = 0
        for rows in groups.values():
            if len(rows) < 2:
                continue
            keep = max(
                rows,
                key=lambda row: (
                    float(row.get("confidence", 0.5)),
                    str(row.get("updated_at") or ""),
                    str(row.get("id") or ""),
                ),
            )
            for row in rows:
                if row["id"] == keep["id"]:
                    continue
                metadata = dict(row.get("metadata") or {})
                metadata["duplicate_of"] = keep["id"]
                row["status"] = "duplicate"
                row["metadata"] = metadata
                row["updated_at"] = utc_now()
                self.store.save_memory_item(row)
                duplicates += 1
        return {"expired": expired, "duplicates": duplicates}

    def record_episode(self, objective, outcome, status="complete", tool_log=None, session_id=None) -> dict | None:
        if not self.enabled:
            return None
        sid = str(session_id if session_id is not None else self.session_id)
        entries = tool_log or []
        failures = [str(item.get("name") or "tool") for item in entries if not item.get("ok", True)]
        metadata = {
            "objective": truncate(objective, 500),
            "outcome": truncate(outcome, 1000),
            "status": str(status),
            "tool_calls": len(entries),
            "failures": failures[:10],
        }
        content = (
            f"Objective: {truncate(objective, 160)} | "
            f"Outcome: {truncate(outcome, 300)} | "
            f"Status: {status} | "
            f"Failures: {', '.join(failures[:5]) or 'none'}"
        )
        return self.remember(
            "episodic",
            content,
            subject=f"session:{sid or 'none'}",
            provenance=f"turn:{sid or 'none'}",
            confidence=0.55,
            session_id=sid,
            metadata=metadata,
        )

    def migrate_markdown(self) -> int:
        if not self.enabled:
            return 0
        migrated = 0
        for user, layer, prefix, provenance, confidence in (
            (False, "semantic", "markdown", "markdown:memory", 0.70),
            (True, "user", "markdown:user", "markdown:user", 0.90),
        ):
            for category, entry in self.markdown.list(user):
                subject = f"{prefix}:{category}"
                if self._exact_exists(layer, subject, entry, ""):
                    continue
                item = self.remember(
                    layer,
                    entry,
                    subject=subject,
                    provenance=provenance,
                    confidence=confidence,
                    session_id="",
                    metadata={"migrated_from": "MEMORY.md" if not user else "USER.md", "category": category},
                )
                if item:
                    migrated += 1
        return migrated

    def export_data(self) -> dict:
        return {
            "version": 2,
            "markdown": self.markdown.export(),
            "layers": [dict(row) for row in self.store.list_memory_items(status=None, include_expired=True)],
        }

    def import_data(self, data: dict, merge=True) -> int:
        if not isinstance(data, dict):
            raise ValueError("Layered memory import must be a JSON object")
        if isinstance(data.get("markdown"), dict):
            self.markdown.import_data(data["markdown"], merge=merge)
        if not self.enabled:
            return 0
        if not merge:
            self.clear()
        imported = 0
        rows = data.get("layers") or data.get("memory_items") or []
        if not isinstance(rows, list):
            return 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = self.remember(
                row.get("layer", "semantic"),
                row.get("content", ""),
                subject=row.get("subject", ""),
                provenance=row.get("provenance", "import"),
                confidence=row.get("confidence"),
                session_id=row.get("session_id", ""),
                metadata=row.get("metadata"),
            )
            if item:
                imported += 1
        return imported

    def counts(self) -> dict:
        result = {layer: 0 for layer in LAYERS}
        for row in self.list():
            layer = row.get("layer")
            if layer in result:
                result[layer] += 1
        result["total"] = sum(result.values())
        return result
