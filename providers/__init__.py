"""Grounded answer-engine provider stubs, in bench.py's provider style.

Each module in this package exposes

    provider(question) -> {"text": str, "sources": [domain, ...], "model": str}
    MODEL, KEY_NAME, GROUNDED, DESCRIPTION

and raises ProviderNotConfigured (bench.py's exception) with a plain message when its
key is missing, before any request is built. Keys are read from the environment or a
local .env through bench.read_key(), exactly as the Gemini provider does. Nothing here is
wired into bench.py yet and none of these providers has been run; README-RUN.md has the
plan for a --providers flag and the record of what was checked on 2026-09-03.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

try:
    from bench import ProviderNotConfigured, QuotaExhausted, read_key, PROMPT
except ImportError:  # the folder was copied away from bench.py; keep the same contract
    class ProviderNotConfigured(Exception):
        pass

    class QuotaExhausted(Exception):
        pass

    PROMPT = "%s Answer as you would for a shopper."

    def read_key(name):
        val = os.environ.get(name, "").strip()
        if val:
            return val
        try:
            for line in io.open(os.path.join(REPO, ".env"), encoding="utf-8-sig"):
                if line.strip().startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip()
        except OSError:
            pass
        return None


def require_key(name, label):
    """The key, or ProviderNotConfigured with a message that says what to set."""
    key = read_key(name)
    if not key:
        raise ProviderNotConfigured(
            "%s not found. Set it in the environment or a local .env to run the %s "
            "provider. No request was sent." % (name, label))
    return key


def post_json(url, body, headers, label, timeout=180):
    """POST a JSON body, return the parsed JSON reply. 429 raises QuotaExhausted so
    bench.py marks the remaining questions not_run instead of inventing verdicts."""
    all_headers = {"Content-Type": "application/json"}
    all_headers.update(headers)
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        if e.code == 429:
            raise QuotaExhausted("%s quota or rate limit hit (HTTP 429): %s" % (label, detail))
        raise RuntimeError("%s HTTP %d: %s" % (label, e.code, detail))


def domain(url):
    """Registered host of a URL without a leading www., matching how the Gemini run
    records grounding sources (gia.edu, wikipedia.org)."""
    try:
        host = urllib.parse.urlsplit(url or "").hostname or ""
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def add_source(sources, url):
    d = domain(url)
    if d and d not in sources:
        sources.append(d)
