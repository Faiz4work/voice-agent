#!/usr/bin/env bash
set -eu
RECEPTION_PROJECT_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
RECEPTION_VENV="${RECEPTION_VENV:-/home/$USER/.virtualenvs/voice-agent}"
cd -- "$RECEPTION_PROJECT_ROOT"
exec "$RECEPTION_VENV/bin/uvicorn" --app-dir "$RECEPTION_PROJECT_ROOT" --uds "${DOMAIN_SOCKET:?PythonAnywhere must supply DOMAIN_SOCKET}" main:app --workers 1 --no-access-log
