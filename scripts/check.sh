#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m compileall -q aether tests
python3 -m unittest discover -s tests

tmp_home="$(mktemp -d)"
trap 'rm -rf "$tmp_home"' EXIT

AETHER_HOME="$tmp_home" python3 -m aether doctor >/dev/null
smoke_output="$(AETHER_HOME="$tmp_home" python3 -m aether --provider mock run "Say hello")"
case "$smoke_output" in
  *"mock provider is active"*) ;;
  *)
    echo "mock CLI smoke test failed" >&2
    exit 1
    ;;
esac

if grep -R -E 'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}' \
  --exclude-dir=.git --exclude-dir=__pycache__ --exclude='*.pyc' .; then
  echo "possible secret found" >&2
  exit 1
fi

python3 scripts/benchmark.py

python3 -c '
import pathlib, re, sys
root = pathlib.Path(".")
pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
broken = []
for path in root.rglob("*.md"):
    for target in pattern.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            broken.append((str(path), target))
if broken:
    print("broken local links:", broken, file=sys.stderr)
    sys.exit(1)
'

echo "all checks passed"
