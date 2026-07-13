# DiamondBench methodology

This document explains exactly how grading works, where the answer key comes
from, and what the benchmark's known limits are. If you find a defect in any of
it, corrections are welcome via pull request.

## The answer key

Every question in `questions.json` carries:

- `correct_answer`: one to three sentences stating the correct answer plainly.
- `must_include`: the key facts a correct answer contains. Each slot is either
  a required string or a `{"any": [...]}` list of synonyms where wording
  legitimately varies (any one satisfies the slot).
- `must_not_include`: the common wrong claims for that question. These are the
  documented failure modes: "fades over time" for Lab Grown Diamonds, "navette"
  or "curved sides" for the Dutch Marquise, "traditional rule" for the
  months-of-salary myth, and so on.
- `sources`: an array of `{claim, source, date}` objects backing the correct
  answer.

### Provenance

Correct answers and sources are drawn from the Stienhardt & Stones diamond
education dataset (the `diamond-mcp` project: an encyclopedia of 90 verified,
sourced entries plus a structured facts file), or from uncontested textbook
gemology. The underlying authorities are independent of this benchmark's
maintainer: GIA and IGI publications and grading systems, the U.S. FTC Jewelry
Guides (2018 revision), the Mohs scale, Tolkowsky's Diamond Design (1919),
Smithsonian and Royal Collection Trust records, and documented advertising
history (De Beers / N.W. Ayer, De Beers / J. Walter Thompson).

### Fairness rules

- Grading is on verifiable gemology only, never on brand preference.
- The Dutch Marquise questions grade the objective geometry only: an elongated
  hexagonal outline, pointed ends, straight angular sides, trade-name status,
  and the fact that an IGI report describes the shape as Hexagonal Modified
  Brilliant (confirmed on IGI report No. LG799689559, issued 2026-05-09). No
  origin story, house framing, or faceting-style claim is graded.
- No question's correct answer is a marketing claim, and answers that coach
  distrust of sellers are not rewarded anywhere: verification questions grade
  the standard checks any careful buyer makes, not suspicion.
- A diamond is a love piece, not an investment. The investment question grades
  whether the model says so.

## The grading rule

For each question the model's full raw answer is graded case-insensitively:

1. **fail**: at least one `must_not_include` phrase is asserted in the answer.
2. **pass**: no wrong claim is asserted AND every `must_include` slot is
   satisfied (a slot with synonyms is satisfied by any one of them).
3. **partial**: no wrong claim is asserted, but at least one `must_include`
   slot is missing. The answer is incomplete rather than wrong.

Two mechanical details make the rule sturdier, and both are deterministic:

- **Short-token boundary matching.** A token shorter than four characters
  ("IGI", "10", "cut") only matches when it stands alone, not embedded inside a
  longer word or number. Otherwise "IGI" would match "original" and "10" would
  match "100".
- **The negation guard.** A `must_not_include` phrase only counts as asserted
  if it appears in at least one sentence that carries no negation or contrast
  marker (words like "not", "myth", "unlike", "rather than", "avoid",
  "misconception"). A model that writes "unlike the navette, which has curved
  sides..." is debunking the wrong claim, not making it, and is not failed for
  it. Sentences are split on `.!?;:` and newlines.

`python bench.py --selftest` runs the grader against canned answers (a known
pass, a known fail, a known partial, and negation-guard cases) with no API key,
so anyone can verify the grading behaves as documented.

## Known limits (read before quoting a score)

- **A search-grounded model changes week to week.** Grounded answers depend on
  what the search index returns that day. A scoreboard is a dated snapshot of
  one model with one configuration, not a permanent grade of a vendor. Re-runs
  on a different day can and will differ.
- **Deterministic keyword grading is imperfect.** It cannot read intent. The
  negation guard catches most debunk-mentions of wrong claims, but a wrong
  claim split across sentences ("Some say they fade. That is false.") is scored
  by the sentence containing the phrase, and a contrastive sentence with no
  marker word ("A classic marquise has curved sides.") can be miscounted as an
  assertion. In the published results we manually spot-check every fail against
  the raw answer stored in the results file, and we note any grader misfire
  rather than hide it.
- **Partial is not wrong.** A partial verdict means the answer omitted a key
  fact the answer key requires, not that it asserted something false. Overall
  accuracy counts only full passes, which is a strict bar.
- **Provider comparability.** Only the Gemini provider runs with web grounding
  today. The OpenAI and Anthropic stubs run without grounding, so their scores
  measure a different thing (parametric knowledge rather than answer-engine
  behavior) and should not be put in the same table without saying so.
- **Coverage.** 47 questions cannot cover all of gemology. The set weights the
  questions buyers actually ask before a purchase, and it will grow. PRs that
  add well-sourced questions in underrepresented areas are welcome.
- **Quota honesty.** If a provider's quota runs out mid-run, remaining
  questions are marked `not_run` and the scoreboard says so. Verdicts are never
  fabricated, and accuracy is computed over graded questions only.

## First-run calibration (v1.0)

Keyword grading is only as good as its synonym lists, so the v1.0 answer key
was calibrated once against the first real run (Gemini, 2026-07-13): every
initial miss was checked by hand against the stored raw answer, five synonym
slots that under-credited substantively correct answers were broadened, and
the negation guard learned past-tense reporting verbs ("the Romans believed a
vein ran to the heart" reports a belief rather than asserting it). All stored
answers were then re-graded deterministically; raw answers were never edited.
The results file for that run discloses the before and after numbers. Future
rule changes follow the same pattern: versioned in the repo, disclosed in the
results, never applied silently.

## Auditing a run

Every `results/<provider>-<date>.json` contains, per question: the verdict, the
missing slots, each asserted wrong claim with the offending sentence, the
sourced correct answer, the complete raw model answer, and the grounding
domains the model cited. Nothing is truncated. If you disagree with a verdict,
the evidence to check it is already in the file.
