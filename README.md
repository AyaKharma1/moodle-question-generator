# Secure AI Moodle Question Generator

Generate, review, approve and export **Moodle-compatible XML questions** from
university lecture materials (PDF / TXT / DOCX) — with an AI pipeline, an
instructor review workflow and security built in from the start.

The application is **standalone**: it does **not** connect to any live Moodle
server. It produces a `.xml` file that you import manually into Moodle. See
[`MOODLE_IMPORT_GUIDE.md`](MOODLE_IMPORT_GUIDE.md).

> Academic project for Hochschule Bochum. The default AI provider is an offline
> **mock**, so the whole app runs with no paid API key and no network.

---

## Workflow

```
Upload  →  Generate  →  Review & Approve  →  Export (Moodle XML)
```

Nothing is exported until an instructor **explicitly approves** it. The AI never
publishes anything on its own.

## Pipeline (why it is built this way)

```
Document → Text extraction → AI → Structured JSON → Validation → Moodle XML
```

The AI never writes XML directly. It returns structured data that is parsed into
typed objects, validated (grounding + duplicates), and only then converted to
Moodle XML by a separate, model-independent exporter. This keeps the exporter
testable and makes a misbehaving model unable to produce anything the app
accepts. More in [`ARCHITECTURE.md`](ARCHITECTURE.md) and
[`LEARNING_GUIDE.md`](LEARNING_GUIDE.md).

---

## Quick start (Docker — recommended)

Requires Docker + Docker Compose.

```bash
cp .env.example .env          # optional; defaults work for local demo
docker compose up --build
```

Then open:

- Frontend: <http://localhost:8081>
- API docs (Swagger): <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Register a user in the UI, upload `samples/sample_lecture_de.txt`, generate,
approve and export.

> If port 8081 or 8000 is busy on your machine, change the `ports:` mapping in
> `docker-compose.yml`.

### Optional demo seed

Create a demo instructor and load the sample lecture:

```bash
docker compose exec backend python -m scripts.seed
# Login: demo@hs-bochum.example / demo-password-123
```

---

## Running without Docker (local dev)

### Backend

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Use SQLite for a zero-setup local run (or point DATABASE_URL at Postgres):
export DATABASE_URL="sqlite:///./dev.db"
export SECRET_KEY="dev-secret"
export AI_PROVIDER="mock"
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

---

## Tests

**Do not take a green README on faith — run them.** All tests below were
executed and pass in this repository.

Backend (38 tests: schema, extraction, validation, XML export, full API
workflow, authorization, malicious uploads, prompt injection):

```bash
cd backend && source .venv/bin/activate
pytest
```

Frontend unit tests:

```bash
cd frontend && npm test
```

Build + typecheck the frontend:

```bash
cd frontend && npm run build
```

---

## Configuration

All configuration is environment-based (see [`.env.example`](.env.example)).
Key variables:

| Variable        | Default                    | Meaning                                   |
|-----------------|----------------------------|-------------------------------------------|
| `SECRET_KEY`    | dev placeholder            | JWT signing key — **set a strong value**  |
| `AI_PROVIDER`   | `mock`                     | `mock` (offline) or `openai`              |
| `AI_API_KEY`    | empty                      | only for `openai`                         |
| `DATABASE_URL`  | Postgres (compose)         | SQLAlchemy URL                            |
| `MAX_UPLOAD_BYTES` | 10 MB                   | upload size limit                         |

> Do **not** send real university documents to an external AI provider without
> authorization. See [`SECURITY.md`](SECURITY.md).

---

## Project layout

```
backend/        FastAPI app, AI pipeline, exporter, DB, tests, migrations
frontend/       Vue 3 + TypeScript SPA (Vite)
samples/        Synthetic lecture material (incl. a prompt-injection sample)
docker-compose.yml
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the module breakdown.

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — modules, data model, design decisions
- [`SECURITY.md`](SECURITY.md) — threat model and controls
- [`MOODLE_IMPORT_GUIDE.md`](MOODLE_IMPORT_GUIDE.md) — manual import test procedure
- [`LEARNING_GUIDE.md`](LEARNING_GUIDE.md) — explained for a CS student
- [`FUTURE_MOODLE_INTEGRATION.md`](FUTURE_MOODLE_INTEGRATION.md) — later integration notes

## Status / honesty notes

- Well-formed XML that follows the documented format is **not** proof of Moodle
  compatibility. Verify with a manual import (guide included).
- Prompt injection is mitigated, **not** solved. The real safety net is
  structured-output validation plus mandatory human approval.
