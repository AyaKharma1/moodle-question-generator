#!/usr/bin/env bash
# Startet die Moodle-Fragenbank lokal (macOS / Linux) mit einem Befehl:
#   bash start_mac.command        (oder im Finder doppelklicken)
# Beim ersten Start werden Python-Umgebung und npm-Pakete installiert.
# Beenden mit Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for candidate in python3.13 python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11, 3.12 oder 3.13 wurde nicht gefunden."
  echo "Bitte installieren: https://www.python.org/downloads/release/python-3128/"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js wurde nicht gefunden. Bitte installieren: https://nodejs.org"
  exit 1
fi

echo "==> Backend vorbereiten ($PY)"
cd backend
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt
export DATABASE_URL="${DATABASE_URL:-sqlite:///./dev.db}"
export SECRET_KEY="${SECRET_KEY:-dev-secret}"
export AI_PROVIDER="${AI_PROVIDER:-mock}"
alembic upgrade head
python -m uvicorn app.main:app --port 8000 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

echo "==> Frontend vorbereiten"
cd ../frontend
[ -d node_modules ] || npm install
(sleep 5; command -v open >/dev/null && open http://localhost:5173) &
echo "==> Läuft: http://localhost:5173  (Beenden mit Ctrl+C)"
npm run dev
