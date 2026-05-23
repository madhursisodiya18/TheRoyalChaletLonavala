#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/Scripts/python.exe"

if [[ ! -f "$PY" ]]; then
  echo "Missing .venv. Run in PowerShell:"
  echo "  py -3.13 -m venv .venv"
  echo "  .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
  exit 1
fi

cd "$ROOT"
exec "$PY" "$ROOT/app.py" "$@"
