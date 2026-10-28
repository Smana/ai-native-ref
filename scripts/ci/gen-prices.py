#!/usr/bin/env python3
"""Render the llm-gateway-prices group of vmrule-llm-gateway.yaml and the agentgateway catalog overlay from meter.prices (truthful costs TC2 and TC3; cost cross-check XC2).

meter.prices, in the factory's values (tooling/base/agent-factory/helm-values-configmap.yaml), is the
one place a price is edited: USD per million tokens per served model, `input`, `cacheRead`, `output`,
and `cacheWrite` where the provider bills one. This script renders each row as four series of
llm_gateway:charge_usd_per_mtoken{gen_ai_request_model, gen_ai_token_type}, what one counted token of
that type adds to the cost. Every gateway counts cache tokens inside `input`, so:

    input                 input
    output                output
    cached_input          cacheRead - input
    cache_creation_input  cacheWrite - input, 0 without a cacheWrite (an unbilled write costs as input)

and a cost is one join over the four types:
sum(tokens * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:charge_usd_per_mtoken) / 1e6.
Zeros are rendered too, so no token type of a priced model drops out of the join.

The same rows render ConfigMap agent-model-catalog (infrastructure/base/agent-gateway/model-catalog.yaml,
key catalog.json), the overlay agentgateway prices each response with: Anthropic rows under `anthropic`,
GLM rows under `zai` (both Z.ai backends set providerOverride: zai), `input`, `output`, `cacheRead` and
`cacheWrite` as the table's values in strings, an absent `cacheWrite` absent. The script owns that file whole.

The script owns the group, from its `- name: llm-gateway-prices` line to the next line indented no
deeper, and nothing else in the file. Charges are exact decimals: 0.26 - 1.40 is written -1.14.

Usage: gen-prices.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed group and catalog are the rendering (or --write wrote it), 1 drift or a bad row.
"""
import difflib
import json
import math
import pathlib
import re
import sys
from decimal import Decimal

import yaml

VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
VALUES_NAME = "agent-factory-helm-values"
RULES = pathlib.PurePosixPath("infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml")
CATALOG = pathlib.PurePosixPath("infrastructure/base/agent-gateway/model-catalog.yaml")
CATALOG_NAME = "agent-model-catalog"
CATALOG_KEY = "catalog.json"
PARAMETERS = pathlib.PurePosixPath("infrastructure/base/agent-gateway/parameters.yaml")
CATALOG_NAMESPACE = "agent-gateway"
# The provider key agentgateway looks a model up under, by the model name's family.
PROVIDERS = (("claude-", "anthropic"), ("glm-", "zai"), ("k3", "moonshot"), ("mistral-", "mistral"))
CATALOG_FIELDS = ("input", "output", "cacheRead", "cacheWrite")
GROUP = "llm-gateway-prices"
INTERVAL = "5m"
RECORD = "llm_gateway:charge_usd_per_mtoken"
TYPES = ("input", "output", "cached_input", "cache_creation_input")
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
REQUIRED = ("input", "cacheRead", "output")
# Truthful costs TC1: provenance a row may carry. The meter ignores it, and so does this script.
METADATA = ("source", "checkedAt")
MODEL = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
BLOCK = re.compile(rf"^(?P<indent> *)- name: {re.escape(GROUP)}\n(?:(?P=indent)  .*\n)*", re.M)


class Strict(yaml.SafeLoader):
    """SafeLoader that refuses a key written twice in one mapping, where PyYAML would let the last win."""


def _mapping(loader, node):
    keys = [loader.construct_object(k, deep=True) for k, _ in node.value]
    if len(set(map(str, keys))) != len(keys):
        raise yaml.constructor.ConstructorError(None, None, "a key written twice", node.start_mark)
    return loader.construct_mapping(node, deep=True)


Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def usd(d):
    """A charge as the rule writes it: plain decimal notation, at least two places, no float noise."""
    text = format(d.normalize() if d else Decimal(0), "f")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def charges(row):
    """{token type: Decimal} for one valid meter.prices row."""
    p = {f: Decimal(str(row[f])) for f in FIELDS if f in row}
    write = p.get("cacheWrite", p["input"])
    return {"input": p["input"], "output": p["output"],
            "cached_input": p["cacheRead"] - p["input"], "cache_creation_input": write - p["input"]}


