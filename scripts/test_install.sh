#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cp -R "$ROOT" "$TMP/source"
# Build a real clean source remote. Copying the checkout's existing .git directory
# leaves the copied worktree clean, so a second snapshot commit would fail.
rm -rf "$TMP/source/.git"
git -C "$TMP/source" init -q
git -C "$TMP/source" add -A
git -C "$TMP/source" -c user.name="Aether Test" -c user.email="test@example.invalid" commit -q -m "test install snapshot"
git clone -q "$TMP/source" "$TMP/clone"

AETHER_HOME="$TMP/home" "$TMP/clone/scripts/install.sh" >/dev/null
"$TMP/home/bin/aether" version
"$TMP/home/bin/aether" memory add "install-preservation-marker" --category general >/dev/null
smoke="$("$TMP/home/bin/aether" --provider mock run "Say hello")"
case "$smoke" in
  *"mock provider is active"*) ;;
  *) echo "installed CLI smoke test failed" >&2; exit 1 ;;
esac
bench="$("$TMP/home/bin/aether" --provider mock models benchmark --samples 1)"
case "$bench" in
  *"Offline deterministic benchmark"*) ;;
  *) echo "installed benchmark command failed" >&2; exit 1 ;;
esac

AETHER_HOME="$TMP/home" "$TMP/clone/scripts/uninstall.sh" >/dev/null
if [ -e "$TMP/home/bin/aether" ]; then
  echo "uninstall did not remove wrapper" >&2
  exit 1
fi
python3 - "$TMP" <<'PY'
import sqlite3
import sys
from pathlib import Path

home = Path(sys.argv[1]) / "home"
if not (home / "config.json").is_file():
    raise SystemExit("uninstall removed configuration")
with sqlite3.connect(home / "state.db") as db:
    row = db.execute(
        "SELECT content FROM memory_items WHERE content LIKE ? LIMIT 1",
        ("%install-preservation-marker%",),
    ).fetchone()
if not row:
    raise SystemExit("uninstall removed memory")
PY

echo "local git-remote install test passed"
