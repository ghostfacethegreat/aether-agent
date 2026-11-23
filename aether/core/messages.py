from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str = ""
    name: str = ""
    tool_call_id: str = ""
    tool_calls: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = [call if isinstance(call, dict) else call.__dict__ for call in self.tool_calls]
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content") or "",
            name=data.get("name", ""),
            tool_call_id=data.get("tool_call_id", ""),
            tool_calls=data.get("tool_calls") or [],
            metadata=data.get("metadata") or {},
        )


def tool_message(call_id: str, content: str, name: str = "") -> dict:
    return {"role": "tool", "tool_call_id": call_id, "name": name, "content": content}
