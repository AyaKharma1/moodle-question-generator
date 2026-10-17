# Future Moodle Integration

The app is deliberately standalone today. This note records how a real Moodle
integration could be added **later**, and the conditions that must be met first.

## Do not build this yet

Direct Moodle integration must **not** be implemented until the following are
confirmed with the responsible administrator (Ruhr-Universität Bochum hosts the
Moodle used by Hochschule Bochum):

- the exact Moodle **version** and its question-bank API capabilities,
- **permission** to integrate and against which (test) instance,
- the **web-service** functions enabled and the authentication method,
- university data-protection requirements.

Do **not** request or use production Moodle credentials, and do not invent API
capabilities that have not been verified.

## Where it would plug in

The current pipeline already ends at a clean boundary: a set of **approved**
questions. A future `moodle_integration` module would consume exactly that, so
nothing in the AI pipeline, validation, or exporter needs to change.

```
... → Review & Approve ─┬─▶ moodle_export (XML file)      ← exists today
                        └─▶ moodle_integration (API push) ← future, same gate
```

## Likely approach (Moodle Web Services)

- Enable Moodle **Web Services** (REST), create a dedicated service + token on a
  **test** instance.
- Store the token and base URL as environment config (never hard-coded), exactly
  like `AI_API_KEY` today.
- Add a small client that calls the relevant web-service functions to create a
  question category and import questions, reusing the existing Moodle XML as the
  payload where the API accepts it.
- Keep the **approval gate**: only approved questions are eligible, and a human
  triggers the push — the AI never publishes automatically.
- Record each push in `export_history` (extend it with a target + remote id) for
  traceability.

## Candidate future capabilities

- Moodle API integration (question import).
- Moodle authentication integration (SSO / OAuth) instead of local accounts.
- Question-bank synchronization (track which app questions map to which Moodle
  questions).
- Course-specific question management.

## Design properties that make this feasible

- Clear module boundaries and a typed question model.
- Environment-based secrets already in place.
- Ownership/authorization and an audit trail already in place.
- Export already modeled as an explicit, logged action behind human approval.
