"""Registry of the grounded provider stubs, in the shape of bench.py's PROVIDERS dict,
plus the per-provider model and grounding metadata a --providers flag will need.

    from providers.registry import PROVIDERS, MODULES, status

PROVIDERS maps a name to (callable, description), the same tuple shape bench.PROVIDERS
uses, so bench.py can merge it in without touching grading. MODULES maps the same names
to the modules, which carry MODEL, KEY_NAME, and GROUNDED for the results payload.
Nothing here calls any network.
"""
from . import read_key
from . import anthropic_web_search, grok_live_search, openai_web_search, perplexity_sonar

MODULES = {
    "openai-web": openai_web_search,
    "anthropic-web": anthropic_web_search,
    "perplexity-sonar": perplexity_sonar,
    "grok-live": grok_live_search,
}

PROVIDERS = {name: (m.provider, m.DESCRIPTION) for name, m in MODULES.items()}


def status():
    """[(name, description, key name, note)] for a --list-providers listing. Reports only
    whether a key is present, never its value."""
    out = []
    for name in sorted(MODULES):
        m = MODULES[name]
        note = "key found" if read_key(m.KEY_NAME) else "set the key to run this model"
        out.append((name, m.DESCRIPTION, m.KEY_NAME, note))
    return out


if __name__ == "__main__":
    for name, desc, key_name, note in status():
        print("  %-17s %-70s %-20s [%s]" % (name, desc, key_name, note))