def provider_of(model):
    """The catalog provider key of a served model, None for a name no prefix claims."""
    return next((p for prefix, p in PROVIDERS if model.startswith(prefix)), None)


def catalog_file(prices):
    """The ConfigMap file: the overlay catalog.json rendered from meter.prices."""
    providers = {p: {"models": {}} for _, p in PROVIDERS}
    for model, row in prices.items():
        rates = {f: usd(Decimal(str(row[f]))) for f in CATALOG_FIELDS if f in row}
        providers[provider_of(model)]["models"][model] = {"rates": rates}
    body = json.dumps({"providers": providers}, indent=2)
    return (f"# Generated by scripts/ci/gen-prices.py --write from meter.prices ({VALUES}): edit a price there,\n"
            "# never here. agentgateway merges it over its built-in catalog (parameters.yaml, spec.modelCatalog).\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n"
            f"  name: {CATALOG_NAME}\n  namespace: {CATALOG_NAMESPACE}\n"
            "data:\n  catalog.json: |\n" + "".join(f"    {line}\n" for line in body.splitlines()))


def catalog_link_errors(root):
    """The Gateway's AgentgatewayParameters must load the ConfigMap and key this file generates: a rename on
    one side prices every response at $0 live, and no other offline check would see it."""
    docs = [d for d in yaml.safe_load_all((root / PARAMETERS).read_text()) if isinstance(d, dict)]
    sources = [src for d in docs for src in ((((d.get("spec") or {}).get("modelCatalog") or {}).get("sources")) or [])]
    refs = [src.get("configMap") or {} for src in sources]
    if not any(r.get("name") == CATALOG_NAME and r.get("key", CATALOG_KEY) == CATALOG_KEY for r in refs):
        got = ", ".join(f"{r.get('name')}/{r.get('key', CATALOG_KEY)}" for r in refs) or "no source"
        return [f"{PARAMETERS}: spec.modelCatalog.sources holds {got}, not the generated ConfigMap "
                f"{CATALOG_NAME} key {CATALOG_KEY} ({CATALOG})"]
    return []


def load_prices(root, errors):
    """meter.prices as written, rows in file order; {} after an error."""
    docs = [d for d in yaml.safe_load_all((root / VALUES).read_text()) if isinstance(d, dict)]
    cm = next((d for d in docs if d.get("kind") == "ConfigMap"
               and (d.get("metadata") or {}).get("name") == VALUES_NAME), None)
    if cm is None:
        errors.append(f"{VALUES}: no ConfigMap {VALUES_NAME}")
        return {}
    values = yaml.safe_load((cm.get("data") or {}).get("values.yaml") or "") or {}
    prices = ((values.get("config") or {}).get("meter") or {}).get("prices")
    if not isinstance(prices, dict) or not prices:
        errors.append(f"{VALUES}: config.meter.prices holds no row")
        return {}
    for model, row in prices.items():
        where = f"{VALUES}: meter.prices.{model}"
        if not isinstance(model, str) or not MODEL.match(model):
            errors.append(f"{VALUES}: meter.prices key {model!r} is not a served model name")
        if isinstance(model, str) and MODEL.match(model) and provider_of(model) is None:
            errors.append(f"{where}: no catalog provider for this model name; known prefixes: "
                          + ", ".join(p for p, _ in PROVIDERS))
        if not isinstance(row, dict):
            errors.append(f"{where} is a mapping of {', '.join(FIELDS)}")
            continue
        for key in sorted(set(row) - set(FIELDS) - set(METADATA), key=str):
            errors.append(f"{where}: unknown key {key}; a row holds {', '.join(FIELDS + METADATA)}")
        for f in FIELDS:
            v = row.get(f)
            if f not in row:
                if f in REQUIRED:
                    errors.append(f"{where}: missing {f}")
            elif isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                errors.append(f"{where}: {f} must be a positive number of USD per million tokens, got {v!r}")
    return prices


