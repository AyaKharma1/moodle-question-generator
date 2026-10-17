# Moodle Import Guide (manual test procedure)

> **Honesty first.** This application produces XML that follows the documented
> Moodle "quiz" question format and is checked for well-formedness. That is
> **not** proof of Moodle compatibility. The only proof is a successful import
> into a real Moodle instance. This guide describes how to do that test.

## What the exporter produces

- A single UTF-8 `<quiz>` XML document containing one `<question>` per question.
- Supported types: `multichoice`, `truefalse`, `shortanswer`.
- German umlauts preserved (UTF-8); special characters escaped via CDATA.

## Set up a Moodle test environment

Use a **test** instance — never a production server, and never production
credentials.

Fastest option (official Docker image, Bitnami):

```bash
docker run -d --name moodle-test -p 8090:8080 \
  -e MOODLE_USERNAME=admin \
  -e MOODLE_PASSWORD=Admin123! \
  -e MOODLE_EMAIL=admin@example.com \
  bitnami/moodle:latest
```

Wait a few minutes for first-time setup, then open <http://localhost:8090> and
log in as `admin`.

(Alternatively use a disposable sandbox such as a local MoodleCloud/"Moodle
Sandbox" test site. Do not use your university's production Moodle.)

## Import procedure

1. In the app: **Upload → Generate → Review → approve some questions → Export**.
   Save the downloaded `.xml` file.
2. In Moodle, create or open a course.
3. Go to: **Course → More → Question bank → Import**
   (or *Site administration → Question bank → Import*).
4. **File format:** choose **Moodle XML format**.
5. Optionally pick a category.
6. Upload the `.xml` file and click **Import**.
7. Moodle shows "Parsing questions …" and lists the imported questions.
8. Open **Question bank** and verify:
   - All questions appear with the right type.
   - Multiple-choice answers and the correct option(s) are right.
   - True/false shows the correct value.
   - Short-answer accepted answers are present.
   - Umlauts/special characters display correctly.
9. Add the questions to a quiz and **preview** one of each type to confirm
   grading works.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Error importing questions" | Wrong format selected | Choose **Moodle XML format**, not GIFT/Aiken |
| Garbled umlauts | File opened/re-saved in a non-UTF-8 editor | Import the file as exported; don't re-encode |
| Multichoice credit wrong | Multiple correct answers with odd weights | This app only emits equal weights for 2–5 correct answers |
| True/false not accepted | Edited option text away from true/false | Keep true/false (or wahr/falsch) wording |

## Record your result

When you run this test, note the Moodle version and the outcome, e.g.:

```
Moodle 4.x — imported 6 questions (3 MC, 2 T/F, 1 SA) — all previewed and graded correctly.
```

Only after a successful manual import should you describe the output as
"Moodle-compatible" for that Moodle version.
