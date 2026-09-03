"""Anthropic Messages API with the web_search server tool.

STUB, not yet run. Raw HTTP on purpose: bench.py is standard-library only. Shape from
https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool (fetched
2026-09-03): POST https://api.anthropic.com/v1/messages with headers x-api-key and
anthropic-version: 2023-06-01, and tools [{"type": "<web_search version>", "name":
"web_search", "max_uses": 5}]. The reply's content blocks carry the answer ("text"
blocks, each with optional "citations" of type web_search_result_location that name a
url) and the searches ("web_search_tool_result" blocks whose content is a list of
web_search_result objects with url and title; a dict there is an error object, not a
result).

Tool version: web_search_20260209 (dynamic filtering) on the Claude 4.6 family and
later, including claude-opus-5. For older models use web_search_20250305.

No server-side fallbacks parameter, on purpose: a fallback would answer with a different
model and the results file would misattribute the score. A stop_reason of "refusal" is
raised, so bench.py records an error for that question rather than a verdict.
"""
import json

from . import PROMPT, add_source, post_json, require_key

KEY_NAME = "ANTHROPIC_API_KEY"
MODEL = "claude-opus-5"
TOOL_TYPE = "web_search_20260209"
GROUNDED = True
URL = "https://api.anthropic.com/v1/messages"
MAX_TOKENS = 16000          # thinking and the answer share this budget; do not lowball it
MAX_USES = 5
MAX_CONTINUATIONS = 3       # pause_turn continuations before giving up
DESCRIPTION = "STUB, not yet run: Anthropic Messages API (%s) with the %s tool" % (MODEL, TOOL_TYPE)


def provider(question):
    key = require_key(KEY_NAME, "anthropic-web")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    messages = [{"role": "user", "content": PROMPT % question}]
    text, sources = [], []
    d = {}
    for _ in range(MAX_CONTINUATIONS + 1):
        body = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
            "tools": [{"type": TOOL_TYPE, "name": "web_search", "max_uses": MAX_USES}],
        }
        d = post_json(URL, body, headers, "Anthropic")
        for block in d.get("content") or []:
            t = block.get("type")
            if t == "text":
                text.append(block.get("text", ""))
                for c in block.get("citations") or []:
                    add_source(sources, c.get("url"))
            elif t == "web_search_tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    for r in content:
                        if isinstance(r, dict):
                            add_source(sources, r.get("url"))
        stop = d.get("stop_reason")
        if stop == "refusal":
            raise RuntimeError("Anthropic returned stop_reason=refusal (%s); recorded as an "
                               "error, not a verdict" % json.dumps(d.get("stop_details")))
        if stop == "pause_turn":
            # A long search turn was paused. Per the docs, send the assistant message back
            # unchanged and let it continue.
            messages = messages + [{"role": "assistant", "content": d.get("content") or []}]
            continue
        break
    return {"text": " ".join(t for t in text if t), "sources": sources,
            "model": d.get("model") or MODEL}
