#!/usr/bin/env python3
"""Compares meter.prices with three public price catalogs and keeps one `prices-drift` issue.

Run nightly by .github/workflows/price-drift.yaml (truthful costs design, TC10). A catalog copies the
providers' page mistakes, so a finding only tells a human where to look: this script never edits
the table and never opens a pull request.

  python3 scripts/ci/check-price-drift.py [--dry-run] [ROOT]

Exit 0: the issue now matches the night's findings (opened, updated, closed or left as it was).
Exit 1: the table or a catalog could not be read; the issue is left alone and the failed run
notifies. A failed gh call also exits 1 (gh's error goes to the job log), possibly after the
label was created. --dry-run fetches and compares, prints the body, and calls no gh.
"""
import argparse
import http.client
import json
import pathlib
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

import yaml

VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
LABEL = "prices-drift"
TITLE = "Price drift: a public catalog disagrees with meter.prices"
CLOSING = "The nightly price drift check found no disagreement: every row matches its catalogs."
CATALOGS = {
    # v2 is genai-prices' live feed; prices/data.json is a v1 snapshot frozen since 2026-07-25.
    "genai-prices": "https://raw.githubusercontent.com/pydantic/genai-prices/main/prices/new_data/v2/data.json",
    "LiteLLM": "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
    "models.dev": "https://models.dev/api.json",
}
ZAI = "https://docs.z.ai/guides/overview/pricing"
ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"

# Each meter.prices row's key in each catalog, and the provider page a human confirms it on (the
# row's `source` replaces `page` once rows carry one). genai-prices and models.dev keys are
# <provider id>/<model id>; LiteLLM's are its own top-level keys. Z.ai rows name the pay-as-you-go
# providers: genai-prices `zai`, not `zhipuai` (CNY converted), and models.dev `zai`, not
# `zai-coding-plan` (priced 0).
MAPPING = {
    "glm-5.3": {"page": ZAI, "genai-prices": "zai/GLM-5.3", "LiteLLM": "zai/glm-5.3",
                "models.dev": "zai/glm-5.3"},
    "glm-5.3-flashx": {"page": ZAI, "genai-prices": "zai/GLM-5.3-FlashX", "LiteLLM": "zai/glm-5.3-flashx",
                       "models.dev": "zai/glm-5.3-flashx"},
    "glm-5.3-flash": {"page": ZAI, "genai-prices": "zai/GLM-5.3-Flash", "LiteLLM": "zai/glm-5.3-flash",
                      "models.dev": "zai/glm-5.3-flash"},
    "claude-opus-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-opus-5-5",
                        "LiteLLM": "claude-opus-5-5", "models.dev": "anthropic/claude-opus-5-5"},
    "claude-sonnet-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-sonnet-5-5",
                          "LiteLLM": "claude-sonnet-5-5", "models.dev": "anthropic/claude-sonnet-5-5"},
    "claude-haiku-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-haiku-5-5",
                         "LiteLLM": "claude-haiku-5-5", "models.dev": "anthropic/claude-haiku-5-5"},
}
# Rows a catalog does not list, checked 2026-10-22. No finding while the key stays absent; the
# night it appears, one, so the entry is dropped here and the row compared.
ABSENT = {
    ("glm-5.3-flashx", "LiteLLM"): "LiteLLM lists GLM-5.3-FlashX under tencent/ only",
}
# Rows held at a context tier on purpose, by the tier's threshold in prompt tokens. Haiku 5.5: the
# over-100K rate, which an agent's context soon reaches; over-counting is a cap's safe direction.
TIERS = {"claude-haiku-5-5": 100_000}
# Accepted deviations: (row, catalog, field) -> (the catalog value accepted, why). Any other value
# of that field is a finding again.
ACCEPTED: dict = {}

# Each catalog's name for a field. genai-prices and models.dev are in USD per million tokens,
# LiteLLM in USD per token.
NAMES = {
    "genai-prices": {"input": "input_mtok", "cacheRead": "cache_read_mtok",
                     "cacheWrite": "cache_write_mtok", "output": "output_mtok"},
    "LiteLLM": {"input": "input_cost_per_token", "cacheRead": "cache_read_input_token_cost",
                "cacheWrite": "cache_creation_input_token_cost", "output": "output_cost_per_token"},
    "models.dev": {"input": "input", "cacheRead": "cache_read", "cacheWrite": "cache_write",
                   "output": "output"},
}
Q = Decimal("0.0001")


class CatalogError(ValueError):
    """A catalog whose shape is not the one this script reads."""


