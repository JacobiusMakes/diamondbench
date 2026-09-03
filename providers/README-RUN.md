# Grounded providers: stubs, the --providers plan, and the name check

Status on 2026-09-03: four provider stubs written in bench.py's style, none executed.
No request was sent to any of them while scaffolding, and no key value was read into
any file or output. The only offline check run is described under "Dry check".

## The four stubs

| name | module | key (env or .env) | endpoint | model / config | grounding | doc shape fetched |
| --- | --- | --- | --- | --- | --- | --- |
| `openai-web` | `openai_web_search.py` | `OPENAI_API_KEY` | `POST https://api.openai.com/v1/responses` | `gpt-5.6` | `tools: [{"type": "web_search"}]` | 2026-09-03 |
| `anthropic-web` | `anthropic_web_search.py` | `ANTHROPIC_API_KEY` | `POST https://api.anthropic.com/v1/messages` | `claude-opus-5` | `tools: [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]` | 2026-09-03 |
| `perplexity-sonar` | `perplexity_sonar.py` | `PERPLEXITY_API_KEY` | `POST https://api.perplexity.ai/v1/agent` | Agent API, `preset: low` (Perplexity picks the model; the response's model field is recorded) | built in | 2026-09-03 |
| `grok-live` | `grok_live_search.py` | `XAI_API_KEY` | `POST https://api.x.ai/v1/responses` | `grok-4.6` | `tools: [{"type": "web_search"}]` | 2026-09-03 |

Each `provider(question)` returns `{"text", "sources", "model"}`. `sources` is the list
of cited domains, de-duplicated, the same way the Gemini run records grounding sources.
Every stub raises `bench.ProviderNotConfigured` with a message naming the variable to
set before it builds a request. HTTP 429 raises `bench.QuotaExhausted`, so bench.py's
existing not_run handling applies.

Notes that came out of reading the docs:

- Perplexity: the docs say "Sonar Chat Completions is now Agent API. Sonar will be
  supported until September 27, 2026." The stub targets the Agent API for that reason
  and keeps the legacy `/v1/sonar` URL as a constant. With a preset, the model is chosen
  server-side, so the results file must take the model string from the response.
- Anthropic: `web_search_20260209` is the dynamic-filtering version for the Claude 4.6
  family and later; `web_search_20250305` is the basic version for older models. Web
  search is billed at $10 per 1,000 searches plus tokens (docs, 2026-09-03). No
  server-side fallback model is configured, because a fallback would misattribute the
  score; a refusal is recorded as an error for that question.
- xAI: "Live Search" (search_parameters on chat completions) is the older name; the
  current docs use the `web_search` tool on the Responses API and return a top-level
  `citations` list plus inline `url_citation` annotations.
- OpenAI: the web search guide's examples use `gpt-5.6`; citations arrive as
  `url_citation` annotations on the `output_text` content of the `message` item.
- Search pricing for OpenAI, Perplexity, and xAI was not verified here. Check before a
  full 47-question run, and run `--n 3` smoke tests before any full run.

## Dry check (no keys, no network)

```
python -c "from providers.registry import status; [print(s) for s in status()]"
```

prints the four names, their descriptions, key variable names, and whether a key is
present. To confirm the stubs fail closed, the scaffold check on 2026-09-03 patched
`read_key` to return None and called each `provider()`: all four raised
`ProviderNotConfigured` naming their variable, before any request was built. Nothing was
sent.

## Design note: a `--providers` flag for bench.py

bench.py takes one `--provider` and hardcodes the model field of the payload
(`GEMINI_MODEL if provider_name == "gemini" else "see provider stub"`) and the grounded
flag (`provider_name == "gemini"`). Adding the four grounded providers wants three small
changes, none of them in grading:

1. Merge the registry. In bench.py, after `PROVIDERS` is defined:
   `from providers.registry import PROVIDERS as EXTRA, MODULES; PROVIDERS.update(EXTRA)`.
   `--list-providers` gains the four rows through `registry.status()`.
2. Take model and grounding from the module. In `run()`, replace the two hardcoded
   expressions with a lookup: if `provider_name in MODULES`, use `MODULES[name].MODEL`
   and `MODULES[name].GROUNDED`; the Gemini branch stays as it is. Where a provider
   returns a `model` key (Perplexity's preset routing), prefer that string, so the file
   names the model that actually answered.
3. Accept `--providers a,b,c`. Loop `run()` once per name, in the order given, each
   writing its own `results/<name>-<date>.json`, so a quota failure on one provider never
   touches another's file. Keep `--provider` as a one-name alias. The leaderboard app
   already lists any results file with a summary block, so new providers appear without
   changes there.

Comparability: all four stubs are web-grounded, as the Gemini runs are, so their rows
can sit in the same table. Each is still a dated snapshot of one model with one
configuration; a re-run on another day can and will differ (METHODOLOGY.md, "Known
limits"). Ungrounded runs (the lm-eval harness path) stay in a separate table.

Rate and quota: keep `sleep_s` between questions, and expect Anthropic's `pause_turn`
continuation on long searches (handled in the stub, up to three continuations).

## Recorded name check (2026-09-03)

Nothing in this repository is titled "diamond benchmark" alone. Two web searches were
run to confirm who owns the nearby queries:

- Exact phrase "diamond benchmark": the results were IDEX Online's Diamond Retail
  Benchmark (a retail price benchmark for consumers), GPQA-Diamond (the 198-question
  expert science benchmark, via the EvalScope docs and an IntuitionLabs leaderboard
  page), Benchmark Rings' "Benchmark Diamonds" education page, and several USPTO patents
  on jewelry recommendation systems. In AI contexts that query belongs to GPQA-Diamond;
  in trade contexts, to IDEX. We do not compete for it.
- Exact phrase "DiamondBench": the results were DMT's "EdgeSharp DiamondBench Pro", a
  countertop knife and shear sharpener (Amazon, dmtsharp.com, KnifeCenter, Sharpening
  Supplies). No AI benchmark of that name surfaced, and this repository did not surface
  either, which is a reminder that discoverability rides on the subtitle.

House rule that follows: every title, card, YAML task name, and page in this repository
uses "DiamondBench" with the subtitle "AI answer-engine accuracy on diamond and gemology
questions" (or a shorter form that keeps "AI" and "gemology"), never the bare words
"diamond benchmark". The lm-eval task id is `diamondbench`, the Hub id is
`stienhardt/diamondbench` (fallback `JacobiusMakes/diamondbench`), and the price track is
"DiamondBench price staleness".
