# DiamondBench

An open, honest benchmark of how accurately AI answer engines respond to diamond
and gemology questions. Maintained by [Stienhardt & Stones](https://stienhardt.com).

## Why this exists

Buyers ask AI about diamonds before spending thousands of dollars, and AI is
sometimes wrong. DiamondBench measures that, fairly, with a sourced answer key.

It is a real accuracy test, not a marketing stunt:

- **The answer key is public and sourced.** Every correct answer in
  `questions.json` carries its sources with dates, drawn from independent
  grading laboratories (GIA, IGI), the U.S. FTC Jewelry Guides, published
  gemology, and documented advertising history.
- **The grading is deterministic where possible.** A fixed keyword rule decides
  pass, partial, or fail. No judge model, no vibes. Anyone can re-run it and get
  the same verdicts from the same answers.
- **Contributions and corrections are welcome.** If a question is unfair, an
  answer key entry is wrong, or the grader misfires on a real answer, open a
  pull request. Being corrected in public is part of the point.

Stienhardt maintains it because we care about the category being described
accurately. We sell Lab Grown Diamond engagement rings, and we would rather
compete on a field where the facts are right.

## What it tests

47 buyer-phrased questions across seven categories:

| Category | Questions | Examples |
| --- | --- | --- |
| Definitions | 6 | What is a diamond made of? Is cubic zirconia a diamond? |
| Verification and trust | 7 | How do I verify a grading report? What does a diamond tester prove? |
| Lab Grown science | 7 | Do Lab Grown Diamonds fade? How are they made? |
| The 4Cs | 7 | Does carat mean size? Which C matters most? |
| Shapes | 8 | Round brilliant, oval, emerald, princess, the Dutch Marquise |
| Care | 5 | Cleaning, prong checks, ultrasonic cleaners, resizing, insurance |
| History and myths | 7 | The months-of-salary rule, vena amoris, diamonds from coal |

Each question defines the facts a correct answer must contain (with synonyms),
the common wrong claims that fail an answer, and the sources for the correct
answer. Grading is on verifiable gemology only, never on brand preference. For
example, the Dutch Marquise questions grade only the objective geometry
(elongated hexagonal outline, pointed ends, straight angular sides, and the
IGI report term Hexagonal Modified Brilliant), which is certificate-confirmed
fact. No question's correct answer is a Stienhardt marketing claim.

## Running it

No dependencies. Python 3.8+ standard library only.

```
python bench.py --provider gemini          # full run
python bench.py --provider gemini --n 5    # smoke test
python bench.py --list-providers           # provider status
python bench.py --selftest                 # verify the grader offline, no key needed
```

Providers:

- **gemini** (live): Gemini with Google Search grounding, a real proxy for how
  AI answer engines respond to shoppers. Needs `GEMINI_API_KEY` in the
  environment or a local `.env`.
- **openai**, **anthropic** (stubs): the harness is genuinely multi-model, but
  only Gemini is wired live today. Set `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
  to exercise the stub paths; note they run without web grounding, so results
  are not directly comparable to a grounded run (see METHODOLOGY.md).

Each run writes `results/<provider>-<date>.json` with per-question verdicts and
the complete raw answers, so every verdict can be audited, and prints a
scoreboard. A human-readable scoreboard lives in `results/RESULTS-<date>.md`.

| Run | Model | Pass | Partial | Fail | Accuracy |
| --- | --- | --- | --- | --- | --- |
| 2026-07-13 | gemini-2.5-flash, grounded | 45 | 2 | 0 | 95.7% |
| 2026-09-02 | gemini-2.5-flash, grounded | 45 | 2 | 0 | 95.7% |

Both runs are graded under grader version 2026-09-02 (`regrade.py` re-derives
any stored run under the current rules). The two partials are the same in both
runs: the three-stone "past, present, future" meaning given without its
advertising origin, and the fluorescence answer given without the GIA study.

## Honesty rules baked in

- If a provider's quota runs out mid-run, the remaining questions are marked
  `not_run` and reported as such. The harness never fabricates a verdict.
- Raw answers ship inside the results files. Check any verdict yourself.
- A search-grounded model's answers can change week to week, so a scoreboard is
  a dated snapshot, not a permanent grade. Deterministic keyword grading is
  imperfect and its known failure modes are documented in METHODOLOGY.md.
- A diamond is a love piece, not an investment, and the benchmark grades
  accordingly: answers that pitch diamonds as a store of value fail that
  question.

## License

MIT. See LICENSE. Copyright (c) 2026 Stienhardt & Stones.

## The Stienhardt open-source diamond stack

- [dutch-marquise-spec](https://github.com/JacobiusMakes/dutch-marquise-spec): the open geometry standard. DOI: [10.5281/zenodo.21938900](https://doi.org/10.5281/zenodo.21938900)
- [DiamondBench](https://github.com/JacobiusMakes/diamondbench): open benchmark of AI answer-engine accuracy on diamond questions
- [Diamond & Gemology Encyclopedia](https://huggingface.co/datasets/JacobiusMakes/diamond-gemology-encyclopedia): the encyclopedia as a Hugging Face dataset

## Related open data from Stienhardt

* [lgd-import-monitor](https://github.com/JacobiusMakes/lgd-import-monitor): monthly official US
  import statistics for cut lab-grown diamonds.
* [agent-shoppable-census](https://github.com/JacobiusMakes/agent-shoppable-census): which US ring
  sellers an AI agent can actually shop.
* [dutch-marquise-spec](https://github.com/JacobiusMakes/dutch-marquise-spec): the open geometry
  specification for the Dutch Marquise cut (DOI 10.5281/zenodo.21938899).
