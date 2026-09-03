#!/usr/bin/env python3
"""DiamondBench metric for lm-evaluation-harness.

Reuses bench.py's grade() so a harness run and a bench.py run agree verdict for verdict.
bench.py is imported from the repository root when this file lives in <repo>/harness/;
if the folder has been copied elsewhere and bench.py cannot be found, an embedded copy
of the grading functions (verbatim from bench.py, grader version 2026-09-02) is used.
Keep that copy in sync with bench.py: `python diamondbench_metric.py --selftest` checks
the two agree on every stored answer whenever both are available.

The Hub dataset stores every must_include slot as a list of strings (Arrow cannot mix
strings and structs in one column). hub_doc_to_question() converts a row back to the
shape bench.grade() expects: a one-element list becomes a plain string, a longer list
becomes {"any": [...]}.

process_results(doc, results) is the lm-eval contract: results[0] is the generated
answer; the return value is a dict of metric name -> per-document value, which the
metric_list in diamondbench.yaml aggregates by mean.
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
GRADER_VERSION = "2026-09-02"


def _load_bench():
    try:
        import bench  # repo root already on sys.path
        return bench
    except ImportError:
        pass
    if os.path.exists(os.path.join(REPO, "bench.py")):
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        try:
            import bench
            return bench
        except ImportError:
            return None
    return None


_bench = _load_bench()

# ---------------------------------------------------------------------------
# Embedded copy of bench.py's grader (used only when bench.py is not importable).
# Verbatim from bench.py, grader version 2026-09-02. Do not edit here; edit bench.py
# and re-copy.
# ---------------------------------------------------------------------------

NEGATION_MARKERS = [
    "no", "not", "never", "nor", "myth", "false", "falsely", "isn't", "aren't",
    "doesn't", "don't", "won't", "wasn't", "weren't", "didn't", "cannot", "can't",
    "unlike", "rather than", "instead of", "misconception", "contrary", "debunk",
    "debunked", "legend", "folklore", "without", "despite", "avoid", "skip", "steer clear",
    "whereas", "while", "by contrast", "in contrast", "compared to", "compared with",
    "idea that", "belief that", "story that", "notion that", "worry that",
    "fear that", "no longer", "as opposed to", "versus", "different from",
    "differs from", "confused with", "confuse", "mistake", "mistaken",
    "believed", "belief",
]

SENTENCE_SPLIT = re.compile(r"[.!?;:\n•]")


def _contains(text_low, needle):
    n = needle.lower().strip()
    if not n:
        return False
    if len(n) < 4 and " " not in n:
        return re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", text_low) is not None
    return n in text_low


def _slot_hit(text_low, slot):
    if isinstance(slot, dict):
        return any(_contains(text_low, s) for s in slot.get("any", []))
    return _contains(text_low, slot)


def _slot_label(slot):
    if isinstance(slot, dict):
        return " | ".join(slot.get("any", []))
    return slot


def _sentences_with_spans(text_low):
    spans = []
    start = 0
    for m in SENTENCE_SPLIT.finditer(text_low):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text_low)))
    return spans


def _is_negated(sentence):
    return any(_contains(sentence, mk) for mk in NEGATION_MARKERS)


def _find_wrong_claims_embedded(answer, must_not):
    text_low = answer.lower()
    spans = _sentences_with_spans(text_low)
    LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
    negated_span = {}
    lead_negated = False
    in_list = False
    for (s, e) in spans:
        sentence = text_low[s:e]
        own = _is_negated(sentence)
        if LIST_ITEM.match(sentence):
            negated_span[(s, e)] = own or lead_negated
            in_list = True
        else:
            if sentence.strip():
                lead_negated = own if in_list else (lead_negated or own)
                in_list = False
            negated_span[(s, e)] = own
    hits = []
    for phrase in must_not:
        p = phrase.lower().strip()
        if not p or p not in text_low:
            continue
        asserted_snippet = None
        idx = 0
        while True:
            pos = text_low.find(p, idx)
            if pos < 0:
                break
            sent = next(((s, e) for (s, e) in spans if s <= pos < e), (0, len(text_low)))
            sentence = text_low[sent[0]:sent[1]]
            if not negated_span.get(sent, _is_negated(sentence)):
                asserted_snippet = answer[sent[0]:sent[1]].strip()
                break
            idx = pos + max(1, len(p))
        if asserted_snippet is not None:
            hits.append({"phrase": phrase, "snippet": asserted_snippet[:300]})
    return hits


def _grade_embedded(answer, q):
    text_low = answer.lower()
    missing = [_slot_label(s) for s in q["must_include"] if not _slot_hit(text_low, s)]
    wrong = _find_wrong_claims_embedded(answer, q.get("must_not_include", []))
    if wrong:
        verdict = "fail"
    elif not missing:
        verdict = "pass"
    else:
        verdict = "partial"
    return {"verdict": verdict, "missing": missing, "wrong_claims": wrong}


if _bench is not None:
    grade = _bench.grade
    GRADER_SOURCE = "bench.py"
else:
    grade = _grade_embedded
    GRADER_SOURCE = "embedded copy"


# ---------------------------------------------------------------------------
# Hub row -> bench.py question
# ---------------------------------------------------------------------------

def hub_doc_to_question(doc):
    """Convert a Hub row (must_include as list of lists) to bench.py's question shape."""
    slots = []
    for slot in doc.get("must_include", []):
        if isinstance(slot, (str, dict)):
            slots.append(slot)          # already in bench.py shape
            continue
        syn = [s for s in slot if isinstance(s, str)]
        slots.append(syn[0] if len(syn) == 1 else {"any": syn})
    return {
        "id": doc.get("id"),
        "category": doc.get("category"),
        "question": doc.get("question"),
        "must_include": slots,
        "must_not_include": list(doc.get("must_not_include") or []),
    }


