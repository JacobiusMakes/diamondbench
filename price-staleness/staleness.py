#!/usr/bin/env python3
"""Price staleness: how far off, and how old, is the dollar figure an AI assistant gives a
shopper for a lab-grown diamond?

Standard library only. DESIGN.md has the twelve questions, the reference source, the two
metrics, and the disclosure rules.

    python staleness.py --selftest
    python staleness.py --check-reference
    python staleness.py --question ps-01 --date 2026-09-03 --answer "A 1 carat lab-grown diamond runs about $500 to $600."
    python staleness.py --question ps-02 --date 2026-09-03 --answer-file answer.txt --json

Two numbers come out of one answer:

  pct_overstatement  = (assistant midpoint - reference on the prompt date) / reference * 100
  months_stale       = age in months of the most recent reference reading that the quoted
                       midpoint matches within a tolerance (default 5 percent). None when
                       no reading in the loaded series matches ("not in series").

The reference CSV (reference/stonealgo-lab-grown.csv) mixes three kinds of rows, told
apart by the status column: observed (read from the source page on a stated date),
derived (arithmetic from a stated percent change, not a reading), placeholder (a slot to
fill; it never carries a value). Only observed rows are used unless --include says
otherwise. Placeholder rows are never computed against, whatever the flags.

No Stienhardt price appears in this file, the CSV, or DESIGN.md, by rule.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import unittest
from datetime import date, datetime

TOOL_VERSION = "2026-09-03"
HERE = os.path.abspath(os.path.dirname(__file__))
REF_CSV = os.path.join(HERE, "reference", "stonealgo-lab-grown.csv")
QUESTIONS_PATH = os.path.join(HERE, "questions.json")
DAYS_PER_MONTH = 30.44
DEFAULT_TOLERANCE_PCT = 5.0
MIN_SERIES_MONTHS = 12.0
# Dollar figures under this are treated as incidental (a cleaning fee, a shipping charge).
NOISE_FLOOR_USD = 20.0

# bench.py's prompt wrapper, unchanged, so this track asks the way DiamondBench asks.
PROMPT = "%s Answer as you would for a shopper."

LAB_WORDS = ("lab-grown", "lab grown", "lab-created", "lab created", "laboratory-grown",
             "laboratory grown", "lab-made", "man-made", "cvd", "hpht", "lgd")
NATURAL_WORDS = ("natural", "mined", "earth-grown", "earth grown", "earth-mined")
PER_CARAT_WORDS = ("per carat", "per ct", "/ct", "a carat", "/carat", "per-carat")

_DOLLAR = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*([kK])?(?![\d,])")
_WORDED = re.compile(r"(?<![\d,.$])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*([kK])?\s*(?:dollars|usd)\b",
                     re.IGNORECASE)
# Sentences, plus contrastive clauses, so "lab-grown ... $900, while a natural ... $4,000"
# splits into a lab clause and a natural clause.
_CLAUSE = re.compile(r"(?<=[.!?;])\s+|\n+|,\s+(?=(?:while|whereas|but|compared|versus|vs\.?)\b)",
                     re.IGNORECASE)


# ---------------------------------------------------------------------------
# Parsing the assistant's answer
# ---------------------------------------------------------------------------

def _has(text_low, words):
    return any(w in text_low for w in words)


def scope_clauses(text):
    """Return the clauses of an answer that price lab-grown stones. If the answer never
    mentions lab-grown wording, every clause is kept. If it does, clauses that mention
    natural or mined stones without lab-grown wording are dropped, so a natural-diamond
    comparison figure is not read as the lab-grown price."""
    clauses = [c for c in _CLAUSE.split(text or "") if c and c.strip()]
    if not clauses:
        return []
    if not any(_has(c.lower(), LAB_WORDS) for c in clauses):
        return clauses
    kept = [c for c in clauses
            if _has(c.lower(), LAB_WORDS) or not _has(c.lower(), NATURAL_WORDS)]
    return kept or clauses


def _to_value(whole, frac, k):
    v = float(whole.replace(",", "") + ("." + frac if frac else ""))
    if k:
        v *= 1000.0
    return v


def extract_figures(text, scope=True):
    """All dollar figures in reading order, as floats, after clause scoping. Figures under
    NOISE_FLOOR_USD are dropped."""
    out = []
    clauses = scope_clauses(text) if scope else [text or ""]
    for c in clauses:
        for m in _DOLLAR.finditer(c):
            out.append(_to_value(m.group(1), m.group(2), m.group(3)))
        for m in _WORDED.finditer(c):
            out.append(_to_value(m.group(1), m.group(2), m.group(3)))
    return [v for v in out if v >= NOISE_FLOOR_USD]


def figures_with_basis(text):
    """[(value, 'per_carat' | 'unknown')] so a per-carat quote can be converted."""
    out = []
    for c in scope_clauses(text):
        basis = "per_carat" if _has(c.lower(), PER_CARAT_WORDS) else "unknown"
        for m in _DOLLAR.finditer(c):
            out.append((_to_value(m.group(1), m.group(2), m.group(3)), basis))
        for m in _WORDED.finditer(c):
            out.append((_to_value(m.group(1), m.group(2), m.group(3)), basis))
    return [(v, b) for v, b in out if v >= NOISE_FLOOR_USD]


def midpoint(figures):
    """A stated range gives its midpoint; one figure is itself; several figures give the
    midpoint of the lowest and highest. None when there is nothing to read."""
    if not figures:
        return None
    if len(figures) == 1:
        return float(figures[0])
    return (min(figures) + max(figures)) / 2.0


def midpoint_in_basis(text, target_basis, carat):
    """Midpoint of the answer's figures expressed in the question's basis. Figures the
    answer labels per carat are converted when the target is per stone; unlabeled figures
    are assumed to already be in the question's basis (stated in the disclosure)."""
    vals = []
    for v, b in figures_with_basis(text):
        if b == "per_carat" and target_basis == "per_stone":
            v = v * carat
        elif b == "per_carat" and target_basis == "per_carat":
            pass
        vals.append(v)
    return midpoint(vals)