def group(prices, indent):
    """The group's text at `indent`, and the structure it must parse back to."""
    rules, lines = [], [f"{indent}- name: {GROUP}", f"{indent}  interval: {INTERVAL}", f"{indent}  rules:"]
    for model, row in prices.items():
        listed = ", ".join(f"{f} {usd(Decimal(str(row[f])))}" for f in FIELDS if f in row)
        lines.append(f"{indent}    # {model}: {listed}" + ("" if "cacheWrite" in row else "; writes cost as input"))
        for t, charge in charges(row).items():
            rules.append({"record": RECORD, "expr": f"vector({usd(charge)})",
                          "labels": {"gen_ai_request_model": model, "gen_ai_token_type": t}})
            lines += [f"{indent}    - record: {RECORD}", f"{indent}      expr: vector({usd(charge)})",
                      f"{indent}      labels:", f'{indent}        gen_ai_request_model: "{model}"',
                      f"{indent}        gen_ai_token_type: {t}"]
    return "".join(f"{line}\n" for line in lines), {"name": GROUP, "interval": INTERVAL, "rules": rules}


def groups_of(text):
    """Every group of the file's VMRule documents, in order; None when a mapping repeats a key."""
    try:
        docs = list(yaml.load_all(text, Loader=Strict))
    except yaml.constructor.ConstructorError:
        return None
    return [g for d in docs if isinstance(d, dict) and d.get("kind") == "VMRule"
            for g in (d.get("spec") or {}).get("groups") or []]


def render(root):
    """({path: the file rendered from meter.prices}, []) or (None, the errors that prevent it)."""
    root = pathlib.Path(root)
    errors = []
    prices = load_prices(root, errors)
    if errors:
        return None, errors
    current = (root / RULES).read_text()
    found = list(BLOCK.finditer(current))
    if len(found) != 1:
        return None, [f"{RULES}: expected one group `- name: {GROUP}`, found {len(found)}"]
    m = found[0]
    text, want = group(prices, m["indent"])
    spliced = current[:m.start()] + text + current[m.end():]
    # The splice replaces the lines indented under the group's name only: a group whose lines are
    # written otherwise (a flow mapping, a blank line inside, no final newline) would leave pieces
    # behind, so the result must parse back to exactly the rendering, and every other group unchanged.
    before = [g for g in groups_of(current) or [] if g.get("name") != GROUP]
    after = groups_of(spliced) or []
    if [g for g in after if g.get("name") == GROUP] != [want] or [g for g in after if g.get("name") != GROUP] != before:
        return None, [f"{RULES}: group {GROUP} holds lines the generator does not own (a blank line, a flow "
                      "mapping, or no final newline?): write it as a block, or delete it and run --write"]
    return {RULES: spliced, CATALOG: catalog_file(prices)}, []


def main(argv):
    args = argv[1:]
    write = "--write" in args
    paths = [a for a in args if a != "--write"]
    root = pathlib.Path(paths[0]) if paths else pathlib.Path(__file__).resolve().parents[2]
    rendered, errors = render(root)
    errors = (errors or []) + catalog_link_errors(root)
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if errors:
        return 1
    drift = {}
    for rel, text in rendered.items():
        path = root / rel
        current = path.read_text() if path.exists() else ""
        if text != current:
            drift[rel] = (current, text)
    if not drift:
        print(f"gen-prices: {RULES} group {GROUP} is meter.prices' rendering, and so is {CATALOG}")
        return 0
    if write:
        for rel, (_, text) in drift.items():
            (root / rel).write_text(text)
            print(f"gen-prices: wrote {rel}")
        return 0
    for rel, (current, text) in drift.items():
        sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                                   f"{rel} (committed)", f"{rel} (rendered from meter.prices)"))
        print(f"FAIL {rel} differs from meter.prices' rendering: edit the price in {VALUES}, run "
              "python3 scripts/ci/gen-prices.py --write and commit both", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
