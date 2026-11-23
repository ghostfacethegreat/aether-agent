#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AETHER_HOME="${AETHER_HOME:-$HOME/.aether}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BIN_DIR="$AETHER_HOME/bin"
VENV_DIR="$AETHER_HOME/venv"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: $PYTHON_BIN not found. Set PYTHON_BIN to a Python 3.10+ interpreter." >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/aether/__init__.py" ]; then
  echo "error: installer could not find Aether source at $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$AETHER_HOME" "$BIN_DIR" "$HOME/.local/bin"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m compileall -q "$SOURCE_DIR/aether"

cat > "$BIN_DIR/aether" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export AETHER_HOME="$AETHER_HOME"
export PYTHONPATH="$SOURCE_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$VENV_DIR/bin/python" -m aether "\$@"
EOF
chmod +x "$BIN_DIR/aether"

if [ ! -e "$HOME/.local/bin/aether" ]; then
  ln -s "$BIN_DIR/aether" "$HOME/.local/bin/aether"
fi

"$BIN_DIR/aether" setup

echo
echo "Aether installed from: $SOURCE_DIR"
echo "Wrapper: $BIN_DIR/aether"
echo "Add this to your shell profile if needed:"
echo "  export PATH=\"$HOME/.local/bin:\$PATH\""
