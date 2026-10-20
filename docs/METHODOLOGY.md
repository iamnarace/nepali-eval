# Methodology and limitations

## What is measured
Each task has a `prompt`, one or more acceptable `references`, and a list of `metrics`:

| metric | meaning | range |
|---|---|---|
| `exact` | normalised prediction equals any normalised reference (punctuation ignored) | 0/1 |
| `chrf` / `chrfpp` | best sentence-level chrF / chrF++ (β=2, char order 6, word order 0/2) over all references | 0-100 |
| `numbers` | numbers in the prediction match those in some reference (२०८२ == 2082; `1,500` == `1500`) | 0/1 |
| `devanagari` | share of letters in Devanagari script (reported, not pass/fail) | 0-1 |

`checks` are pass/fail constraints reported as `checks_pass_rate`: `min_devanagari_ratio`,
`must_include`, `must_not_include`.

## Normalisation (what is *not* penalised)
Unicode NFC; zero-width joiner/non-joiner; Devanagari vs ASCII digits; danda vs full stop;
letter case; whitespace. Genuine spelling variants (e.g. काठमाडौं / काठमाडौँ / काठमाण्डौ) are **not**
merged automatically — list them as separate references so the decision is visible and reviewable.
This is how valid variation is kept from being scored as an error without hiding linguistic choices.

## chrF correctness
`metrics.chrf` is an independent implementation of the sacrebleu algorithm; `tests/test_metrics.py`
asserts agreement with sacrebleu to 1e-6 on fixed examples (corpus and sentence level, chrF and chrF++).
That verifies the *arithmetic*, not that chrF is a good metric for Nepali.

## Limitations (please read)
- **The seed tasks are not a benchmark.** 24 original tasks, unreviewed, mostly short, standard-register
  sentences. Results on them say nothing general about any model.
- chrF/exact match reward overlap with references; a correct paraphrase absent from the references is
  scored low. Add references and use human review (`review.csv` → `nepali-eval human`).
- `numbers` is trivially satisfied by an adapter that echoes a prompt containing the number; read it
  next to the other metrics.
- Script share cannot tell English from Romanised Nepali (both are Latin).
- Regional/dialectal coverage is unknown; no claim is made of representing all Nepali speakers.
- Using a hosted model (`openai` adapter) may cost money and sends prompts to that provider.

## Human review workflow
1. `nepali-eval run ...` writes `review.csv`.
2. Reviewers fill `human_score_0_to_5`, `reviewer`, `notes` (suggested rubric: 5 = fully correct and
   natural; 3 = understandable with errors; 0 = wrong/unrelated; adapt and document your rubric).
3. `nepali-eval human review.csv` prints the mean overall and per reviewer. Inter-annotator agreement
   is not computed yet (see roadmap).
