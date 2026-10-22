#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/check-price-drift.py, the nightly price drift check (truthful costs, TC10).

The fixtures in price-drift-fixtures/ are excerpts of the three catalogs as fetched on
2026-10-22, when all six rows agreed. Each case changes one thing and checks the findings, the
issue body and the issue action. main() runs with the network and gh stubbed: nothing here leaves
the machine.

Run: python3 scripts/ci/tests/test-check-price-drift.py
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
from datetime import date
from decimal import Decimal

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("check_price_drift", ROOT / "scripts/ci/check-price-drift.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FIX = pathlib.Path(__file__).resolve().parent / "price-drift-fixtures"
FILES = {"genai-prices": "genai-prices.json", "LiteLLM": "litellm.json", "models.dev": "models-dev.json"}
TODAY = date(2026, 10, 22)
ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
# meter.prices on 2026-10-22.
TABLE = {
    "glm-5.3": {"input": 1.40, "cacheRead": 0.26, "output": 4.40},
    "glm-5.3-flashx": {"input": 0.37, "cacheRead": 0.075, "output": 1.25},
    "glm-5.3-flash": {"input": 0.15, "cacheRead": 0.03, "output": 0.50},
    "claude-opus-5-5": {"input": 4.00, "cacheRead": 0.20, "cacheWrite": 5.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cacheRead": 0.10, "cacheWrite": 2.50, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.50, "cacheRead": 0.05, "cacheWrite": 0.625, "output": 2.50},
}
FAILURES = []


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def configmap(table):
    values = yaml.safe_dump({"config": {"meter": {"prices": table}}})
    return yaml.safe_dump({"apiVersion": "v1", "kind": "ConfigMap", "data": {"values.yaml": values}})


def prices(table=TABLE):
    return gen.load_prices(configmap(table))


def catalogs():
    """A fresh copy of each fixture, parsed as the script parses a catalog."""
    return {name: gen.parse_catalog(name, (FIX / f).read_text()) for name, f in FILES.items()}


def genai_model(cats, provider, model):
    p = next(p for p in cats["genai-prices"] if p["id"] == provider)
    return next(m for m in p["models"] if m["id"] == model)


def findings(cats=None, table=TABLE, today=TODAY, **kw):
    return gen.compare(prices(table), cats or catalogs(), today, **kw)


def summary(fs):
    return [(f.model, f.catalog, f.field, f.ours, f.theirs) for f in fs]


# --- The comparison ---
got = findings()
check("today's fixtures agree: no finding (zhipuai and zai-coding-plan are not read)", got == [], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("2e-07")
got = findings(cats)
check("Sonnet 5.5's cache read at 0.20 is one finding",
      got == [gen.Finding("claude-sonnet-5-5", "LiteLLM", "cacheRead", "0.10", "0.20", "claude-sonnet-5-5",
                          ANTHROPIC)], str(got))
SONNET = got

cats = catalogs()
del cats["models.dev"]["anthropic"]["models"]["claude-opus-5-5"]
got = findings(cats)
check("a row a catalog lacks is one finding",
      summary(got) == [("claude-opus-5-5", "models.dev", "—", "—", "not listed")]
      and got[0].key == "anthropic/claude-opus-5-5", str(got))

got = findings(tiers={})
check("Haiku's tier: without it, each catalog's base rate differs on all four fields",
      len(got) == 12 and {f.model for f in got} == {"claude-haiku-5-5"}
      and ("claude-haiku-5-5", "genai-prices", "input", "0.50", "0.10") in summary(got), str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["zai/glm-5.3"]["cache_creation_input_token_cost"] = Decimal("1.68e-06")
got = findings(cats)
check("Z.ai's absent cacheWrite agrees with 0 and absent, not with a price",
      summary(got) == [("glm-5.3", "LiteLLM", "cacheWrite", "absent", "1.68")], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["zai/glm-5.3-flashx"] = dict(cats["LiteLLM"]["tencent/glm-5.3-flashx"], litellm_provider="zai")
got = findings(cats)
check("a declared absence that gets listed is one finding",
      summary(got) == [("glm-5.3-flashx", "LiteLLM", "—", "—", "listed now: drop its ABSENT entry")],
      str(summary(got)))

got = findings(table={**TABLE, "glm-6": {"input": 1.0, "cacheRead": 0.2, "output": 4.0}})
check("a row the mapping lacks is one finding per catalog",
      summary(got) == [("glm-6", c, "—", "—", "not in the mapping")
                       for c in ("LiteLLM", "genai-prices", "models.dev")], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("2e-07")
accepted = {("claude-sonnet-5-5", "LiteLLM", "cacheRead"): ("0.20", "LiteLLM lags; the provider's page says 0.10")}
check("an accepted deviation at its accepted value is no finding", findings(cats, accepted=accepted) == [])
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("3e-07")
check("an accepted deviation at another value is a finding again",
      summary(findings(cats, accepted=accepted)) == [("claude-sonnet-5-5", "LiteLLM", "cacheRead", "0.10", "0.30")])

cats = catalogs()
cats["models.dev"]["zai"]["models"]["glm-5.3-flashx"]["cost"]["cache_read"] = Decimal("0.07504")
check("equal to 4 decimals: 0.07504 agrees with 0.075", findings(cats) == [])
cats["models.dev"]["zai"]["models"]["glm-5.3-flashx"]["cost"]["cache_read"] = Decimal("0.07505")
check("0.07505 rounds to 0.0751 and differs",
      summary(findings(cats)) == [("glm-5.3-flashx", "models.dev", "cacheRead", "0.075", "0.0751")])

got = findings(today=date(2026, 9, 5))
check("genai-prices' dated prices: before 2026-09-10 the GLM-5.3-Flash promotion is in force",
      summary(got) == [("glm-5.3-flash", "genai-prices", "input", "0.15", "0.075"),
                       ("glm-5.3-flash", "genai-prices", "cacheRead", "0.03", "0.015"),
                       ("glm-5.3-flash", "genai-prices", "output", "0.50", "0.25")], str(summary(got)))

cats = catalogs()
genai_model(cats, "anthropic", "claude-opus-5-5")["prices"]["cache_read_mtok"] = Decimal("0.25")
opus = {**TABLE["claude-opus-5-5"], "source": "https://example.test/opus"}
got = findings(cats, table={**TABLE, "claude-opus-5-5": opus})
check("the row's source wins over the mapping's page",
      [f.source for f in got] == ["https://example.test/opus"], str(got))

for name, what, mutate in [
    ("genai-prices", "a genai-prices that is not a list",
     lambda c: c.__setitem__("genai-prices", {"providers": []})),
    ("LiteLLM", "a LiteLLM price that is a string",
     lambda c: c["LiteLLM"]["zai/glm-5.3"].__setitem__("input_cost_per_token", "1.4e-06")),
    ("genai-prices", "a genai-prices dated price with a malformed start_date",
     lambda c: genai_model(c, "zai", "GLM-5.3-Flash")["prices"][1]["constraint"].__setitem__(
         "start_date", "soon")),
    ("models.dev", "a models.dev that is not an object", lambda c: c.__setitem__("models.dev", [])),
    # genai-prices' frozen v1 file would read so: no 5.5 model, no zai provider.
    ("models.dev", "a catalog listing none of the rows",
     lambda c: c.__setitem__("models.dev", {"opencode": {"models": {}}})),
]:
    cats = catalogs()
    mutate(cats)
    try:
        gen.compare(prices(), cats, TODAY)
        check(f"{what} is refused", False, "no CatalogError")
    except gen.CatalogError as e:
        check(f"{what} is refused", str(e).startswith(name), str(e))

try:
    gen.parse_catalog("LiteLLM", "<html>rate limited</html>")
    check("a catalog that is not JSON is refused", False, "no CatalogError")
except gen.CatalogError as e:
    check("a catalog that is not JSON is refused", str(e).startswith("LiteLLM: not JSON"), str(e))

real = gen.load_prices((ROOT / gen.VALUES).read_text())
check("the real tree's meter.prices loads, every row with an input and an output",
      bool(real) and all(r.get("input", 0) > 0 and r.get("output", 0) > 0 for r in real.values()), str(real))

# --- The issue ---
body = gen.issue_body(SONNET)
row = (f"| `claude-sonnet-5-5` | cacheRead | 0.10 | 0.20 | [LiteLLM]({gen.CATALOGS['LiteLLM']}) "
       f"`claude-sonnet-5-5` | {ANTHROPIC} |")
check("the body names model, field, ours, theirs, catalog and source", row in body.splitlines(), body)
check("the body says closing the issue by hand silences nothing; ACCEPTED or ABSENT does",
      "Closing it by hand silences nothing" in body and "`ACCEPTED`" in body and "`ABSENT`" in body, body)
check("the same findings twice give the same body", gen.issue_body(list(SONNET)) == body)
check("clean, no issue: nothing", gen.issue_action([], None) == ("nothing", None))
check("clean, an open issue: close", gen.issue_action([], {"number": 7, "body": body}) == ("close", None))
check("findings, no issue: open", gen.issue_action(SONNET, None) == ("open", body))
check("findings, the same body: nothing",
      gen.issue_action(SONNET, {"number": 7, "body": body.replace("\n", "\r\n")}) == ("nothing", None))
check("findings, another body: update", gen.issue_action(SONNET, {"number": 7, "body": "old"}) == ("update", body))


# --- gh's own error reaches the job log ---
# A fake gh on PATH fails the way gh does. The real gh() must neither swallow its stderr nor hide the exit.
real_gh = gen.gh
with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryFile() as err:
    fake = pathlib.Path(tmp) / "gh"
    fake.write_text("#!/bin/sh\necho 'HTTP 403: Resource not accessible by integration' >&2\necho out\nexit 1\n")
    fake.chmod(0o755)
    old_path, saved = os.environ["PATH"], os.dup(2)
    os.environ["PATH"] = f"{tmp}:{old_path}"
    os.dup2(err.fileno(), 2)
    try:
        real_gh("issue", "create")
        failed = False
    except subprocess.CalledProcessError:
        failed = True
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.environ["PATH"] = old_path
    err.seek(0)
    shown = err.read().decode()
check("a failing gh call still raises", failed)
check("a failing gh call's stderr reaches the job log", "HTTP 403: Resource not accessible" in shown, shown)


# --- main(), with the network and gh stubbed ---
def run_main(table, fetched, open_issues):
    calls = []

    def fetch(url):
        name = next(n for n, u in gen.CATALOGS.items() if u == url)
        v = fetched[name]
        if isinstance(v, Exception):
            raise v
        return v

    def gh(*args, stdin=None):
        calls.append((args, stdin))
        return open_issues if args[:2] == ("issue", "list") else ""

    with tempfile.TemporaryDirectory() as tmp:
        values = pathlib.Path(tmp) / gen.VALUES
        values.parent.mkdir(parents=True)
        values.write_text(configmap(table))
        gen.fetch, gen.gh = fetch, gh
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = gen.main([tmp])
    return code, calls, out.getvalue()


texts = {name: (FIX / f).read_text() for name, f in FILES.items()}
code, calls, out = run_main(TABLE, {**texts, "models.dev": urllib.error.URLError("timed out")}, "[]")
check("an unreachable catalog fails the run, names it and its URL, and calls no gh",
      code == 1 and calls == [] and "left alone" in out
      and f"models.dev ({gen.CATALOGS['models.dev']}): " in out, out)
code, calls, out = run_main(TABLE, {**texts, "genai-prices": urllib.error.HTTPError(
    gen.CATALOGS["genai-prices"], 429, "Too Many Requests", {}, None)}, "[]")
check("a rate-limited catalog is named too", code == 1 and calls == [] and "genai-prices (" in out
      and "429" in out, out)
code, calls, out = run_main(TABLE, {**texts, "LiteLLM": "<html>"}, "[]")
check("an unparseable catalog fails the run and calls no gh", code == 1 and calls == [], out)

drift = {**TABLE, "claude-sonnet-5-5": {**TABLE["claude-sonnet-5-5"], "cacheRead": 0.20}}
code, calls, out = run_main(drift, texts, "[]")
verbs = [a[:2] for a, _ in calls]
check("drift with no open issue: list, label, create",
      code == 0 and verbs == [("issue", "list"), ("label", "create"), ("issue", "create")]
      and "--label" in calls[2][0] and gen.LABEL in calls[2][0] and "| cacheRead | 0.20 | 0.10 |" in calls[2][1],
      f"{code} {calls}")
code, calls, out = run_main(TABLE, texts, '[{"number": 9, "body": "x"}, {"number": 7, "body": "y"}]')
check("clean with an open issue: the oldest is closed",
      code == 0 and [a for a, _ in calls][1:] == [("issue", "close", "7", "--comment", gen.CLOSING)], f"{code} {calls}")

print("all passed" if not FAILURES else f"{len(FAILURES)} failed: {FAILURES}")
sys.exit(1 if FAILURES else 0)
