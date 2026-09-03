# DiamondBench leaderboard (local)

A minimal Gradio page over `results/*.json`: one row per run (run date, model,
grounded, pass, partial, fail, accuracy), a per-category breakdown, and a footer with
the grader version and a link to `METHODOLOGY.md`. It reads the summary blocks that
`bench.py` wrote (or `regrade.py` re-derived); it never re-grades.

Local run only; the app binds to 127.0.0.1 and never opens a share link.

```
pip install -r leaderboard/requirements.txt
python leaderboard/app.py            # open http://127.0.0.1:7860
python leaderboard/app.py --print    # the same tables as plain text; no gradio needed
python leaderboard/app.py --results-dir path/to/other/results
```

Any results file with a `summary` and `results` block appears automatically, so a new
provider run shows up the moment `bench.py` writes it. Ungrounded runs are labeled in the
per-category header; do not compare them with grounded runs without saying so (see
`METHODOLOGY.md`, "Provider comparability").