def grade_doc(doc, answer):
    """Grade one generated answer against one Hub row. Returns bench.py's grade dict."""
    return grade(answer or "", hub_doc_to_question(doc))


def verdict(doc, answer):
    """'pass' | 'partial' | 'fail' for one document."""
    return grade_doc(doc, answer)["verdict"]


def process_results(doc, results):
    """lm-eval contract. results[0] is the generated continuation."""
    answer = results[0] if results else ""
    v = grade_doc(doc, answer)["verdict"]
    return {
        "accuracy": 1.0 if v == "pass" else 0.0,
        "pass": 1.0 if v == "pass" else 0.0,
        "partial": 1.0 if v == "partial" else 0.0,
        "fail": 1.0 if v == "fail" else 0.0,
    }


# ---------------------------------------------------------------------------
# Self-test: re-grade the stored runs through process_results and compare with the
# verdicts in the results files (and with bench.grade when bench.py is importable).
# ---------------------------------------------------------------------------

def _load_hub_rows():
    path = os.path.join(REPO, "hf-dataset", "questions.jsonl")
    rows = {}
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            rows[r["id"]] = r
    return rows


def selftest():
    print("grader source: %s (grader version %s)" % (GRADER_SOURCE, GRADER_VERSION))
    rows = _load_hub_rows()
    print("hub rows: %d" % len(rows))
    failures = 0
    results_dir = os.path.join(REPO, "results")
    files = sorted(f for f in os.listdir(results_dir) if f.endswith(".json"))
    for f in files:
        d = json.load(io.open(os.path.join(results_dir, f), encoding="utf-8"))
        if not isinstance(d, dict) or "results" not in d:
            continue
        tally = {"pass": 0, "partial": 0, "fail": 0}
        mismatches = []
        for r in d["results"]:
            if not r.get("answer") or r["id"] not in rows:
                continue
            out = process_results(rows[r["id"]], [r["answer"]])
            v = "pass" if out["pass"] else ("partial" if out["partial"] else "fail")
            tally[v] += 1
            if v != r.get("verdict"):
                mismatches.append((r["id"], r.get("verdict"), v))
            if _bench is not None:
                emb = _grade_embedded(r["answer"], hub_doc_to_question(rows[r["id"]]))["verdict"]
                if emb != v:
                    mismatches.append((r["id"], "embedded=" + emb, "bench=" + v))
        n = sum(tally.values())
        acc = 100.0 * tally["pass"] / n if n else 0.0
        print("  %-28s %d graded: %d pass / %d partial / %d fail = %.1f%%  mismatches: %d"
              % (f, n, tally["pass"], tally["partial"], tally["fail"], acc, len(mismatches)))
        for m in mismatches:
            print("     MISMATCH", m)
        failures += len(mismatches)
    print("selftest: %s" % ("OK, harness verdicts equal stored verdicts" if not failures
                             else "%d mismatches" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
