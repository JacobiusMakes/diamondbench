"""OpenAI Responses API with the built-in web_search tool.

STUB, not yet run. Written to the shape documented at
https://developers.openai.com/api/docs/guides/tools-web-search (fetched 2026-09-03):
POST https://api.openai.com/v1/responses with tools [{"type": "web_search"}]; the answer
is the output item of type "message", whose "output_text" content carries the text and
"url_citation" annotations (url, title, start_index, end_index).
"""
from . import PROMPT, add_source, post_json, require_key

KEY_NAME = "OPENAI_API_KEY"
MODEL = "gpt-5.6"          # the model the web search guide uses in its examples
GROUNDED = True
URL = "https://api.openai.com/v1/responses"
DESCRIPTION = "STUB, not yet run: OpenAI Responses API (%s) with the web_search tool" % MODEL


def provider(question):
    key = require_key(KEY_NAME, "openai-web")
    body = {
        "model": MODEL,
        "tools": [{"type": "web_search"}],
        "input": PROMPT % question,
    }
    d = post_json(URL, body, {"Authorization": "Bearer " + key}, "OpenAI")
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
    return {"text": " ".join(t for t in text if t), "sources": sources,
            "model": d.get("model") or MODEL}
