#!/usr/bin/env bash
set -euo pipefail

AETHER_HOME="${AETHER_HOME:-$HOME/.aether}"
BIN_DIR="$AETHER_HOME/bin"
VENV_DIR="$AETHER_HOME/venv"
REMOVE_DATA=0

for arg in "$@"; do
  case "$arg" in
    --data) REMOVE_DATA=1 ;;
    *) echo "error: unknown option '$arg'" >&2; exit 1 ;;
  esac
done

rm -f "$BIN_DIR/aether"

link="$HOME/.local/bin/aether"
if [ -L "$link" ] && [ "$(readlink "$link")" = "$BIN_DIR/aether" ]; then
  rm -f "$link"
fi

if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
fi

echo "Aether wrapper and virtual environment removed from $AETHER_HOME"

if [ "$REMOVE_DATA" -eq 1 ]; then
  echo "This will delete config, sessions, memory, skills, logs, and scheduled jobs in $AETHER_HOME"
  read -r -p "Type 'yes' to continue: " answer
  if [ "$answer" = "yes" ]; then
    rm -rf "$AETHER_HOME"
    echo "Aether data removed"
  else
    echo "Data kept"
  fi
fi
