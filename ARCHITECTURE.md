# Architecture

## Goals

- A **standalone** app that exports valid Moodle XML (no live Moodle needed).
- The AI model is **interchangeable** and never produces XML directly.
- Moodle XML generation is **independent** of the AI model.
- Security and human approval are part of the design, not add-ons.

## High-level diagram

```
          ┌─────────────┐      HTTP/JSON       ┌───────────────────────────┐
          │  Vue 3 SPA  │  ─────────────────▶  │        FastAPI API         │
          │ (frontend)  │  ◀─────────────────  │                            │
          └─────────────┘                      │  auth · documents ·        │
                                               │  generation · questions ·  │
                                               │  export                    │
                                               └─────────────┬──────────────┘
                                                             │
     ┌──────────────┬───────────────┬─────────────┬─────────┴───────┬──────────────┐
     ▼              ▼               ▼             ▼                 ▼              ▼
document_      ai_generation   question_      question_        moodle_export   security
processing     (provider +     validation     management       (lxml → XML)    (JWT, bcrypt,
(PDF/TXT/DOCX, mock/openai)    (grounding,    (persist, convert)                authz)
 magic bytes)                  duplicates)
                                   │
                                   ▼
                              PostgreSQL (SQLAlchemy + Alembic)
```

## The pipeline

```
Document → Text extraction → AI → Structured JSON → Validation → Moodle XML
```

1. **document_processing** extracts text and validates the file by magic bytes.
2. **ai_generation** builds a hardened prompt, calls the active provider, and
   returns raw dicts. A model-independent *service* parses those into typed
   `GeneratedQuestion` objects.
3. **question_validation** adds grounding and duplicate checks.
4. Questions are stored as **pending** and go through instructor review.
5. **moodle_export** converts approved questions to Moodle XML with `lxml`.

The single typed representation in the middle (`GeneratedQuestion`) is the key
design idea: the AI layer and the exporter never touch each other, so each can
be tested and changed independently.

## Backend modules (`backend/app`)

| Module                 | Responsibility                                                        |
|------------------------|----------------------------------------------------------------------|
| `config.py`            | Environment-based settings (Pydantic Settings).                      |
| `database.py`          | Engine, session, `Base`; parameterized queries only.                 |
| `models.py`            | SQLAlchemy ORM (7 tables).                                           |
| `schemas/question.py`  | Domain model + structural validation rules per question type.        |
| `schemas/api.py`       | HTTP request/response models.                                        |
| `document_processing/` | `extractor.py` (text + magic bytes), `storage.py` (safe uploads).    |
| `ai_generation/`       | `base.py` interface, `mock_provider.py`, `openai_provider.py`, `prompts.py`, `factory.py`, `service.py`. |
| `question_validation/` | Grounding + duplicate detection (dependency-free, explainable).      |
| `question_management/` | Persist generated questions; convert ORM ↔ domain.                   |
| `moodle_export/`       | `exporter.py` — Moodle XML via `lxml`.                               |
| `security/`            | `auth.py` (bcrypt + JWT), `deps.py` (current user, ownership).       |
| `api/`                 | Routers: `auth`, `documents`, `generation`, `questions`, `export`.   |

## Data model (normalized)

```
users ──1─┬─< documents ──1──< questions ──1──< answers
          │                         │
          └─< questions             ├──< question_sources   (provenance / grounding)
                                     ├──< question_reviews   (approve/reject audit)
          └─< export_history        └─ original_snapshot (JSON of first AI version)
```

Key points:

- **Every content row has an `owner_id`** → authorization is checked per row.
- `questions.status` ∈ `pending | approved | rejected`. Only `approved` can be
  exported (enforced in the export route, not the UI).
- `questions.original_snapshot` stores the first AI version as JSON, so an
  instructor can edit freely **without losing the original source**.
- `question_sources.snippet` records where a question is grounded (citation).
- `export_history` makes every export **traceable** (who, when, which ids).
- Foreign keys use `ON DELETE CASCADE`/`SET NULL`; indexes on all FKs and
  `questions.status`.

## Why these choices

- **FastAPI + Pydantic** give typed request/response validation for free and
  auto-generated API docs (`/docs`) — good for a student project and for safety.
- **SQLAlchemy + Alembic**: portable models (Postgres in prod, SQLite in tests),
  versioned schema migrations, parameterized queries (no SQL injection).
- **lxml** for XML: correct escaping/encoding and no string concatenation.
- **Mock AI provider** makes the whole system developable, testable and
  demoable offline and deterministically.
- **No Kubernetes/microservices**: one backend, one frontend, one database. The
  module boundaries above are enough separation for this scope.

## Request lifecycle example (`POST /api/generate`)

1. `get_current_user` validates the JWT and loads the `User`.
2. The document is fetched **and ownership checked** (`404` otherwise).
3. `get_provider(settings)` returns the active AI provider.
4. `run_generation(...)` → raw dicts → parsed `GeneratedQuestion`s → validation.
5. `persist_generated(...)` stores questions as `pending` with answers, source
   snippet and the original snapshot.
6. The response includes created questions + per-question warnings.