class Finding(NamedTuple):
    model: str
    catalog: str
    field: str   # one of FIELDS, or "—" when the whole row is concerned
    ours: str
    theirs: str
    key: str     # the catalog key, "" when the mapping has none
    source: str


def load_prices(text):
    """meter.prices from the factory's values ConfigMap: model -> {field: Decimal}, plus `source`."""
    cm = yaml.safe_load(text) or {}
    values = yaml.safe_load((cm.get("data") or {}).get("values.yaml") or "") or {}
    prices = ((values.get("config") or {}).get("meter") or {}).get("prices")
    if not isinstance(prices, dict) or not prices:
        raise ValueError(f"{VALUES}: no config.meter.prices")
    return {m: {k: (v if k == "source" else Decimal(str(v)))
                for k, v in row.items() if k in FIELDS or k == "source"}
            for m, row in prices.items()}


def parse_catalog(name, text):
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as e:
        raise CatalogError(f"{name}: not JSON ({e})") from None


def _number(name, key, field, v):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise CatalogError(f"{name}: {key} {field} is {v!r}, not a number")
    return Decimal(v)


def _in_force(constraint, today):
    """A genai-prices constraint: none, a start_date, or a time of day (off-peak, never the list price)."""
    if not constraint:
        return True
    return "start_date" in constraint and date.fromisoformat(str(constraint["start_date"])) <= today


def _genai(data, key, tier, today):
    if not isinstance(data, list):
        raise CatalogError("genai-prices: not a list of providers")
    provider, _, model = key.partition("/")
    p = next((p for p in data if isinstance(p, dict) and p.get("id") == provider), None)
    m = next((m for m in (p or {}).get("models") or [] if m.get("id") == model), None)
    if m is None:
        return None
    prices = m.get("prices")
    if isinstance(prices, list):  # dated prices: the last one in force today wins
        live = [c for c in prices if _in_force(c.get("constraint"), today)]
        prices = live[-1]["prices"] if live else {}
    if not isinstance(prices, dict):
        raise CatalogError(f"genai-prices: {key} prices is {type(prices).__name__}")
    out = {}
    for f, n in NAMES["genai-prices"].items():
        v = prices.get(n)
        if isinstance(v, dict):  # tiered: {base, tiers: [{start, price}]}
            v = next((t["price"] for t in v.get("tiers") or [] if t.get("start") == tier), v.get("base"))
        out[f] = _number("genai-prices", key, f, v)
    return out


def _litellm(data, key, tier, today):
    if not isinstance(data, dict):
        raise CatalogError("LiteLLM: not an object keyed by model")
    e = data.get(key)
    if e is None:
        return None
    suffix = f"_above_{tier // 1000}k_tokens" if tier else ""
    out = {}
    for f, n in NAMES["LiteLLM"].items():
        v = _number("LiteLLM", key, f, e.get(n + suffix, e.get(n)))
        out[f] = None if v is None else v * 1_000_000
    return out


def _modelsdev(data, key, tier, today):
    if not isinstance(data, dict):
        raise CatalogError("models.dev: not an object keyed by provider")
    provider, _, model = key.partition("/")
    m = ((data.get(provider) or {}).get("models") or {}).get(model)
    if m is None:
        return None
    cost = m.get("cost") or {}
    if tier:
        cost = next((t for t in cost.get("tiers") or [] if t.get("tier") == {"type": "context", "size": tier}),
                    cost)
    return {f: _number("models.dev", key, f, cost.get(n)) for f, n in NAMES["models.dev"].items()}


READERS = {"genai-prices": _genai, "LiteLLM": _litellm, "models.dev": _modelsdev}


def usd(d):
    """A rate as the table writes it: 4 decimals at most, 2 at least."""
    if d is None:
        return "absent"
    whole, _, frac = format(d.quantize(Q, rounding=ROUND_HALF_UP), "f").partition(".")
    return f"{whole}.{frac.rstrip('0').ljust(2, '0')}"


def same(field, ours, theirs):
    if ours is None and field == "cacheWrite":  # not billed: a catalog's absent or 0 agrees
        return theirs is None or theirs == 0
    if ours is None or theirs is None:
        return ours is None and theirs is None
    return ours.quantize(Q, rounding=ROUND_HALF_UP) == theirs.quantize(Q, rounding=ROUND_HALF_UP)


