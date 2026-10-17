# Learning Guide

Written for an Informatik student. It explains *why* the system looks the way it
does, and which parts map to **AI Engineering**, **IT Security** and **Database
Engineering**. Read it alongside [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. How the AI pipeline works

```
Document → Text extraction → AI → Structured JSON → Validation → Moodle XML
```

- **Text extraction** (`document_processing/extractor.py`): we pull plain text
  out of PDF/TXT/DOCX. We check the file's *real* type by its first bytes
  (magic bytes), not just its name.
- **Prompt building** (`ai_generation/prompts.py`): we write a *system prompt*
  with the hard rules (how many questions, which type, which language, "answer
  in JSON only") and a *user prompt* that contains the lecture text inside a
  clearly marked block. We tell the model the material is **data, not
  commands**.
- **Provider** (`ai_generation/`): an `AIProvider` interface with two
  implementations — a `MockAIProvider` (offline, deterministic, used in tests
  and demos) and an `OpenAIProvider` (real model, optional). The rest of the app
  only knows the interface, so swapping models changes one line of config.
- **Parsing + validation**: the model returns JSON. We parse each item into a
  strict `GeneratedQuestion` object and run grounding/duplicate checks.

### Why a mock provider?
So the whole app runs with **no API key, no network, no cost**, and so tests are
**deterministic**. This is a standard technique: isolate the external dependency
behind an interface and provide a fake for development and testing.

---

## 2. Why JSON *before* XML (this is the key design idea)

We **never** ask the AI to write Moodle XML. Instead:

1. The AI returns **structured JSON**.
2. JSON is parsed into a typed object (`GeneratedQuestion`) with validation
   rules (e.g. "multiple choice needs ≥2 options and ≥1 correct").
3. A separate exporter turns the *validated object* into XML.

Reasons:

- **Validation.** You can check JSON fields precisely. XML from a language model
  is easy to get subtly wrong (missing tags, bad fractions) and hard to validate
  meaningfully.
- **Separation of concerns.** The AI layer and the XML layer never touch each
  other. You can change the model without touching the exporter, and change the
  export format without touching the AI.
- **Security.** A model that is tricked by a prompt injection still cannot
  produce valid output, because its output must pass the schema first.
- **Testability.** The exporter is a pure function `questions → XML` with its own
  unit tests, independent of any model.

This "typed model in the middle" pattern is worth remembering — it applies
whenever an LLM feeds a system that needs correctness.

---

## 3. How the database is structured

PostgreSQL via SQLAlchemy (ORM) + Alembic (migrations). Seven normalized tables:
`users, documents, questions, answers, question_sources, question_reviews,
export_history`.

Things to understand:

- **Normalization**: answers live in their own table (one row per option), not
  as a blob inside the question. Sources and reviews are separate tables too.
  This avoids redundancy and keeps each fact in one place.
- **Foreign keys + indexes**: every child row points at its parent
  (`answers.question_id → questions.id`) with `ON DELETE CASCADE`, and FKs are
  indexed for fast lookups.
- **State machine**: `questions.status` is `pending → approved/rejected`. The
  export endpoint refuses anything not `approved`.
- **Provenance**: `original_snapshot` keeps the first AI version as JSON, so edits
  never destroy the original; `question_sources.snippet` records the citation.
- **Migrations**: `alembic upgrade head` creates/updates the schema in a
  versioned, repeatable way — never "edit the DB by hand".
- **Parameterized queries**: the ORM builds SQL with bound parameters, which is
  what prevents SQL injection.

> Tip: the same models run on SQLite (fast tests) and Postgres (real), because we
> only use portable column types.

---

## 4. How authentication and authorization work

- **Authentication** = *who are you?* On login we verify the bcrypt password hash
  and issue a signed **JWT** containing the user id and an expiry. The client
  sends it as `Authorization: Bearer <token>` on every request.
- **Authorization** = *are you allowed to do this?* Each document and question
  has an `owner_id`. Every protected route loads the current user from the token
  and checks ownership on the **backend**. Another user's resource returns
  `404`.

Important lesson: **never rely on the frontend for authorization.** Our Vue
router guard only tidies the UI; the real checks are server-side, because a
client can send any request it likes.

---

## 5. How the app can later connect to Moodle

Today the app is standalone and exports an XML file you import manually. It is
designed so a real Moodle integration can be added later **without touching the
AI pipeline or the exporter** — see
[`FUTURE_MOODLE_INTEGRATION.md`](FUTURE_MOODLE_INTEGRATION.md). The short version:
add a new `moodle_integration` module that takes already-approved questions and
pushes them via Moodle's web-service API, behind the same approval gate.

---

## 6. Which parts are relevant for which skill area

**AI Engineering**
- `ai_generation/` — provider interface, prompt design, prompt-injection
  hardening, mock vs real model, JSON-first output.
- `question_validation/` — grounding score, duplicate detection, basic
  hallucination flags.

**IT Security**
- `security/` — bcrypt, JWT, ownership checks.
- `document_processing/` — magic-byte validation, size limits, path-traversal
  prevention.
- `moodle_export/` — safe XML (no string concatenation).
- `tests/test_api_workflow.py`, `test_document_processing.py` — the security tests.
- [`SECURITY.md`](SECURITY.md) — the whole threat model.

**Database Engineering**
- `models.py` — normalized schema, FKs, indexes, state field, provenance.
- `alembic/` — migrations.
- `database.py` — session management, parameterized access.

**Software Architecture / Testing / Docker**
- Module boundaries (`ARCHITECTURE.md`), the typed-model-in-the-middle pattern.
- `tests/` — unit + integration tests; mock provider for determinism.
- `Dockerfile`s + `docker-compose.yml` — reproducible local stack.

---

## 7. Suggested reading order in the code

1. `schemas/question.py` — the domain model and its rules.
2. `ai_generation/mock_provider.py` + `service.py` — how questions are made.
3. `question_validation/validator.py` — grounding + duplicates.
4. `moodle_export/exporter.py` — JSON → XML.
5. `models.py` — how it is stored.
6. `api/` — how it is all exposed over HTTP.
7. `tests/` — read the tests to see every piece exercised.
