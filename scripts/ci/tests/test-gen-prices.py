#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/gen-prices.py, which renders the llm-gateway-prices group and the agentgateway
model catalog overlay (ConfigMap agent-model-catalog) from meter.prices.

Each case copies the real factory values and price rule into a temporary root, changes one thing and
runs the generator there: the rendering holds the design's charges, it rebuilds the group byte for
byte, a hand edit or a price changed without --write fails with the diff, and each malformed row is
refused, by name, without a write.

Run: python3 scripts/ci/tests/test-gen-prices.py
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import shutil
import sys
import tempfile
from decimal import Decimal

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen_prices", ROOT / "scripts/ci/gen-prices.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FAILURES = []
# The truthful costs design, "The charge series": input, output, cached_input, cache_creation_input.
DESIGN = {
    "glm-5.3": ("1.40", "4.40", "-1.14", "0.00"),
    "glm-5.3-flashx": ("0.37", "1.25", "-0.295", "0.00"),
    "glm-5.3-flash": ("0.15", "0.50", "-0.12", "0.00"),
    "claude-opus-5-5": ("4.00", "20.00", "-3.80", "1.00"),
    "claude-sonnet-5-5": ("2.00", "10.00", "-1.90", "0.50"),
    "claude-haiku-5-5": ("0.50", "2.50", "-0.45", "0.125"),
}
PROVENANCE_Z = 'source: "https://docs.z.ai/guides/overview/pricing", checkedAt: "2026-10-16"'
PROVENANCE_A = 'source: "https://platform.claude.com/docs/en/about-claude/pricing", checkedAt: "2026-10-16"'
HAIKU = f"claude-haiku-5-5: {{input: 0.50, cacheRead: 0.05, cacheWrite: 0.625, output: 2.50, {PROVENANCE_A}}}"
FLASH = f"glm-5.3-flash: {{input: 0.15, cacheRead: 0.03, output: 0.50, {PROVENANCE_Z}}}"


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def run(root, *flags):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = gen.main(["gen-prices.py", *flags, str(root)])
    return code, out.getvalue()


@contextlib.contextmanager
def tree():
    """A temporary root holding copies of the factory values and the price rule, the group rendered."""
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for rel in (gen.VALUES, gen.RULES, gen.CATALOG, gen.PARAMETERS):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, root / rel)
        run(root, "--write")
        yield root


def rules(root):
    return root / gen.RULES


def catalog(root):
    """(the ConfigMap, the catalog.json it holds parsed) from the tree's rendered overlay."""
    cm = yaml.safe_load((root / gen.CATALOG).read_text())
    return cm, json.loads(cm["data"]["catalog.json"])


def replace(root, rel, old, new):
    path = root / rel
    text = path.read_text()
    assert text.count(old) == 1, f"{rel}: {old!r} found {text.count(old)} times"
    path.write_text(text.replace(old, new))


def charges_in(root):
    """{model: (input, output, cached_input, cache_creation_input)} as the file's group holds them."""
    group = next(g for g in gen.groups_of(rules(root).read_text()) if g["name"] == gen.GROUP)
    got = {}
    for r in group["rules"]:
        assert r["record"] == gen.RECORD and r["expr"].startswith("vector(")
        got.setdefault(r["labels"]["gen_ai_request_model"], {})[r["labels"]["gen_ai_token_type"]] = r["expr"][7:-1]
    return {m: tuple(t.get(k) for k in gen.TYPES) for m, t in got.items()}, len(group["rules"])