def compare(prices, catalogs, today, mapping=MAPPING, absent=ABSENT, tiers=TIERS, accepted=ACCEPTED):
    """Every disagreement between meter.prices and the catalogs, sorted. Raises CatalogError."""
    out, found = [], set()
    for model in sorted(prices):
        row, entry = prices[model], mapping.get(model) or {}
        source = row.get("source") or entry.get("page") or ""
        for name in sorted(catalogs):
            key = entry.get(name)
            if not key:
                out.append(Finding(model, name, "—", "—", "not in the mapping", "", source))
                continue
            theirs = READERS[name](catalogs[name], key, tiers.get(model), today)
            if theirs is not None:
                found.add(name)
            if (model, name) in absent:
                if theirs is not None:
                    out.append(Finding(model, name, "—", "—", "listed now: drop its ABSENT entry", key, source))
                continue
            if theirs is None:
                out.append(Finding(model, name, "—", "—", "not listed", key, source))
                continue
            for f in FIELDS:
                ours, their = row.get(f), theirs[f]
                if same(f, ours, their):
                    continue
                ok = accepted.get((model, name, f))
                if ok and their is not None and same(f, Decimal(ok[0]), their):
                    continue
                out.append(Finding(model, name, f, usd(ours), usd(their), key, source))
    blind = sorted(set(catalogs) - found)
    if blind:  # a moved or reshaped feed, not every row gone
        raise CatalogError(f"{blind[0]}: lists none of meter.prices' rows")
    return out


def issue_body(findings):
    lines = [
        "The nightly price drift check (`.github/workflows/price-drift.yaml`) found public catalogs that "
        "disagree with `meter.prices` in `tooling/base/agent-factory/helm-values-configmap.yaml`.",
        "",
        "Catalogs copy the providers' page mistakes: confirm each finding on the provider's page "
        "(Source) before changing anything. Then correct the row, or record the deviation in "
        "`scripts/ci/check-price-drift.py` (`MAPPING`, `ABSENT`, `TIERS` or `ACCEPTED`). This check "
        "never edits the table; the first clean run closes this issue.",
        "",
        "| Model | Field | Ours | Theirs | Catalog | Source |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        cat = f"[{f.catalog}]({CATALOGS[f.catalog]})" + (f" `{f.key}`" if f.key else "")
        lines.append(f"| `{f.model}` | {f.field} | {f.ours} | {f.theirs} | {cat} | {f.source or '—'} |")
    lines += ["", "USD per million tokens; equal when both round to the same 4 decimals."]
    return "\n".join(lines) + "\n"


def issue_action(findings, issue):
    """(action, body): open, update, close or nothing, given the open issue ({number, body}) or None."""
    if not findings:
        return ("close", None) if issue else ("nothing", None)
    body = issue_body(findings)
    if issue is None:
        return "open", body
    if issue.get("body", "").replace("\r\n", "\n").strip() == body.strip():
        return "nothing", None
    return "update", body


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-native-ref price drift check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def gh(*args, stdin=None):
    return subprocess.run(["gh", *args], input=stdin, check=True, stdout=subprocess.PIPE, encoding="utf-8").stdout


def open_issue():
    issues = json.loads(gh("issue", "list", "--state", "open", "--label", LABEL,
                           "--json", "number,body", "--limit", "100"))
    return min(issues, key=lambda i: i["number"]) if issues else None


def apply(action, body, issue):
    if action == "open":
        gh("label", "create", LABEL, "--color", "fbca04", "--force",
           "--description", "A public price catalog disagrees with meter.prices")
        gh("issue", "create", "--title", TITLE, "--label", LABEL, "--body-file", "-", stdin=body)
    elif action == "update":
        gh("issue", "edit", str(issue["number"]), "--body-file", "-", stdin=body)
    elif action == "close":
        gh("issue", "close", str(issue["number"]), "--comment", CLOSING)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="print the body; call no gh")
    p.add_argument("root", nargs="?", default=str(pathlib.Path(__file__).resolve().parents[2]))
    a = p.parse_args(argv)
    try:
        prices = load_prices((pathlib.Path(a.root) / VALUES).read_text())
        catalogs = {name: parse_catalog(name, fetch(url)) for name, url in CATALOGS.items()}
        findings = compare(prices, catalogs, datetime.now(timezone.utc).date())
    except (OSError, ValueError, http.client.HTTPException) as e:
        print(f"FAIL {e}: the {LABEL} issue is left alone", file=sys.stderr)
        return 1
    for f in findings:
        print(f"finding: {f.model} {f.field} ours {f.ours}, {f.catalog} {f.key or '-'} {f.theirs}")
    issue = None if a.dry_run else open_issue()
    action, body = issue_action(findings, issue)
    print(f"check-price-drift: {len(prices)} rows, {len(catalogs)} catalogs, {len(findings)} finding(s);"
          f" issue: {action}" + (f" #{issue['number']}" if issue else ""))
    if a.dry_run:
        print(body or "", end="")
    else:
        apply(action, body, issue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
