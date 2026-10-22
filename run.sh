#!/usr/bin/env bash
# One-command local demo: installs dependencies, seeds synthetic data, builds the UI, starts the server.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r backend/requirements.txt

(cd frontend && npm install --no-audit --no-fund && npm run build)

cd backend
if [ ! -f data/vidyapramaan.db ] || [ "${RESEED:-0}" = "1" ]; then
  ../.venv/bin/python -m app.seed > /dev/null
  echo "Seeded synthetic dataset (240 institutions, ~48k students)."
fi
echo "Open http://localhost:8000  (API docs: http://localhost:8000/docs)"
exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
