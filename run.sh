#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

set -a
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi
set +a

HOST="${BIND_HOST:-127.0.0.1}"
PORT="${BIND_PORT:-8080}"

exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT"
