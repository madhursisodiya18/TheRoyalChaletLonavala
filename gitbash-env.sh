#!/usr/bin/env bash
# Source this in Git Bash:  source ./gitbash-env.sh
# Then: python app.py   or   ./run.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/Scripts/python.exe"

if [[ ! -f "$PY" ]]; then
  echo "Missing .venv at $ROOT/.venv"
  echo "Create it: py -3.13 -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt"
  return 1 2>/dev/null || exit 1
fi

export VIRTUAL_ENV="$ROOT/.venv"
export PATH="$ROOT/.venv/Scripts:$PATH"
hash -r 2>/dev/null

alias python="$PY"
alias pip="$ROOT/.venv/Scripts/pip.exe"

if [[ -z "${VIRTUAL_ENV_DISABLE_PROMPT:-}" ]]; then
  PS1="(.venv) ${PS1}"
fi

echo "Git Bash ready — Python: $PY"
