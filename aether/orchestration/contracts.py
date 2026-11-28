ROLE_CONTRACTS = {
    "researcher": {"required": {"summary": str, "findings": list, "sources": list}},
    "planner": {"required": {"summary": str, "steps": list, "risks": list, "acceptance": list}},
    "architect": {"required": {"summary": str, "design": list, "tradeoffs": list, "files": list, "risks": list}},
    "developer": {"required": {"summary": str, "changes": list, "tests": list, "risks": list}},
    "debugger": {"required": {"summary": str, "reproduction": str, "root_cause": str, "fixes": list, "verification": list}},
    "tester": {
        "required": {"summary": str, "checks": list, "failures": list, "verdict": str},
        "enums": {"verdict": ("pass", "fail", "partial")},
    },
    "security_auditor": {
        "required": {"summary": str, "findings": list, "verdict": str},
        "enums": {"verdict": ("approve", "changes_requested")},
    },
    "data_analyst": {
        "required": {"summary": str, "methods": list, "findings": list, "limitations": list, "confidence": str},
        "enums": {"confidence": ("low", "medium", "high")},
    },
    "documentation_writer": {"required": {"summary": str, "files": list, "changes": list, "open_questions": list}},
    "reviewer": {
        "required": {"summary": str, "findings": list, "verdict": str},
        "enums": {"verdict": ("approve", "changes_requested")},
    },
    "verifier": {
        "required": {"summary": str, "checks": list, "failures": list, "verdict": str},
        "enums": {"verdict": ("pass", "fail", "partial")},
    },
}


def validate_role_output(role, payload):
    """Return deterministic contract violations for a role's structured result."""
    contract = ROLE_CONTRACTS.get(str(role or ""))
    if contract is None:
        return []
    if not isinstance(payload, dict):
        return ["result must be a JSON object"]
    errors = []
    for key, expected_type in contract.get("required", {}).items():
        if key not in payload:
            errors.append(f"missing required field: {key}")
            continue
        if not isinstance(payload[key], expected_type):
            errors.append(f"{key} must be {expected_type.__name__}")
    for key, allowed in contract.get("enums", {}).items():
        value = payload.get(key)
        if isinstance(value, str) and value not in allowed:
            errors.append(f"{key} must be one of: {', '.join(allowed)}")
    return errors
