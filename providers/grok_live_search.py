"""xAI Grok with web search.

STUB, not yet run. "Live Search" was the earlier name for this (search_parameters on
chat completions). The current docs (https://docs.x.ai/developers/tools/web-search and
the citations page, fetched 2026-09-03) use the web_search tool on the Responses API:
POST https://api.x.ai/v1/responses with {"model": "grok-4.6", "input": [{"role":
"user", "content": "..."}], "tools": [{"type": "web_search"}]}. Citations come two ways:
a top-level "citations" list of URLs for every source encountered, and "url_citation"
annotations (url, title, start_index, end_index) on the "output_text" content of the
"message" output item. Inline citations are on by default.
"""
from . import PROMPT, add_source, post_json, require_key

KEY_NAME = "XAI_API_KEY"
MODEL = "grok-4.6"
GROUNDED = True
URL = "https://api.x.ai/v1/responses"
DESCRIPTION = "STUB, not yet run: xAI Responses API (%s) with the web_search tool" % MODEL


def provider(question):
    key = require_key(KEY_NAME, "grok-live")
    body = {
        "model": MODEL,
        "input": [{"role": "user", "content": PROMPT % question}],
        "tools": [{"type": "web_search"}],
    }
    d = post_json(URL, body, {"Authorization": "Bearer " + key}, "xAI")
    text, sources = [], []
    for item in d.get("output") or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if c.get("type") == "output_text":
                text.append(c.get("text", ""))
                for a in c.get("annotations") or []:
                    if a.get("type") == "url_citation":
                        add_source(sources, a.get("url"))
    for u in d.get("citations") or []:
        add_source(sources, u)
    return {"text": " ".join(t for t in text if t), "sources": sources,
            "model": d.get("model") or MODEL}
