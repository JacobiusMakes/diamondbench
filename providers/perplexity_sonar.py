"""Perplexity, the Sonar answer engine.

STUB, not yet run. The file keeps the "sonar" name from the plan, but it targets the
Agent API, because Perplexity's docs (fetched 2026-09-03) say: "Sonar Chat Completions
is now Agent API. Sonar will be supported until September 27, 2026." The Agent API is
POST https://api.perplexity.ai/v1/agent with {"preset": "...", "input": "..."}; the
answer comes back in an "output" array as items of type "message" (content items with
"text" and url "annotations") and type "search_results" (results with url, title,
snippet, date). The legacy endpoint the same docs show is POST
https://api.perplexity.ai/v1/sonar with {"model": "sonar", "messages": [...]} and
top-level "citations" / "search_results"; it is kept below as a constant only.

The Agent API chooses the model for a preset, so the "model" field of a results file
must come from the response when it is present; the constant MODEL below names the
configuration, not a model.
"""
from . import PROMPT, add_source, post_json, require_key

KEY_NAME = "PERPLEXITY_API_KEY"
URL = "https://api.perplexity.ai/v1/agent"
LEGACY_SONAR_URL = "https://api.perplexity.ai/v1/sonar"   # supported until 2026-09-27 per docs
PRESET = "low"
MODEL = "perplexity-agent-api/preset=%s" % PRESET
GROUNDED = True
DESCRIPTION = "STUB, not yet run: Perplexity Agent API, preset %s (successor to Sonar)" % PRESET


def provider(question):
    key = require_key(KEY_NAME, "perplexity-sonar")
    body = {"preset": PRESET, "input": PROMPT % question}
    d = post_json(URL, body, {"Authorization": "Bearer " + key}, "Perplexity")
    text, sources = [], []
    for item in d.get("output") or []:
        t = item.get("type")
        if t == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("text"):
                    text.append(c["text"])
                    for a in c.get("annotations") or []:
                        add_source(sources, a.get("url"))
        elif t == "search_results":
            for r in item.get("results") or []:
                add_source(sources, r.get("url"))
    return {"text": " ".join(text), "sources": sources, "model": d.get("model") or MODEL}
