#!/usr/bin/env bash
# Wait for the database, apply migrations, then start the API.
set -euo pipefail

echo "[entrypoint] Waiting for the database to accept connections..."
python - <<'PY'
import os, time
import sqlalchemy
url = os.environ.get("DATABASE_URL", "")
engine = sqlalchemy.create_engine(url)
for attempt in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        print("[entrypoint] Database is ready.")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] not ready ({attempt+1}/30): {type(exc).__name__}")
        time.sleep(2)
else:
    raise SystemExit("[entrypoint] Database did not become ready in time.")
PY

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
