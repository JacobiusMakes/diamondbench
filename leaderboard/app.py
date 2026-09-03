#!/usr/bin/env python3
"""DiamondBench leaderboard: a minimal local Gradio app over results/*.json.

Local run only. It binds to 127.0.0.1 and never opens a public share link.

    pip install -r leaderboard/requirements.txt
    python leaderboard/app.py                 # http://127.0.0.1:7860
    python leaderboard/app.py --print         # same tables as plain text, no gradio needed

Every results file written by bench.py (or re-derived by regrade.py) becomes one row:
run date, model, grounded, pass, partial, fail, accuracy. A second table breaks each
run down by category. The footer states the grader version and links the methodology.
Nothing here re-grades anything; it reads the summary blocks the grader wrote.
"""
import argparse
import glob
import io
import json
import os

HERE = os.path.abspath(os.path.dirname(__file__))
DEFAULT_RESULTS_DIR = os.path.abspath(os.path.join(HERE, "..", "results"))
METHODOLOGY_URL = "https://github.com/JacobiusMakes/diamondbench/blob/main/METHODOLOGY.md"
REPO_URL = "https://github.com/JacobiusMakes/diamondbench"
GRADER_VERSION = "2026-09-02"

SUMMARY_HEADERS = ["Run date", "Model", "Grounded", "Pass", "Partial", "Fail", "Accuracy"]


def load_runs(results_dir=DEFAULT_RESULTS_DIR):
    """Read every results/*.json that has a summary block. Sorted by date, then provider."""
    runs = []
    for path in sorted(glob.glob(os.path.join(results_dir, "*.json"))):
        try:
            d = json.load(io.open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or "summary" not in d or "results" not in d:
            continue
        s = d["summary"] or {}
        runs.append({
            "file": os.path.basename(path),
            "date": str(d.get("date", "")),
            "provider": str(d.get("provider", "")),
            "model": str(d.get("model", "")),
            "grounded": bool(d.get("grounded_search")),
            "counts": s.get("counts", {}),
            "graded": s.get("graded", 0),
            "total": s.get("total", 0),
            "accuracy_pct": s.get("accuracy_pct"),
            "per_category": s.get("per_category", {}),
            "grader": d.get("regraded_with_grader_version") or "unrecorded",
        })
    runs.sort(key=lambda r: (r["date"], r["provider"], r["file"]))
    return runs


def summary_rows(runs):
    rows = []
    for r in runs:
        c = r["counts"]
        acc = "%.1f%%" % r["accuracy_pct"] if r["accuracy_pct"] is not None else "n/a"
        note = ""
        if c.get("not_run"):
            note = " (%d not run)" % c["not_run"]
        rows.append([r["date"], r["model"], "yes" if r["grounded"] else "no",
                     c.get("pass", 0), c.get("partial", 0), c.get("fail", 0), acc + note])
    return SUMMARY_HEADERS, rows


def _run_label(r):
    return "%s %s%s" % (r["date"], r["model"], "" if r["grounded"] else " (ungrounded)")


def category_rows(runs):
    cats = sorted({c for r in runs for c in r["per_category"]})
    headers = ["Category"] + [_run_label(r) for r in runs]
    rows = []
    for cat in cats:
        row = [cat]
        for r in runs:
            s = r["per_category"].get(cat)
            if not s:
                row.append("")
                continue
            n = s.get("pass", 0) + s.get("partial", 0) + s.get("fail", 0)
            row.append("%d/%d pass (%d partial, %d fail)"
                       % (s.get("pass", 0), n, s.get("partial", 0), s.get("fail", 0)))
        rows.append(row)
    return headers, rows


def footer_text(runs):
    graders = sorted({r["grader"] for r in runs}) or ["none on file"]
    return (
        "Grader version %s. Runs on file carry grader version: %s. "
        "Methodology: %s. Accuracy counts full passes only; partial means incomplete, "
        "not wrong. A search-grounded model's answers change week to week, so each row "
        "is a dated snapshot of one model with one configuration, not a permanent grade. "
        "Raw answers for every verdict are in the results files (%s)."
        % (GRADER_VERSION, ", ".join(graders), METHODOLOGY_URL, REPO_URL)
    )


def _text_table(headers, rows):
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join("%%-%ds" % w for w in widths)
    out = [fmt % tuple(headers), fmt % tuple("-" * w for w in widths)]
    out += [fmt % tuple(str(c) for c in row) for row in rows]
    return "\n".join(out)


def render_text(runs):
    h1, r1 = summary_rows(runs)
    h2, r2 = category_rows(runs)
    return "\n".join([
        "DIAMONDBENCH LEADERBOARD", "",
        _text_table(h1, r1), "",
        "Per category:", _text_table(h2, r2), "",
        footer_text(runs),
    ])


def build_app(results_dir=DEFAULT_RESULTS_DIR):
    import gradio as gr  # imported here so --print works without gradio installed

    runs = load_runs(results_dir)
    h1, r1 = summary_rows(runs)
    h2, r2 = category_rows(runs)
    with gr.Blocks(title="DiamondBench leaderboard") as demo:
        gr.Markdown(
            "# DiamondBench leaderboard\n"
            "How accurately AI answer engines respond to 47 buyer-phrased diamond and "
            "gemology questions, graded pass / partial / fail by a deterministic, public "
            "rule against a sourced answer key. Reading `%s`." % results_dir
        )
        gr.Dataframe(headers=h1, value=r1, interactive=False, label="Runs")
        gr.Markdown("## Per category")
        gr.Dataframe(headers=h2, value=r2, interactive=False, label="Per category")
        gr.Markdown("---\n" + footer_text(runs).replace(METHODOLOGY_URL,
                    "[METHODOLOGY.md](%s)" % METHODOLOGY_URL))
    return demo


def main():
    ap = argparse.ArgumentParser(description="DiamondBench leaderboard (local only)")
    ap.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR)
    ap.add_argument("--print", action="store_true", help="print the tables as text and exit")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    if a.print:
        print(render_text(load_runs(a.results_dir)))
        return
    demo = build_app(a.results_dir)
    demo.launch(server_name="127.0.0.1", server_port=a.port, share=False)


if __name__ == "__main__":
    main()
