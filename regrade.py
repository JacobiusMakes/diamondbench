"""Re-grade a stored results file with the current grader and answer key, without re-querying
any model. Raw answers are never modified; verdicts and the summary block are rewritten.
Usage: python regrade.py results/gemini-2026-09-02.json
"""
import json, sys, io, collections
import bench

GRADER_VERSION = "2026-09-02"

path = sys.argv[1]
d = json.load(io.open(path, encoding="utf-8"))
qs = json.load(io.open("questions.json", encoding="utf-8"))
qs = qs if isinstance(qs, list) else qs["questions"]
byid = {q["id"]: q for q in qs}
rows = d["results"] if isinstance(d, dict) and "results" in d else d
tally = collections.Counter()
cat = collections.defaultdict(collections.Counter)
notes = []
for r in rows:
    q = byid.get(r.get("id"))
    if not q or not r.get("answer"):
        continue
    g = bench.grade(r["answer"], q)
    r["verdict"] = g["verdict"]
    r["missing"] = r["missing_must_include"] = g.get("missing")
    r["wrong"] = r["wrong_claims"] = g.get("wrong_claims")
    tally[g["verdict"]] += 1
    cat[q["category"]][g["verdict"]] += 1
    if g["verdict"] != "pass":
        notes.append((g["verdict"], r["id"], q["category"], g.get("missing"),
                      [w["phrase"] for w in (g.get("wrong_claims") or [])]))
n = sum(tally.values())
print(f"{path}: {100*tally['pass']/n:.1f}% ({tally['pass']} pass / {tally['partial']} partial / {tally['fail']} fail of {n})")
for c in sorted(cat):
    print(f"   {c:24} {cat[c]['pass']}/{sum(cat[c].values())} pass ({cat[c]['partial']} partial, {cat[c]['fail']} fail)")
for v, i, c, m, w in notes:
    print(f"   [{v.upper()}] {i} ({c}) missing={m} wrong={w}")
if isinstance(d, dict):
    d["regraded_with_grader_version"] = GRADER_VERSION
    d["summary"] = {
        "total": len(rows), "graded": n,
        "counts": {"pass": tally["pass"], "partial": tally["partial"], "fail": tally["fail"],
                   "error": 0, "not_run": len(rows) - n},
        "accuracy_pct": round(100 * tally["pass"] / n, 1),
        "per_category": {c: {"pass": cat[c]["pass"], "partial": cat[c]["partial"], "fail": cat[c]["fail"]}
                         for c in sorted(cat)},
    }
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=1, ensure_ascii=False))
