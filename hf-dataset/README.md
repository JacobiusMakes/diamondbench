---
license: mit
language:
- en
pretty_name: DiamondBench
size_categories:
- n<1K
task_categories:
- question-answering
tags:
- diamonds
- gemology
- lab-grown-diamonds
- benchmark
- evaluation
- ai-evaluation
- question-answering-benchmark
configs:
- config_name: default
  data_files: questions.jsonl
---

# DiamondBench

47 buyer-phrased diamond and gemology questions, each with a public, sourced answer
key and a deterministic grading rule, for measuring how accurately AI answer engines
respond before a shopper spends real money. Maintained by [Stienhardt & Stones](https://stienhardt.com/?utm_source=huggingface&utm_medium=benchmark_dataset&utm_campaign=diamondbench),
a New York lab-grown diamond jeweler. The runner, the grader, every raw model answer,
and the dated scoreboards live in the
[DiamondBench repository](https://github.com/JacobiusMakes/diamondbench) (MIT).

Live Hub id: `JacobiusMakes/diamondbench`, the account that also hosts the companion
[diamond-gemology-encyclopedia](https://huggingface.co/datasets/JacobiusMakes/diamond-gemology-encyclopedia)
dataset.

## What it measures

Whether an AI answer engine gets the gemology right when a shopper asks. The questions
are phrased the way buyers phrase them ("Do lab grown diamonds fade?", "Does carat mean
size?", "How do I verify a grading report?"), and the answer key grades verifiable
gemology only, never brand preference. The correct answers and sources come from
independent authorities: GIA and IGI publications and grading systems, the U.S. FTC
Jewelry Guides (2018 revision), the Mohs scale, Tolkowsky's Diamond Design (1919),
Smithsonian and Royal Collection Trust records, and documented advertising history
(De Beers / N.W. Ayer, De Beers / J. Walter Thompson).

| Category | Questions | Examples |
| --- | --- | --- |
| Definitions | 6 | What is a diamond made of? Is cubic zirconia a diamond? |
| Verification and trust | 7 | How do I verify a grading report? What does a diamond tester prove? |
| Lab Grown science | 7 | Do Lab Grown Diamonds fade? How are they made? |
| The 4Cs | 7 | Does carat mean size? Which C matters most? |
| Shapes | 8 | Round brilliant, oval, emerald, princess, the Dutch Marquise |
| Care | 5 | Cleaning, prong checks, ultrasonic cleaners, resizing, insurance |
| History and myths | 7 | The months-of-salary rule, vena amoris, diamonds from coal |

Fairness rules baked into the key:

- The two Dutch Marquise questions grade objective geometry only. A Dutch Marquise is an
  elongated hexagonal cut diamond: pointed ends, straight angled sides, not a navette.
  The term is a trade name, not an officially recognized gemological shape, and an IGI
  report describes the geometry as Hexagonal Modified Brilliant (report LG799689559,
  2026-05-09). It is cut for brilliance; the Elongated Hexagon is the step cut that
  shares the outline. No origin story, house framing, or length-to-width range is
  graded. The open geometry specification is at
  [dutch-marquise-spec](https://github.com/JacobiusMakes/dutch-marquise-spec)
  (concept DOI [10.5281/zenodo.21938899](https://doi.org/10.5281/zenodo.21938899),
  v1.0.2 DOI 10.5281/zenodo.22261016, CC BY 4.0).
- No question's correct answer is a marketing claim, and answers that coach distrust of
  sellers are not rewarded anywhere.
- A diamond is a love piece, not an investment. The investment question grades whether
  the model says so.

## Fields

One JSON object per line, one line per question.

| field | type | description |
| --- | --- | --- |
| `id` | string | stable question id, for example `shape-dutch-marquise` |
| `category` | string | one of the seven categories above |
| `question` | string | the buyer-phrased question. The runner appends " Answer as you would for a shopper." |
| `must_include` | list of list of string | the key facts a correct answer contains. Each inner list is one slot; any one string in the list satisfies the slot |
| `must_not_include` | list of string | the common wrong claims for that question; asserting one fails the answer |
| `correct_answer` | string | one to three sentences stating the correct answer plainly |
| `sources` | list of objects | `{claim, source, date}` backing the correct answer |

In the repository's `questions.json` a `must_include` slot is either a plain string or
`{"any": [synonyms]}`. Arrow cannot infer a column that mixes strings and structs, so
this file stores every slot as a list of strings (a plain string becomes a one-element
list). `hf-dataset/build_jsonl.py` performs that one transformation and nothing else;
`harness/diamondbench_metric.py` converts the lists back before grading.

## The grading rule in plain words

The model's full raw answer is graded case-insensitively:

1. **Fail** if the answer asserts any `must_not_include` phrase.
2. **Pass** if no wrong claim is asserted and every `must_include` slot is satisfied.
3. **Partial** if no wrong claim is asserted but at least one slot is missing. The
   answer is incomplete rather than wrong.

Two mechanical details make the rule sturdier, and both are deterministic. A token
shorter than four characters ("IGI", "10", "cut") only matches when it stands alone, so
"IGI" does not match "original" and "10" does not match "100". And a wrong claim only
counts as asserted when it appears in a sentence that carries no negation or contrast
marker ("not", "myth", "unlike", "rather than", "avoid", "misconception", and so on); a
bulleted or numbered line inherits negation from the block of prose that leads into it,
so "What to avoid:" followed by "bleach" is a debunk, not an assertion. Sentences split
on `.!?;:` and newlines. `python bench.py --selftest` verifies the grader against canned
answers with no API key.

Overall accuracy counts full passes only, which is a strict bar. There is no judge model.

## Calibration disclosure

Keyword grading is only as good as its synonym lists, so the answer key has been
calibrated twice, both times against stored raw answers that were never edited, and
both times disclosed.

**Initial-run calibration (v1.0, Gemini, 2026-07-13).** Every initial miss was checked
by hand against the stored raw answer. Five synonym slots that under-credited
substantively correct answers were broadened, and the negation guard learned past-tense
reporting verbs ("the Romans believed a vein ran to the heart" reports a belief rather
than asserting it). All stored answers were then re-graded deterministically. The
results file for that run discloses the before and after numbers.

**Second-run calibration (v1.1, 2026-09-02).** The second Gemini run's initial scoring
pass reported 85.1%. Auditing every miss against the raw answers showed that five of the
seven misses were grader misfires, and the rules changed in three places:

- Assertion-form keys. A `must_not_include` phrase must be the assertion itself, never a
  bare noun phrase that also appears in true sentences. "completely flawless" (which
  matched "completely flawless diamonds are rare") became "are completely flawless".
- List items inherit their lead-in's negation, as described above, and "steer clear"
  joined the negation markers.
- Three synonym slots widened for correct answers in different words: "does not tell
  you" (thermal tester), "no universal rule" and "marketing strategy" (months' salary),
  "all your fingers" and "isn't one special vein" (vena amoris).

Every change was re-applied to the July run with `regrade.py`; its score did not move
(45 pass / 2 partial / 0 fail), which is the check that a rule change is a correction
and not a loosening. Grader version string: `2026-09-02`. Future rule changes follow the
same pattern: versioned in the repository, disclosed in the results, never applied
silently.

## Results so far

| Run | Model | Pass | Partial | Fail | Accuracy |
| --- | --- | --- | --- | --- | --- |
| 2026-07-13 | gemini-2.5-flash, Google Search grounding | 45 | 2 | 0 | 95.7% |
| 2026-09-02 | gemini-2.5-flash, Google Search grounding | 45 | 2 | 0 | 95.7% |

Both runs are graded under grader version 2026-09-02. No answer in either run asserted a
wrong claim. The two partials are the same two questions in both runs:

- `myth-three-stone`: the "past, present, future" meaning of a three-stone ring was
  given without its origin, a De Beers marketing campaign developed by J. Walter
  Thompson around the year 2000.
- `c4-fluorescence`: the fluorescence answer reached the right conclusion (usually not
  a defect, can make some stones look whiter) without the evidence, the GIA study in
  Gems and Gemology (Winter 1997) that found no systematic effect on appearance for the
  average observer.

Seven weeks apart, the gemology was right and the provenance was still missing. A
search-grounded model's answers change week to week, so every scoreboard is a dated
snapshot, not a permanent grade of a vendor. The full readout, with the raw answers, is
`results/RESULTS-2026-09-02.md` in the repository.

## Reproduce

Standard library Python 3.8+, no dependencies.

```
git clone https://github.com/JacobiusMakes/diamondbench
cd diamondbench
python bench.py --selftest                       # grader check, no key needed
python bench.py --provider gemini                # live run, needs GEMINI_API_KEY
python regrade.py results/gemini-2026-09-02.json # re-derive any stored run under the current rules
python hf-dataset/build_jsonl.py                 # regenerate questions.jsonl from questions.json
```

`bench.py` writes `results/<provider>-<date>.json` with per-question verdicts, the
missing slots, each asserted wrong claim with its sentence, and the complete raw answer.
`regrade.py` re-grades a stored file without re-querying any model; raw answers are
never modified. An `lm-evaluation-harness` task that reuses the same grader is in the
repository's `harness/` folder.

Load the questions:

```python
from datasets import load_dataset
ds = load_dataset("JacobiusMakes/diamondbench")
row = ds["train"][0]
print(row["question"], row["correct_answer"])
```

## Honest limits

Deterministic keyword grading cannot read intent: a wrong claim split across sentences
("Some say they fade. That is false.") is scored by the sentence containing the phrase,
and a contrastive sentence with no marker word can be miscounted. Published results
spot-check every fail against the raw answer and note any misfire rather than hide it.
47 questions cannot cover all of gemology; well-sourced additions in underrepresented
areas are welcome as pull requests.

## Citation

```bibtex
@misc{diamondbench2026,
  title  = {DiamondBench: an open benchmark of AI answer-engine accuracy on diamond and gemology questions},
  author = {{Stienhardt}},
  year   = {2026},
  url    = {https://github.com/JacobiusMakes/diamondbench},
  note   = {Answer key v1.1, grader version 2026-09-02. MIT license.}
}
```

A `CITATION.cff` ships alongside this card.

## License

MIT. Copyright (c) 2026 Stienhardt.
