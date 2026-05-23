#!/usr/bin/env bash
# Always use the project venv (Git Bash often leaves `python` pointing at Windows Store Python).
cd "$(dirname "$0")"
PY=".venv/Scripts/python.exe"
if [[ ! -f "$PY" ]]; then
  echo "Missing .venv. Create it with:"
  echo "  py -3.13 -m venv .venv"
  echo "  .venv/Scripts/python.exe -m pip install -r requirements.txt"
  exit 1
fi
exec "$PY" app.py "$@"