def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves the rule file alone."""
    with tree() as t:
        change(t)
        before = rules(t).read_text()
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and rules(t).read_text() == before, out)


def row(old, new):
    """A tree change that rewrites one meter.prices row."""
    return lambda t: replace(t, gen.VALUES, old, new)


print("the rendering (design offline proof 2)")
with tree() as t:
    got, n = charges_in(t)
    check("four rows per model, in meter.prices' order, at the design's charges",
          got == DESIGN and list(got) == list(DESIGN) and n == 24, str(got))
    text = rules(t).read_text()
    check("no glm-5.2 and no llm_gateway:price_usd_per_mtoken",
          "glm-5.2" not in text and "price_usd_per_mtoken" not in text)
check("exact decimals: 0.26 - 1.40 is -1.14, not float noise",
      gen.usd(Decimal("0.26") - Decimal("1.40")) == "-1.14" and gen.usd(Decimal("20")) == "20.00"
      and gen.usd(Decimal("0.625") - Decimal("0.50")) == "0.125" and gen.usd(Decimal("1.4") - Decimal("1.40")) == "0.00")
check("a write the provider does not bill is charged as input",
      gen.charges({"input": 1.4, "cacheRead": 0.26, "output": 4.4})["cache_creation_input"] == 0)

print("the catalog overlay (cost cross-check design, offline proof 1)")
with tree() as t:
    cm, cat = catalog(t)
    check("a ConfigMap agent-model-catalog in agent-gateway holding catalog.json",
          cm["kind"] == "ConfigMap" and cm["metadata"] == {"name": "agent-model-catalog", "namespace": "agent-gateway"}
          and list(cm["data"]) == ["catalog.json"], str(cm["metadata"]))
    anthropic = cat["providers"]["anthropic"]["models"]
    zai = cat["providers"]["zai"]["models"]
    check("six rows: Anthropic under anthropic, GLM under zai, nothing else",
          list(cat["providers"]) == ["anthropic", "zai"] and list(anthropic) == [
              "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"] and list(zai) == [
              "glm-5.3", "glm-5.3-flashx", "glm-5.3-flash"], str(cat))
    check("the rates are the table's values as strings, USD per million",
          anthropic["claude-opus-5-5"] == {"rates": {"input": "4.00", "output": "20.00", "cacheRead": "0.20", "cacheWrite": "5.00"}}
          and anthropic["claude-haiku-5-5"]["rates"] == {"input": "0.50", "output": "2.50", "cacheRead": "0.05", "cacheWrite": "0.625"},
          str(anthropic))
    check("GLM has no cacheWrite: an absent column stays absent",
          all("cacheWrite" not in m["rates"] for m in zai.values())
          and zai["glm-5.3"]["rates"] == {"input": "1.40", "output": "4.40", "cacheRead": "0.26"}, str(zai))
    check("provenance is never rendered into the catalog",
          "source" not in (t / gen.CATALOG).read_text() and "checkedAt" not in (t / gen.CATALOG).read_text())
with tree() as t:
    path = t / gen.CATALOG
    path.write_text(path.read_text().replace('"output": "20.00"', '"output": "21.00"'))
    code, out = run(t)
    check("a hand edit to catalog.json fails, with the diff and the fix",
          code == 1 and '-                "output": "21.00"' in out and '+                "output": "20.00"' in out and "--write" in out, out)
    code, out = run(t, "--write")
    check("--write restores it", code == 0 and run(t)[0] == 0, out)
with tree() as t:
    replace(t, gen.VALUES, HAIKU, HAIKU + "\n          claude-mythos-5: {input: 25.00, cacheRead: 2.50, cacheWrite: 31.25, output: 125.00}")
    code, out = run(t)
    check("a meter.prices row added without --write fails on the catalog too", code == 1 and gen.CATALOG.as_posix() in out, out)
    code, out = run(t, "--write")
    check("--write adds it under anthropic",
          code == 0 and catalog(t)[1]["providers"]["anthropic"]["models"]["claude-mythos-5"]["rates"]["cacheWrite"] == "31.25", out)
with tree() as t:
    replace(t, gen.VALUES, FLASH, FLASH + "\n          mystery-1: {input: 1.00, cacheRead: 0.10, output: 2.00}")
    before = (t / gen.CATALOG).read_text()
    code, out = run(t, "--write")
    check("a model with no provider is refused, by name, without a write",
          code == 1 and "mystery-1" in out and (t / gen.CATALOG).read_text() == before, out)
with tree() as t:
    (t / gen.CATALOG).unlink()
    code, out = run(t, "--write")
    check("--write creates a missing catalog file", code == 0 and (t / gen.CATALOG).exists() and run(t)[0] == 0, out)

print("the overlay is the one parameters.yaml loads")
with tree() as t:
    code, out = run(t)
    check("the committed parameters.yaml names the generated ConfigMap and its key", code == 0, out)
with tree() as t:
    replace(t, gen.PARAMETERS, "name: agent-model-catalog", "name: agent-model-catalogue")
    code, out = run(t)
    check("a renamed ConfigMap in parameters.yaml fails, naming both",
          code == 1 and "agent-model-catalogue" in out and "agent-model-catalog" in out, out)
with tree() as t:
    replace(t, gen.PARAMETERS, "name: agent-model-catalog", "name: agent-model-catalog\n          key: prices.json")
    code, out = run(t)
    check("a key other than catalog.json fails", code == 1 and "prices.json" in out, out)
with tree() as t:
    replace(t, gen.PARAMETERS, "name: agent-model-catalog", "name: agent-model-catalog\n          key: catalog.json")
    check("the explicit default key passes", run(t)[0] == 0)
with tree() as t:
    replace(t, gen.PARAMETERS, "  modelCatalog:", "  modelCatalogOff:")
    code, out = run(t)
    check("no modelCatalog source at all fails", code == 1 and "modelCatalog" in out, out)

print("parity")
with tree() as t:
    code, out = run(t)
    check("the rendered tree is in sync", code == 0 and "is meter.prices' rendering" in out, out)
    once = rules(t).read_bytes()
    code, out = run(t, "--write")
    check("--write on a tree in sync writes nothing", code == 0 and rules(t).read_bytes() == once, out)
with tree() as t:
    want = rules(t).read_bytes()
    text = rules(t).read_text()
    start = text.index(f"    - name: {gen.GROUP}\n")
    end = text.index("    - name: llm-gateway-budgets\n")
    rules(t).write_text(text[:start] + f"    - name: {gen.GROUP}\n      rules: []\n" + text[end:])
    code, out = run(t, "--write")
    check("--write rebuilds the group from nothing, byte for byte", code == 0 and rules(t).read_bytes() == want, out)
    budgets = [g for g in gen.groups_of(rules(t).read_text()) if g["name"] == "llm-gateway-budgets"]
    check("the hand-written group beside it is untouched", len(budgets) == 1 and
          budgets == [g for g in gen.groups_of((ROOT / gen.RULES).read_text()) if g["name"] == "llm-gateway-budgets"])

print("drift (design offline proof 1)")
with tree() as t:
    replace(t, gen.RULES, "expr: vector(-3.80)", "expr: vector(-3.70)")
    code, out = run(t)
    check("a hand edit to a row fails, with the diff and the fix",
          code == 1 and "-          expr: vector(-3.70)" in out and "+          expr: vector(-3.80)" in out
          and "--write" in out, out)
with tree() as t:
    before = rules(t).read_text().splitlines()
    replace(t, gen.VALUES, HAIKU, HAIKU + "\n          claude-mythos-5: {input: 25.00, cacheRead: 2.50, cacheWrite: 31.25, output: 125.00}")
    code, out = run(t)
    check("a row added to meter.prices without --write fails", code == 1 and "differs" in out, out)
    code, out = run(t, "--write")
    after = rules(t).read_text().splitlines()
    got, n = charges_in(t)
    i = before.index("    - name: llm-gateway-budgets")
    check("--write inserts its comment and four rules at the group's end, and nothing else",
          code == 0 and n == 28 and after[:i] == before[:i] and after[i + 21:] == before[i:]
          and after[i] == "        # claude-mythos-5: input 25.00, cacheRead 2.50, cacheWrite 31.25, output 125.00",
          "\n".join(after[i - 1:i + 2]))
    check("its charges", got["claude-mythos-5"] == ("25.00", "125.00", "-22.50", "6.25"), str(got["claude-mythos-5"]))
    check("the result is in sync", run(t)[0] == 0)
with tree() as t:
    text = rules(t).read_text()
    check("provenance is never rendered: no source, no checkedAt in the rules",
          "source" not in text and "checkedAt" not in text)
with tree() as t:
    replace(t, gen.VALUES, FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: 0.60}")
    code, out = run(t, "--write")
    check("a price change moves its own rule only",
          code == 0 and charges_in(t)[0]["glm-5.3-flash"] == ("0.15", "0.60", "-0.12", "0.00"), out)

print("a group the generator does not fully own")
STRAY = "holds lines the generator does not own"
with tree() as t:
    replace(t, gen.RULES, "      interval: 5m\n", "      interval: 5m\n\n")
    code, out = run(t, "--write")
    check("a blank line inside the group is refused, untouched", code == 1 and STRAY in out
          and "\n\n      rules:" in rules(t).read_text(), out)

print("refused rows and files")
for name, change, needle in [
    ("a row without cacheRead", row(FLASH, "glm-5.3-flash: {input: 0.15, output: 0.50}"),
     "meter.prices.glm-5.3-flash: missing cacheRead"),
    ("a price that is not a number", row(FLASH, "glm-5.3-flash: {input: '0.15', cacheRead: 0.03, output: 0.50}"),
     "input must be a positive number of USD per million tokens, got '0.15'"),
    ("a zero price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0, output: 0.50}"),
     "cacheRead must be a positive number"),
    ("a boolean price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: true}"),
     "output must be a positive number"),
    ("not a finite price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: .nan, output: 0.50}"),
     "cacheRead must be a positive number"),
    ("an unknown key", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, cacheWirte: 0.2, output: 0.50}"),
     "unknown key cacheWirte"),
    ("not a model name", row(FLASH, "'glm 5.3 flash': {input: 0.15, cacheRead: 0.03, output: 0.50}"),
     "meter.prices key 'glm 5.3 flash' is not a served model name"),
    ("no row at all", row("        prices:\n", "        prices: {}\n        unused:\n"), "config.meter.prices holds no row"),
    ("no group in the rule file", lambda t: replace(t, gen.RULES, f"- name: {gen.GROUP}\n", "- name: other\n"),
     f"expected one group `- name: {gen.GROUP}`, found 0"),
    ("the group twice", lambda t: replace(t, gen.RULES, "    - name: llm-gateway-budgets\n",
                                          f"    - name: {gen.GROUP}\n      rules: []\n    - name: llm-gateway-budgets\n"),
     f"expected one group `- name: {gen.GROUP}`, found 2"),
]:
    refused(name, change, needle)
with tree() as t:
    replace(t, gen.VALUES, FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: 0.50}")
    code, out = run(t)
    check("TC1's source and checkedAt are optional, and never rendered", code == 0, out)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
