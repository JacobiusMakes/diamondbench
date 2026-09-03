# Price staleness track: design

Status on 2026-09-03: design plus offline tooling. No model has been asked any of these
questions yet, and nothing in this folder is a result. The reference CSV holds three
observed readings, four derived points, and clearly labeled placeholder rows.

## Why a second track

DiamondBench grades gemology that does not change: what a diamond is made of, what a
grading report proves, what a Dutch Marquise is. A shopper's other question is "what
does it cost", and that answer changes by the week. Lab-grown prices have fallen far
and fast (context below), so an assistant that repeats a figure from its training data
can be off by a large factor while sounding current. This track measures two things
about the dollar figure an assistant gives: how far it is from a same-day reference, and
how old a reading it matches.

## The twelve shopper questions

Asked with bench.py's wrapper and nothing else: `<question> Answer as you would for a
shopper.` No date hint, no instruction to give a number. Whether the model dates its own
figure, or gives one at all, is part of what is measured. The machine-readable copy is
`questions.json`.

| id | question | reference bucket |
| --- | --- | --- |
| ps-01 | How much does a 1 carat lab-grown diamond cost right now? | 1.0 ct, all shapes, per stone |
| ps-02 | What is the average price of a 2 carat lab-grown diamond today? | 2.0 ct, all shapes, per stone |
| ps-03 | How much should I expect to pay for a 3 carat lab-grown diamond? | 3.0 ct, all shapes, per stone |
| ps-04 | What does a 1.5 carat lab-grown diamond cost? | 1.5 ct, all shapes, per stone |
| ps-05 | How much is a half-carat lab-grown diamond? | 0.5 ct, all shapes, per stone |
| ps-06 | What is a fair price for a 2.5 carat lab-grown diamond? | 2.5 ct, all shapes, per stone |
| ps-07 | How much does a 1 carat round brilliant lab-grown diamond cost? | 1.0 ct, round, per stone |
| ps-08 | How much does a 2 carat oval lab-grown diamond cost? | 2.0 ct, oval, per stone |
| ps-09 | What is the price per carat of a 1 carat lab-grown diamond? | 1.0 ct, all shapes, per carat |
| ps-10 | What is the price range for a 4 carat lab-grown diamond? | 4.0 ct, all shapes, per stone |
| ps-11 | How much is a 0.7 carat lab-grown diamond? | 0.7 ct, all shapes, per stone |
| ps-12 | Have 1 carat lab-grown diamond prices changed in the last six months, and what do they cost now? | 1.0 ct, all shapes, per stone |

The buckets follow the reference source's own carat pages. ps-12 exists to see whether a
model that is asked about change reports the direction and a current figure, or a
figure from before the change.

## Reference source (verified 2026-09-03)

StoneAlgo publishes free, daily-updated lab-grown price indexes.

- Landing page: https://www.stonealgo.com/lab-grown-diamond-prices/ (title "Lab Grown
  Diamond Prices"). The page states: "We update these price indexes daily based on the
  current market prices for lab grown diamonds" and "Our price indexes reflect the
  current retail prices for lab grown diamonds."
- Per-weight pages, for example
  https://www.stonealgo.com/lab-grown-diamond-prices/1-carat-lab-grown-diamond-prices/
  and the same pattern for 2-carat and 3-carat. Pages exist for 0.5, 0.6, 0.7, 0.8, 0.9,
  1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, and 5.0 carat, plus finer weights (1.1, 1.17,
  1.72, 6.5) that surface in search.
- What each per-weight page publishes: the current average price for that weight ("The
  average price of a 1 carat lab grown diamond is currently $544"), the range over the
  last month ("Average prices have ranged from $502 to $555 over the last 1 month"), the
  three- and six-month percent change ("1 carat lab grown diamond prices have fallen
  3.37% in the past 3 months and have fallen 26.39% over the past 6 months"), 1-month,
  3-month, 6-month, and 1-year charts, the listing count behind the index ("based on
  372,643 live diamond prices across the 10 most popular diamond shapes" for 1 ct;
  429,523 for 2 ct), and the grade coverage ("color grades D-K and clarity grades
  FL-SI2"). The data set is described as "live inventory from the world's top jewelers
  and other online jewelers and websites." Shape filters exist for the ten shapes, which
  is what ps-07 and ps-08 use.
- Figures seen on 2026-09-03 (landing page tiles dated 09/01/2026): 1 ct $544 (-1.27% in
  1 month), 2 ct $1,173 (0.0%), 3 ct $1,810 (-1.74%).
- No CSV download and no API were found. The series has to be read from the page or its
  charts, one date at a time, and recorded by hand into the reference CSV with the date
  the page showed. Check StoneAlgo's terms before any automated collection; this track
  assumes manual daily reads.
- Basis ambiguity, to settle on the initial fill: the per-weight pages say "the average
  price of a 2 carat lab grown diamond is currently $1,173", which reads as the price of
  the stone; the landing page calls the figures retail prices, and one reading of it is
  per carat. At 1 ct the two coincide. The CSV carries a `basis` column (`per_stone` or
  `per_carat`), `staleness.py` converts and compares like with like, and the 2 ct and
  3 ct rows are marked UNCONFIRMED until the chart axis label settles it.

Fallback, context only: Edahn Golan's wholesale lab-grown price list as reported by JCK
("Lab-Grown Diamond Wholesale Prices Are in Freefall; Retail Margins May Be Next",
2026-08-10): midstream prices fell 14% year over year in Q1 2026 (a three-carat VVS D
color round at $126 per carat, 30% cheaper than in 2025), fell an average of 13% year
over year in Q2 2026 against a 26% decline for all of 2025, and the wholesale index is
down 96% since he began tracking in 2018. These are wholesale figures, not retail asking
prices, so they cannot be the reference for a shopper question; they are the context
that says why staleness matters. If StoneAlgo stops publishing, the track falls back to
Golan's public headline figures as context, says so in every disclosure, and computes no
overstatement number until a retail reference exists again.

## The two metrics

1. Percent overstatement on the same date.
   `((M - R) / R) * 100`, where M is the assistant's midpoint (rule below) and R is the
   reference value on the prompt date: the latest reference reading dated on or before
   the date the model was asked, in the same carat bucket, shape scope, and basis.
   Negative is understatement. Always reported next to the parsed figures.

2. Months of staleness.
   The age of the most recent reference reading the quoted figure matches. Walk the
   reference series backwards from the prompt date; the nearest reading within the
   tolerance (default 5%) of M gives `staleness = days / 30.44`, rounded to one decimal.
   0.0 means the figure matches the current reading. "Not in series" means no reading in
   the loaded series is within tolerance, and it is reported as those words, never as a
   number. The series must span at least 12 months before a staleness number is quoted;
   until then the field reads "series too short". A figure can match an old reading by
   coincidence, which is why both numbers are always shown together.

Midpoint rule. Parse every dollar figure in the answer after scoping to the lab-grown
clauses (when an answer also prices natural stones, the clauses that mention natural or
mined stones without lab-grown wording are dropped). A stated range gives its midpoint;
a single figure is itself; several figures give the midpoint of the lowest and highest.
Figures the answer labels per carat are converted to the question's basis; unlabeled
figures are assumed to be in the question's basis, and the report says so. An answer
with no dollar figure is recorded as "no figure", which is a finding, not a zero.
Figures under $20 are dropped as incidental (a shipping charge, a cleaning fee).

## Disclosure rules

Every published number carries all of these, in the same file:

- the exact prompt text, wrapper included;
- the date the model was asked and the date of the reference reading it is compared to;
- the model string, the provider, and whether web grounding was on;
- the parsed figures and the midpoint next to the complete raw answer, so anyone can
  re-derive both numbers;
- the reference value, its basis, and its source URL;
- the tool version (`staleness.py` prints it) and the tolerance used;
- the reminder that a search-grounded model's figure can change by the day, so each
  number is a dated snapshot of one configuration.

Two rules have no exceptions. No Stienhardt price appears anywhere in this track: not as
a reference, not as a comparison, not as an example, not in a test string. No Stienhardt
sales volumes either. The track measures assistants against a public retail index and
nothing else.

## Files

- `questions.json`: the twelve questions with their reference buckets.
- `reference/stonealgo-lab-grown.csv`: columns `date, carat, shape, basis, price_usd,
  status, source_url, note`. `status` is `observed` (read from the page on a stated
  date), `derived` (arithmetic from a stated percent change, kept only until a chart
  reading replaces it), or `placeholder` (a slot to fill; no value). `staleness.py` uses
  observed rows by default, includes derived rows only with `--include observed,derived`,
  and never computes against a placeholder.
- `staleness.py`: standard library. Loads the CSV, parses dollar figures from an answer,
  computes both numbers, prints a report or JSON, and runs three synthetic unit tests
  with `python staleness.py --selftest`.

## What is not done

- Fill the reference series (at least twelve months of monthly readings for the 1 ct
  bucket, then the other buckets) from StoneAlgo's charts, after confirming the basis.
- Ask the twelve questions through the grounded providers in `providers/` once keys
  exist, and write `results/price-staleness-<date>.json` with the raw answers and the
  per-question reports.
- Decide the cadence. Monthly is the natural one: the reference moves daily, but a
  month is long enough for a stale answer to show as stale.
