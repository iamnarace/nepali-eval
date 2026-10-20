# Native-speaker review guide

**Status today: no task in `tasks/seed_v0.jsonl` has been reviewed by a native speaker.** The tasks were written by the
maintainers with AI assistance. Automated checks (`nepali-eval lint`) catch mechanical problems only — they cannot tell
whether Nepali is correct, natural, or culturally appropriate. A task becomes `reviewed` only through the process below.

## What automated checks do and do not cover
| Covered by `nepali-eval lint` (heuristics) | NOT covered — needs a human |
|---|---|
| Phone-number-like digits, zero-width characters, mixed digit systems | Spelling and grammar correctness |
| Reference script share, danda vs full stop, space before sentence mark | Naturalness, tone, and register (तिमी / तपाईं / तँ) |
| Duplicate references after normalisation, single-reference tasks | Whether the *listed* references are complete (valid paraphrases, regional wording) |
| Informal-form markers without a register tag | Cultural context, ambiguity, offensive or sensitive content |

## Known risks in the current seed set (for reviewers to check)
1. **Tense/aspect ambiguity:** `जान्छु`, `आउँछु` can be habitual or future; references list several readings.
2. **Register:** `Timro naam ke ho?` (rom-002) is informal; decide whether a formal variant should be accepted.
3. **Spelling variants:** काठमाडौं / काठमाडौँ / काठमाण्डौ; स्कुल / स्कूल; भेटौं / भेटौँ. Which are standard for this task?
4. **Loanwords:** `बसपार्क` vs `बस स्टेशन` vs `बस स्टप`; `office`, `laptop` in code-mixed tasks.
5. **Short sentences:** chrF on 4–6-word sentences is noisy; many tasks have only one or two references.
6. **Digits and numbers:** answers like `७` / `सात` (qa-002) are equivalent; check the accepted forms.
7. **Romanised input:** Romanisation is not standardised; many valid spellings exist for each word.

## How to review
```bash
nepali-eval export-review tasks/seed_v0.jsonl --out review.csv     # opens in Excel/LibreOffice/Sheets (UTF-8)
# reviewers fill: reviewer, reviewer_attests_fluent_nepali (yes), prompt_natural_and_correct, references_correct,
# register, extra_valid_references (separate with " | "), region_or_dialect_notes, verdict (approve/revise/reject), comments
nepali-eval apply-review tasks/seed_v0.jsonl review.csv --out tasks/seed_v0.reviewed.jsonl
nepali-eval lint tasks/seed_v0.reviewed.jsonl
```
- `approve` requires a reviewer name, `reviewer_attests_fluent_nepali = yes` and `references_correct = yes`; the task
  becomes `reviewed` and the name is stored in `reviewers`.
- `revise` appends your extra references and keeps the task `unreviewed`.
- `reject` marks it `disputed`; disagreements are kept, not deleted.
- `apply-review` writes a **new** file; open a pull request with the result so the change is visible.

`reviewed` records a *claim by a named person*; the tool cannot verify anyone's fluency. Projects that rely on these
tasks should publish who may review and how many independent reviewers are required (the tool does not require two).
