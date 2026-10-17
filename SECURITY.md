# Security

Security is part of the architecture, not an afterthought. This document lists
the threat model, the controls implemented, and — honestly — the limits.

## Trust boundaries

- **Trusted:** the application's own code and configuration.
- **Untrusted:** everything that enters from outside — HTTP requests, uploaded
  documents, and **AI output**. Uploaded documents are treated as data only and
  are never executed; instructions embedded inside a document must never
  override the application's instructions.

## Controls implemented

### Authentication & authorization
- Passwords hashed with **bcrypt** (passlib); plaintext is never stored or logged.
- Stateless **JWT** access tokens (HS256), signed with `SECRET_KEY` from the
  environment, with an expiry.
- **Row-level authorization on the backend**: every document/question carries an
  `owner_id`, and each route checks it. Another user's resource returns `404`
  (existence is not leaked). Frontend route guards are convenience only and are
  never trusted on their own.

### File upload security (`document_processing`)
- Extension allow-list (`.pdf`, `.txt`, `.docx`) **and** magic-byte check of the
  real content; a mismatch is rejected (a renamed `.exe` cannot pass).
- Upload **size limit** (default 10 MB) enforced before writing to disk.
- **Path traversal prevented**: the original filename is never used to build the
  path. A random name is generated and the resolved path is verified to stay
  inside the upload directory.
- Corrupt/unsupported files raise a clear error instead of crashing.
- Documents are parsed for text only; content is never executed.

### Injection
- **SQL injection:** all DB access goes through SQLAlchemy ORM/Core with
  parameterized queries. No string-built SQL anywhere.
- **XML injection:** XML is built with `lxml` element trees (CDATA + proper
  escaping), never string concatenation. A test feeds `<`, `>`, `&` and umlauts
  through and asserts no stray elements are created.

### AI / prompt-injection resistance (`ai_generation`)
- The lecture material is wrapped in a delimited block and the system prompt
  states it is **data, not instructions**, and that embedded commands must be
  ignored.
- The number of questions is **hard-capped** server-side regardless of what the
  request or a malicious document asks for.
- **Structured-output validation is the real safety net**: whatever the model
  returns is parsed into a strict schema and rejected if malformed. A model that
  is talked into misbehaving still cannot produce anything the app accepts.
- **Mandatory human approval**: no question can be exported without an
  instructor approving it; the AI never publishes anything.
- **Safe model-failure handling**: provider errors are wrapped and surfaced as a
  clean `502`, never as a stack trace or leaked key.

### Secrets, config, errors, logging
- All secrets/config come from environment variables (`.env`), never hard-coded.
- The API key is read from settings and **never logged**.
- A global exception handler returns a generic `500` to the client and logs the
  detail server-side — no stack traces or secrets reach the user.
- Logs record actions (user id, document/question ids) but not secrets.

### Transport / deployment notes
- CORS is restricted to the configured frontend origins.
- Backend container runs as a **non-root** user.
- In production: set a strong `SECRET_KEY`, run behind HTTPS, and set
  `ENVIRONMENT=production`.

## Security tests (in `backend/tests`)

Executed and passing:

- Unauthorized access to another user's document and generation → `404`.
- Protected routes without a token → `401`.
- Malicious upload (executable + disallowed extension) → `400`.
- Oversized upload (> 10 MB) → `400`.
- Content/extension mismatch and binary-as-text → rejected.
- Path-traversal filename is neutralized (stored under a random name).
- Prompt-injection document cannot force 999 questions.
- XML special-character / injection content is escaped, not interpreted.
- Export blocked until approval (`409`).
- Invalid AI/edited output rejected by schema validation.

## Dependency vulnerability checks

Dependencies are pinned (`backend/requirements.txt`, `frontend/package.json`).
Recommended checks (not run automatically here):

```bash
pip install pip-audit && pip-audit -r backend/requirements.txt
cd frontend && npm audit
```

## Honest limitations

- **Prompt injection cannot be fully prevented.** The controls above reduce risk;
  mandatory human approval and output validation are what keep it safe.
- The grounding/duplicate/hallucination checks are **simple heuristics**, meant
  to flag questions for the reviewer, not to guarantee correctness.
- Do **not** send real university documents to an external AI provider without
  authorization; use the offline `mock` provider during development.