# ---------------------------------------------------------------------------
# Reference series
# ---------------------------------------------------------------------------

def _parse_date(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def load_reference(path=REF_CSV, include=("observed",)):
    """Rows of the reference CSV with a usable price and a status in `include`.
    Placeholder rows never have a price and are never returned."""
    rows = []
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            status = (r.get("status") or "").strip().lower()
            price = (r.get("price_usd") or "").strip()
            if status == "placeholder" or status not in include or not price:
                continue
            rows.append({
                "date": _parse_date(r["date"]),
                "carat": float(r["carat"]),
                "shape": (r.get("shape") or "all").strip().lower(),
                "basis": (r.get("basis") or "per_stone").strip().lower(),
                "price": float(price.replace(",", "")),
                "status": status,
                "source_url": (r.get("source_url") or "").strip(),
                "note": (r.get("note") or "").strip(),
            })
    return rows


def reference_status(path=REF_CSV):
    counts = {}
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            s = (r.get("status") or "").strip().lower()
            counts[s] = counts.get(s, 0) + 1
    return counts


def series_for(rows, carat, shape="all", basis="per_stone"):
    """[(date, price)] sorted ascending for one carat bucket and shape, converted to the
    requested basis (per_stone <-> per_carat by multiplying or dividing by carat)."""
    out = []
    for r in rows:
        if abs(r["carat"] - float(carat)) > 1e-6 or r["shape"] != shape:
            continue
        p = r["price"]
        if r["basis"] != basis:
            p = p / r["carat"] if basis == "per_carat" else p * r["carat"]
        out.append((r["date"], p))
    return sorted(out)


def reference_on(series, asof):
    """(date, price) of the latest reading dated on or before asof, else None."""
    best = None
    for d, p in series:
        if d <= asof and p:
            best = (d, p)
    return best


def series_span_months(series):
    if len(series) < 2:
        return 0.0
    return round((series[-1][0] - series[0][0]).days / DAYS_PER_MONTH, 1)


# ---------------------------------------------------------------------------
# The two metrics
# ---------------------------------------------------------------------------

def pct_overstatement(mid, ref):
    """Percent by which the assistant's midpoint exceeds the reference. Negative means
    understatement. None if either side is missing."""
    if mid is None or not ref:
        return None
    return round((mid - ref) / ref * 100.0, 1)


def months_stale(mid, series, asof, tol_pct=DEFAULT_TOLERANCE_PCT):
    """Months between asof and the most recent reading (on or before asof) that the
    midpoint matches within tol_pct. 0.0 when the current reading matches. None when
    nothing in the series matches."""
    if mid is None:
        return None
    for d, p in sorted(series, reverse=True):
        if d > asof or not p:
            continue
        if abs(p - mid) / p * 100.0 <= tol_pct:
            return round((asof - d).days / DAYS_PER_MONTH, 1)
    return None


# ---------------------------------------------------------------------------
# One answer, one report
# ---------------------------------------------------------------------------

def load_questions(path=QUESTIONS_PATH):
    d = json.load(io.open(path, encoding="utf-8"))
    return {q["id"]: q for q in d["questions"]}


def evaluate(answer, q, asof, rows, tol_pct=DEFAULT_TOLERANCE_PCT, model="", provider="",
             grounded=None):
    series = series_for(rows, q["carat"], q.get("shape", "all"), q.get("basis", "per_stone"))
    ref = reference_on(series, asof)
    mid = midpoint_in_basis(answer, q.get("basis", "per_stone"), q["carat"])
    span = series_span_months(series)
    stale = months_stale(mid, series, asof, tol_pct) if span >= MIN_SERIES_MONTHS else None
    report = {
        "tool_version": TOOL_VERSION,
        "question_id": q["id"],
        "prompt": PROMPT % q["question"],
        "asked_on": asof.isoformat(),
        "model": model,
        "provider": provider,
        "grounded": grounded,
        "basis": q.get("basis", "per_stone"),
        "carat": q["carat"],
        "shape": q.get("shape", "all"),
        "parsed_figures": [v for v, _b in figures_with_basis(answer)],
        "assistant_midpoint": mid,
        "reference_value": ref[1] if ref else None,
        "reference_date": ref[0].isoformat() if ref else None,
        "reference_source": "StoneAlgo lab-grown price index (see reference CSV source_url)",
        "pct_overstatement": pct_overstatement(mid, ref[1]) if ref else None,
        "months_stale": stale,
        "series_span_months": span,
        "raw_answer": answer,
        "notes": [],
    }
    if mid is None:
        report["notes"].append("no figure: the answer gave no dollar amount")
    if ref is None:
        report["notes"].append("no reference reading on or before the prompt date for this bucket")
    if span < MIN_SERIES_MONTHS:
        report["notes"].append("series too short (%.1f months, need %.0f): months_stale not quoted"
                               % (span, MIN_SERIES_MONTHS))
    elif mid is not None and stale is None:
        report["notes"].append("not in series: no reading within %.0f%% of the midpoint" % tol_pct)
    report["notes"].append("unlabeled figures are assumed to be in the question's basis; "
                           "figures the answer labels per carat were converted")
    return report


def format_report(r):
    lines = [
        "DiamondBench price staleness (tool %s)" % r["tool_version"],
        "question   %s: %s" % (r["question_id"], r["prompt"]),
        "asked on   %s   model %s   provider %s   grounded %s"
        % (r["asked_on"], r["model"] or "?", r["provider"] or "?", r["grounded"]),
        "parsed     %s -> midpoint %s (%s, %s ct, %s)"
        % (r["parsed_figures"], r["assistant_midpoint"], r["basis"], r["carat"], r["shape"]),
        "reference  %s on %s" % (r["reference_value"], r["reference_date"]),
        "overstatement  %s %%" % r["pct_overstatement"],
        "months stale   %s   (series spans %.1f months)" % (r["months_stale"], r["series_span_months"]),
    ]
    for n in r["notes"]:
        lines.append("note       " + n)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Three synthetic unit tests (no CSV, no network)
# ---------------------------------------------------------------------------

class StalenessTests(unittest.TestCase):

    def test_parse_range_midpoint_scoped_to_lab_grown(self):
        text = ("A 1 carat lab-grown diamond typically runs about $900 to $1,100 today, "
                "while a natural 1 carat stone is closer to $4,000 to $6,000. "
                "Expect a $15 shipping charge.")
        figs = extract_figures(text)
        self.assertEqual(figs, [900.0, 1100.0])
        self.assertEqual(midpoint(figs), 1000.0)

    def test_pct_overstatement_against_reference_on_date(self):
        series = [(date(2026, 8, 1), 560.0), (date(2026, 9, 1), 500.0)]
        ref = reference_on(series, date(2026, 9, 3))
        self.assertEqual(ref, (date(2026, 9, 1), 500.0))
        self.assertEqual(pct_overstatement(1000.0, ref[1]), 100.0)
        self.assertEqual(pct_overstatement(450.0, ref[1]), -10.0)
        self.assertIsNone(pct_overstatement(None, ref[1]))

    def test_months_stale_matches_series(self):
        series = [
            (date(2025, 9, 1), 1400.0), (date(2025, 12, 1), 1200.0),
            (date(2026, 3, 1), 1000.0), (date(2026, 4, 1), 900.0),
            (date(2026, 5, 1), 800.0), (date(2026, 6, 1), 700.0),
            (date(2026, 7, 1), 600.0), (date(2026, 8, 1), 550.0),
            (date(2026, 9, 1), 544.0),
        ]
        asof = date(2026, 9, 1)
        self.assertGreaterEqual(series_span_months(series), MIN_SERIES_MONTHS)
        self.assertEqual(months_stale(800.0, series, asof), 4.0)     # matches 2026-05-01
        self.assertEqual(months_stale(544.0, series, asof), 0.0)     # matches the current reading
        self.assertIsNone(months_stale(5000.0, series, asof))        # not in series


def selftest():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StalenessTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="DiamondBench price staleness")
    ap.add_argument("--selftest", action="store_true", help="run the three unit tests")
    ap.add_argument("--check-reference", action="store_true", help="count reference rows by status")
    ap.add_argument("--question", help="question id from questions.json, e.g. ps-01")
    ap.add_argument("--carat", type=float, help="override: carat bucket")
    ap.add_argument("--shape", default=None, help="override: shape (default all)")
    ap.add_argument("--basis", default=None, choices=["per_stone", "per_carat"])
    ap.add_argument("--answer", help="the assistant's answer text")
    ap.add_argument("--answer-file", help="file containing the assistant's answer text")
    ap.add_argument("--date", help="date the model was asked, YYYY-MM-DD (default today)")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PCT)
    ap.add_argument("--include", default="observed",
                    help="comma list of reference statuses to use: observed,derived (placeholders never)")
    ap.add_argument("--model", default="")
    ap.add_argument("--provider", default="")
    ap.add_argument("--grounded", choices=["yes", "no"], default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())
    if a.check_reference:
        counts = reference_status()
        rows = load_reference(include=("observed", "derived"))
        print("reference rows by status:", counts)
        print("usable observed+derived rows:", len(rows))
        for r in rows:
            print("  %s  %.1f ct %-5s %-9s %8.0f  %s" % (r["date"], r["carat"], r["shape"], r["basis"],
                                                         r["price"], r["status"]))
        return

    answer = a.answer
    if a.answer_file:
        answer = io.open(a.answer_file, encoding="utf-8").read()
    if answer is None:
        ap.error("give --answer or --answer-file (or --selftest / --check-reference)")
    if a.question:
        q = dict(load_questions()[a.question])
    else:
        if a.carat is None:
            ap.error("give --question or --carat")
        q = {"id": "adhoc", "question": "(ad hoc)", "carat": a.carat}
    if a.carat is not None:
        q["carat"] = a.carat
    if a.shape:
        q["shape"] = a.shape.lower()
    if a.basis:
        q["basis"] = a.basis
    q.setdefault("shape", "all")
    q.setdefault("basis", "per_stone")
    asof = _parse_date(a.date) if a.date else date.today()
    include = tuple(s.strip().lower() for s in a.include.split(",") if s.strip())
    rows = load_reference(include=include)
    grounded = None if a.grounded is None else (a.grounded == "yes")
    report = evaluate(answer, q, asof, rows, a.tolerance, a.model, a.provider, grounded)
    if a.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
