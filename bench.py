#!/usr/bin/env python3
"""DiamondBench: an open, honest benchmark of how accurately AI answer engines
respond to diamond and gemology questions. Maintained by Stienhardt & Stones.

Pure Python standard library. No dependencies.

Usage:
  python bench.py --provider gemini            # run all questions
  python bench.py --provider gemini --n 5      # first 5 (smoke test)
  python bench.py --list-providers             # show provider status
  python bench.py --selftest                   # verify the grader offline, no API key

For each question in questions.json the harness calls the chosen model, captures
the full answer, and grades it pass / partial / fail by a deterministic rule:

  pass    = every must_include slot present (case-insensitive, counting synonyms)
            AND no wrong claim (must_not_include) asserted
  partial = some must_include slot missing, but no wrong claim asserted
  fail    = at least one wrong claim asserted

A must_not_include phrase that appears inside a negated or contrastive sentence
("it is a myth that...", "unlike the navette...") is a debunk, not an assertion,
and is not counted against the model. See METHODOLOGY.md for the exact rule and
its known limits.

Results are written to results/<provider>-<date>.json with per-question verdicts
and the raw answers, so every verdict can be audited. If a provider's quota runs
out mid-run, the remaining questions are marked not_run and reported honestly;
the harness never fabricates a verdict.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.abspath(os.path.dirname(__file__))
QUESTIONS_PATH = os.path.join(HERE, "questions.json")
RESULTS_DIR = os.path.join(HERE, "results")

# The prompt wrapper mirrors a buyer talking to an AI answer engine.
PROMPT = "%s Answer as you would for a shopper."


# ---------------------------------------------------------------------------
# API keys. Environment variable first, then local .env files (never committed).
# ---------------------------------------------------------------------------

ENV_FILE_CANDIDATES = [
    os.path.join(HERE, ".env"),
    # Stienhardt local layout: this repo lives at <root>/open-source/diamondbench
    os.path.join(HERE, "..", "..", "AssetCreation", ".env"),
]


def read_key(name):
    """Return the named key from the environment or a local .env file, else None."""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    for p in ENV_FILE_CANDIDATES:
        try:
            for line in io.open(p, encoding="utf-8-sig"):
                if line.strip().startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip()
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# Providers. Each is a callable: question_text -> {"text": str, "sources": [str]}
# Raise ProviderNotConfigured when the key is missing, QuotaExhausted when the
# provider says stop. Only Gemini is wired live today; the OpenAI and Anthropic
# providers are clearly marked stubs so the harness is genuinely multi-model.
# ---------------------------------------------------------------------------

class ProviderNotConfigured(Exception):
    pass


class QuotaExhausted(Exception):
    pass


GEMINI_MODEL = "gemini-2.5-flash"


def gemini_provider(question):
    """Live provider: Gemini with Google Search grounding, a real proxy for how
    AI answer engines respond to shoppers. thinkingBudget is set to 0 so the
    answer text is not truncated by thinking-token spend."""
    key = read_key("GEMINI_API_KEY")
    if not key:
        raise ProviderNotConfigured("GEMINI_API_KEY not found. Set the key to run this model.")
    body = {
        "contents": [{"parts": [{"text": PROMPT % question}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
    }
    url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
           % (GEMINI_MODEL, key))
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    tries = 0
    while True:
        tries += 1
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode()[:400]
            except Exception:
                pass
            quota = e.code == 429 or "RESOURCE_EXHAUSTED" in detail
            if quota and tries == 1:
                time.sleep(20)  # one polite retry, then fail closed
                continue
            if quota:
                raise QuotaExhausted("Gemini quota exhausted (HTTP %d)." % e.code)
            raise RuntimeError("Gemini HTTP %d: %s" % (e.code, detail))
    cand = (d.get("candidates") or [{}])[0]
    text = " ".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", []) or []
    sources = []
    for c in chunks:
        t = (c.get("web", {}) or {}).get("title", "")
        if t and t not in sources:
            sources.append(t)
    return {"text": text, "sources": sources}


def openai_provider(question):
    """STUB: not wired live today. Reads OPENAI_API_KEY and, if present, makes a
    plain chat.completions call (no web grounding; note the comparability caveat
    in METHODOLOGY.md). Contributions that harden this path are welcome."""
    key = read_key("OPENAI_API_KEY")
    if not key:
        raise ProviderNotConfigured("OPENAI_API_KEY not found. Set the key to run this model.")
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": PROMPT % question}],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise QuotaExhausted("OpenAI quota exhausted (HTTP 429).")
        raise RuntimeError("OpenAI HTTP %d" % e.code)
    text = d["choices"][0]["message"]["content"]
    return {"text": text, "sources": []}


def anthropic_provider(question):
    """STUB: not wired live today. Reads ANTHROPIC_API_KEY and, if present, makes
    a plain Messages API call (no web grounding; note the comparability caveat in
    METHODOLOGY.md). Contributions that harden this path are welcome."""
    key = read_key("ANTHROPIC_API_KEY")
    if not key:
        raise ProviderNotConfigured("ANTHROPIC_API_KEY not found. Set the key to run this model.")
    body = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": PROMPT % question}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise QuotaExhausted("Anthropic quota exhausted (HTTP 429).")
        raise RuntimeError("Anthropic HTTP %d" % e.code)
    text = " ".join(b.get("text", "") for b in d.get("content", []))
    return {"text": text, "sources": []}


PROVIDERS = {
    "gemini": (gemini_provider, "LIVE: Gemini (%s) with Google Search grounding" % GEMINI_MODEL),
    "openai": (openai_provider, "STUB: plain chat completion, no grounding"),
    "anthropic": (anthropic_provider, "STUB: plain Messages call, no grounding"),
}


# ---------------------------------------------------------------------------
# Deterministic grading
# ---------------------------------------------------------------------------

# Words and phrases that mark a sentence as negating, debunking, or contrasting,
# so a must_not_include phrase inside it is a debunk rather than an assertion.
NEGATION_MARKERS = [
    "no", "not", "never", "nor", "myth", "false", "falsely", "isn't", "aren't",
    "doesn't", "don't", "won't", "wasn't", "weren't", "didn't", "cannot", "can't",
    "unlike", "rather than", "instead of", "misconception", "contrary", "debunk",
    "debunked", "legend", "folklore", "without", "despite", "avoid", "skip", "steer clear",
    "whereas", "while", "by contrast", "in contrast", "compared to", "compared with",
    "idea that", "belief that", "story that", "notion that", "worry that",
    "fear that", "no longer", "as opposed to", "versus", "different from",
    "differs from", "confused with", "confuse", "mistake", "mistaken",
    # past-tense reporting verbs: "the Romans believed a vein ran to the heart"
    # reports a historical belief rather than asserting it as fact
    "believed", "belief",
]

SENTENCE_SPLIT = re.compile(r"[.!?;:\n•]")


def _contains(text_low, needle):
    """Case-insensitive containment. Short single tokens (under 4 chars) must
    stand alone (not embedded in a longer word or number), so 'IGI' does not
    match 'original' and '10' does not match '100'."""
    n = needle.lower().strip()
    if not n:
        return False
    if len(n) < 4 and " " not in n:
        return re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", text_low) is not None
    return n in text_low


def _slot_hit(text_low, slot):
    """A must_include slot is either a plain string or {"any": [synonyms]}."""
    if isinstance(slot, dict):
        return any(_contains(text_low, s) for s in slot.get("any", []))
    return _contains(text_low, slot)


def _slot_label(slot):
    if isinstance(slot, dict):
        return " | ".join(slot.get("any", []))
    return slot


def _sentences_with_spans(text_low):
    """Yield (start, end) spans of sentences in the lowered text."""
    spans = []
    start = 0
    for m in SENTENCE_SPLIT.finditer(text_low):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text_low)))
    return spans


def _is_negated(sentence):
    return any(_contains(sentence, mk) for mk in NEGATION_MARKERS)


def find_wrong_claims(answer, must_not):
    """Return [{phrase, snippet}] for each must_not_include phrase asserted
    (present in at least one sentence that carries no negation or contrast
    marker). Deterministic; imperfect by design, see METHODOLOGY.md."""
    text_low = answer.lower()
    spans = _sentences_with_spans(text_low)
    # A bulleted or numbered list item inherits the negation of its lead-in line, so
    # "Avoid the following:" followed by "* bleach" is a debunk, not an assertion.
    LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
    # The lead-in is the whole block of prose between the previous list and this one
    # (a "What to avoid:" heading plus a "steer clear of the following:" line), so
    # negation accumulates across those lines and resets only after a list ends.
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


def grade(answer, q):
    """Grade one answer against one question. Returns a dict with verdict,
    missing must_include slots, and asserted wrong claims."""
    text_low = answer.lower()
    missing = [_slot_label(s) for s in q["must_include"] if not _slot_hit(text_low, s)]
    wrong = find_wrong_claims(answer, q.get("must_not_include", []))
    if wrong:
        verdict = "fail"
    elif not missing:
        verdict = "pass"
    else:
        verdict = "partial"
    return {"verdict": verdict, "missing": missing, "wrong_claims": wrong}


# ---------------------------------------------------------------------------
# Self-test: verify the grader offline with canned answers. No API key needed.
# ---------------------------------------------------------------------------

def selftest():
    qs = load_questions()
    by_id = {q["id"]: q for q in qs}
    cases = [
        # (question id, canned answer, expected verdict)
        ("lg-fade",
         "No. A Lab Grown Diamond is a real diamond, crystallized carbon, and it "
         "does not fade, cloud, or yellow. That worry comes from cubic zirconia, "
         "a different material.",
         "pass"),
        ("lg-fade",
         "Lab grown diamonds are real diamonds made of carbon and they will not "
         "degrade. However, budget stones can fade over time if worn daily.",
         "fail"),  # the wrong claim is asserted in its own non-negated sentence
        ("lg-fade",
         "They stay bright forever and never change.",
         "partial"),  # no wrong claim, but the 'real diamond / carbon' slot is missing
        ("shape-dutch-marquise",
         "A Dutch Marquise is an elongated hexagonal cut diamond with pointed ends "
         "and straight, angular sides. Unlike the classic marquise, or navette, it "
         "does not have curved sides. On an IGI report it reads Hexagonal Modified "
         "Brilliant.",
         "pass"),  # navette + curved sides appear only inside negated/contrast sentences
        ("shape-dutch-marquise",
         "The Dutch Marquise is a soft variation of the marquise with gently "
         "curved sides and softened points.",
         "fail"),
        ("myth-months-salary",
         "No, that is a myth. The months-of-salary idea came from De Beers "
         "advertising in the late 1930s, not from any old tradition. Spend what "
         "fits your budget.",
         "pass"),
        ("myth-coal",
         "Mostly no. Diamonds form deep in the mantle and are older than land "
         "plants, so coal is not their source.",
         "pass"),
    ]
    failures = 0
    for qid, canned, expected in cases:
        got = grade(canned, by_id[qid])
        ok = got["verdict"] == expected
        if not ok:
            failures += 1
        print("  %-4s %-28s expected %-7s got %-7s %s"
              % ("OK" if ok else "FAIL", qid, expected, got["verdict"],
                 "" if ok else json.dumps({"missing": got["missing"],
                                           "wrong": [w["phrase"] for w in got["wrong_claims"]]})))
    print("selftest: %d/%d cases behave as expected" % (len(cases) - failures, len(cases)))
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def load_questions(path=QUESTIONS_PATH):
    data = json.load(io.open(path, encoding="utf-8-sig"))
    return data["questions"]


def run(provider_name, limit=0, sleep_s=0.8):
    if provider_name not in PROVIDERS:
        raise SystemExit("unknown provider %r. Choose from: %s"
                         % (provider_name, ", ".join(sorted(PROVIDERS))))
    provider, _desc = PROVIDERS[provider_name]
    questions = load_questions()
    if limit:
        questions = questions[:limit]

    results = []
    quota_hit = False
    print("DiamondBench: %d questions -> %s\n" % (len(questions), provider_name))
    for i, q in enumerate(questions):
        if quota_hit:
            results.append({"id": q["id"], "category": q["category"],
                            "question": q["question"], "verdict": "not_run",
                            "note": "provider quota exhausted before this question"})
            continue
        try:
            out = provider(q["question"])
        except ProviderNotConfigured as e:
            raise SystemExit(str(e))
        except QuotaExhausted as e:
            print("  !! %s Marking this and remaining questions not_run." % e)
            quota_hit = True
            results.append({"id": q["id"], "category": q["category"],
                            "question": q["question"], "verdict": "not_run",
                            "note": str(e)})
            continue
        except Exception as e:
            print("  !  %-44s ERROR %s" % (q["id"][:44], e))
            results.append({"id": q["id"], "category": q["category"],
                            "question": q["question"], "verdict": "error",
                            "note": str(e)})
            time.sleep(sleep_s)
            continue
        g = grade(out["text"], q)
        row = {
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "verdict": g["verdict"],
            "missing_must_include": g["missing"],
            "wrong_claims": g["wrong_claims"],
            "correct_answer": q["correct_answer"],
            "answer": out["text"],
            "grounding_sources": out.get("sources", []),
        }
        results.append(row)
        flag = {"pass": "ok", "partial": "PART", "fail": "FAIL"}[g["verdict"]]
        print("  %-4s %-38s (%s)" % (flag, q["id"][:38], q["category"]))
        time.sleep(sleep_s)

    summary = summarize(results)
    today = date.today().isoformat()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "%s-%s.json" % (provider_name, today))
    payload = {
        "benchmark": "DiamondBench",
        "provider": provider_name,
        "model": GEMINI_MODEL if provider_name == "gemini" else "see provider stub",
        "grounded_search": provider_name == "gemini",
        "date": today,
        "summary": summary,
        "results": results,
    }
    io.open(out_path, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, indent=2))
    print_scoreboard(summary, results, provider_name, today)
    print("\nWROTE %s" % out_path)
    return payload


def summarize(results):
    graded = [r for r in results if r["verdict"] in ("pass", "partial", "fail")]
    counts = {"pass": 0, "partial": 0, "fail": 0, "error": 0, "not_run": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    per_cat = {}
    for r in graded:
        c = per_cat.setdefault(r["category"], {"pass": 0, "partial": 0, "fail": 0})
        c[r["verdict"]] += 1
    accuracy = (100.0 * counts["pass"] / len(graded)) if graded else None
    return {"total": len(results), "graded": len(graded), "counts": counts,
            "accuracy_pct": round(accuracy, 1) if accuracy is not None else None,
            "per_category": per_cat}


def print_scoreboard(summary, results, provider_name, today):
    c = summary["counts"]
    print("\n=== DIAMONDBENCH SCOREBOARD (%s, %s) ===" % (provider_name, today))
    if summary["graded"]:
        print("overall accuracy: %.1f%%  (%d pass / %d partial / %d fail of %d graded)"
              % (summary["accuracy_pct"], c["pass"], c["partial"], c["fail"], summary["graded"]))
    if c["not_run"]:
        print("NOT RUN (quota): %d questions. Verdicts above cover only what actually ran."
              % c["not_run"])
    if c["error"]:
        print("errors: %d questions (see results file)" % c["error"])
    print("\nper category (pass/partial/fail):")
    for cat in sorted(summary["per_category"]):
        s = summary["per_category"][cat]
        n = s["pass"] + s["partial"] + s["fail"]
        print("   %-24s %d/%d pass   (%d partial, %d fail)"
              % (cat, s["pass"], n, s["partial"], s["fail"]))
    misses = [r for r in results if r["verdict"] in ("partial", "fail")]
    if misses:
        print("\nwhat the model got wrong or incomplete:")
        for r in misses:
            print("   [%s] %s" % (r["verdict"].upper(), r["question"]))
            for w in r.get("wrong_claims", []):
                print("        wrong claim %r in: \"%s\"" % (w["phrase"], w["snippet"][:160]))
            if r["verdict"] == "partial":
                for mslot in r.get("missing_must_include", [])[:3]:
                    print("        missing: %s" % mslot[:120])


def main():
    ap = argparse.ArgumentParser(description="DiamondBench runner")
    ap.add_argument("--provider", default="gemini", help="gemini | openai | anthropic")
    ap.add_argument("--n", type=int, default=0, help="limit to first N questions (0 = all)")
    ap.add_argument("--list-providers", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="verify the grader offline against canned answers")
    a = ap.parse_args()
    if a.list_providers:
        for name in sorted(PROVIDERS):
            _fn, desc = PROVIDERS[name]
            key_names = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
                         "anthropic": "ANTHROPIC_API_KEY"}
            has_key = bool(read_key(key_names[name]))
            note = "key found" if has_key else "set the key to run this model"
            print("  %-10s %-55s [%s]" % (name, desc, note))
        return
    if a.selftest:
        sys.exit(selftest())
    run(a.provider, limit=a.n)


if __name__ == "__main__":
    main()
