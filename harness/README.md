# DiamondBench for lm-evaluation-harness

This folder registers DiamondBench as a task in
[EleutherAI's lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness),
reusing the exact grader from `bench.py` so a harness verdict and a bench.py verdict are
the same verdict.

| file | purpose |
| --- | --- |
| `diamondbench.yaml` | the task config: dataset on the Hub, the shopper prompt, `generate_until`, the custom metric |
| `diamondbench_metric.py` | `process_results()` that calls `bench.grade()` (embedded copy as fallback) and returns accuracy / pass / partial / fail |
| `README.md` | this file, including the filled-out Task Validity Checklist |

## Run it

From the repository root, with `lm_eval` installed (`pip install lm-eval`):

```
lm_eval --model hf \
    --model_args pretrained=<hub-model-id> \
    --tasks diamondbench \
    --include_path ./harness \
    --apply_chat_template \
    --output_path results/lm_eval \
    --log_samples
```

Notes on that command:

- `--include_path ./harness` is how the harness finds a task YAML that does not live in
  its own `lm_eval/tasks` tree. `--tasks ./harness/diamondbench.yaml` is also accepted.
- `--apply_chat_template` sends the prompt as a user turn, which is how a shopper talks
  to an assistant. Without it a base model sees a bare string.
- `--log_samples` writes every generated answer next to its per-question metrics, which
  is the same auditability rule `bench.py` follows: no verdict without the raw answer.
- The dataset ships as one `questions.jsonl`, which the `datasets` library exposes as the
  `train` split; the YAML sets `test_split: train` for that reason. Nothing is trained on
  it.
- `generation_kwargs.until` is set to end-of-text markers on purpose. If it were left out
  the harness would stop at a blank line (its fewshot delimiter) and grade a truncated
  answer.
- Dataset id: `stienhardt/diamondbench`, with `JacobiusMakes/diamondbench` as the
  fallback if the organization id is unavailable; change `dataset_path` if so.
- Any other lm-eval backend works the same way (for example
  `--model openai-chat-completions --model_args model=<model>` or
  `--model anthropic-chat --model_args model=<model>`); only `--model` and
  `--model_args` change.

## Verify the metric offline

No model, no key:

```
python harness/diamondbench_metric.py --selftest
```

It re-grades every stored run in `results/` through `process_results()` and confirms the
verdicts match the ones in the results files (45 pass / 2 partial / 0 fail for both the
2026-07-13 and 2026-09-02 Gemini runs), and, when `bench.py` is importable, that the
embedded fallback copy of the grader agrees with `bench.grade()` on every stored answer.

## Comparability caveat (read before putting numbers in one table)

A harness run measures a model's parametric knowledge: no web search, no grounding. The
published DiamondBench runs in `results/` are search-grounded (Gemini with Google Search
grounding), which is a proxy for how an AI answer engine behaves for a shopper. Those are
two different measurements. Report harness scores in their own table, labeled
"ungrounded", and do not mix them with grounded runs without saying so. See
`METHODOLOGY.md`, "Provider comparability".

## Metrics

`process_results` returns four per-document values, each aggregated by mean:

| metric | meaning |
| --- | --- |
| `accuracy` | 1 if the answer fully passes, else 0. The headline number, identical to `accuracy_pct` in `results/` |
| `pass` | same as accuracy, kept so the three verdict rates sit side by side |
| `partial` | 1 if incomplete but nothing wrong was asserted |
| `fail` | 1 if at least one wrong claim was asserted |

Grading rule, deterministic: fail if any `must_not_include` phrase is asserted (negation
guard applies); pass if every `must_include` slot is satisfied; partial otherwise. The
full rule and its known limits are in `METHODOLOGY.md`.

## Task Validity Checklist

Quoted from the harness's
[new task guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/new_task_guide.md)
(fetched 2026-09-03), with DiamondBench's answers under each item.

> For adding novel benchmarks/datasets to the library:
>
> - [ ] Is the task an existing benchmark in the literature?

Answer: not in peer-reviewed literature. It is a published open benchmark: the
[DiamondBench repository](https://github.com/JacobiusMakes/diamondbench) (July 2026,
MIT), with `METHODOLOGY.md` as the written specification and two dated, audited runs.

>   - [ ] Have you referenced the original paper that introduced the task?

Answer: there is no paper. The reference is the repository and its `METHODOLOGY.md`;
both are linked from the task YAML header and this README.

>   - [ ] If yes, does the original paper provide a reference implementation? If so, have you checked against the reference implementation and documented how to run such a test?

Answer: yes, the reference implementation is `bench.py` in the same repository, and this
task calls its `grade()` directly rather than re-implementing it.
`python harness/diamondbench_metric.py --selftest` is the check: it re-grades the stored
runs through the harness metric and confirms identical verdicts.

> If other tasks on this dataset are already supported:
>
> - [ ] Is the "Main" variant of this task clearly denoted?

Answer: `diamondbench` is the only variant and therefore the main one.

> - [ ] Have you provided a short sentence in a README on what each new variant adds / evaluates?

Answer: one variant: 47 buyer-phrased diamond and gemology questions, zero-shot, graded
pass / partial / fail by a deterministic keyword rule with a negation guard.

> - [ ] Have you noted which, if any, published evaluation setups are matched by this variant?

Answer: it matches the `bench.py` setup (same prompt wrapper, same grader, same answer
key, grader version 2026-09-02) except for grounding: the published runs are
search-grounded, a harness run is not. See the comparability caveat above.

The guide also asks that a new task folder carry a filled-out copy of this checklist in
its README, which is what this section is.
