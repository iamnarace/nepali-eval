# Contributing

Thank you for helping make Nepali AI measurable. Two kinds of contribution matter most, and
**the most valuable one needs no programming: reading tasks and correcting them.**

## 1. Review or correct tasks (no code needed)
Every seed task is `review_status: "unreviewed"` — written by the maintainers with AI
assistance and **never checked by a native speaker**. If you read Nepali:

1. Open `tasks/seed_v0.jsonl` and find a task whose reference is unnatural, wrong, or
   missing a valid alternative (regional wording, spelling variant, formal/informal register).
2. Open an issue ("Task correction") or a pull request that edits `references` /
   `notes`. Valid variants belong in `references` — the score uses the *best* reference.
3. A reviewer who has read a task may set `"review_status": "reviewed"` and add their name
   or handle to `notes`. Mark disagreements as `"disputed"` rather than deleting them.

Do not paste text you do not have the right to share. Task text must be original or under a
licence compatible with CC0 / Apache-2.0, with the source named in `source`.

## 2. Code
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && python -m pytest -q
```
- Keep the core dependency-free (standard library only); `sacrebleu` is a dev-only cross-check.
- New metrics need a unit test with hand-checkable examples, and — if a reference
  implementation exists — a parity test against it.
- Normalisation changes must explain why a difference is *representational* (not a real
  spelling or meaning difference) and add a test for both sides.

## Good first issues (suggested)
- Add Nepali-language error messages to the CLI (needs native-speaker review).
- More `must_include` / `must_not_include` check examples in `docs/METHODOLOGY.md`.
- A `tasks/` schema JSON file for editor validation.
- An adapter for another local runtime (e.g. a `llama.cpp` server — already OpenAI-compatible, so
  document and test it).

## Reporting problems
Use GitHub issues. For a wrong score include the task id, the prediction, the references, and
the output of `nepali-eval normalize "<text>"`. Do not include private data or secrets.
