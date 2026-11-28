import re
from pathlib import Path

SYMBOL_INDEX_VERSION = 1

_SYMBOL_PATTERNS = {
    ".py": (
        (re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\b"), "function"),
        (re.compile(r"^\s*class\s+([A-Za-z_]\w*)\b"), "class"),
    ),
    ".js": (
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\b"), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)\b"), "class"),
        (re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\b"), "interface"),
        (re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\b"), "type"),
        (re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_$][\w$]*)\b"), "enum"),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"), "function"),
    ),
}
_SYMBOL_PATTERNS[".jsx"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".ts"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".tsx"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".mjs"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".cjs"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".mts"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".cts"] = _SYMBOL_PATTERNS[".js"]
_SYMBOL_PATTERNS[".lua"] = (
    (re.compile(r"^\s*(?:local\s+)?function\s+([A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)*)\b"), "function"),
    (re.compile(r"^\s*([A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)*)\s*=\s*function\b"), "function"),
)
_SYMBOL_PATTERNS[".go"] = (
    (re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\b"), "function"),
    (re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+(?:struct|interface)\b"), "type"),
)
_SYMBOL_PATTERNS[".rs"] = (
    (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:(?:async|unsafe|const)\s+)*(?:fn|struct|enum|trait|type)\s+([A-Za-z_]\w*)\b"), "declaration"),
)


def extract_symbols(relative, content):
    patterns = _SYMBOL_PATTERNS.get(Path(relative).suffix.lower(), ())
    symbols = []
    for number, line in enumerate(content.splitlines(), start=1):
        for pattern, kind in patterns:
            match = pattern.match(line)
            if match:
                symbols.append({
                    "name": match.group(1),
                    "kind": kind,
                    "path": relative,
                    "line": number,
                })
                break
    return symbols
