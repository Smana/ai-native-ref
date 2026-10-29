#!/usr/bin/env python3
# requires: python3
"""Spend per identity, offline proof 6 (docs/superpowers/specs/2026-10-22-spend-per-identity-design.md):
the agent-identity dashboard on the real tree. One principal at a time and no ranking of people
(SI6, SI7): a single-value variable without All, the framing text, and no panel that groups, sorts or
ranks by principal. Every figure is VictoriaMetrics, filtered on the page's principal, and every
counter or per-run series reads through increase_pure (SI11). The fleet and factory pages link to it."""
import json
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
DASHBOARDS = "observability/base/agent-platform"
errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


def board(name):
    rel = f"{DASHBOARDS}/grafana-dashboard-{name}.yaml"
    raw = (ROOT / rel).read_text()
    check(not re.search(r"(?<!\$)\$\{(?!private_domain_name\})", raw),
          f"{rel}: every ${{…}} but ${{private_domain_name}} is written $${{…}} for Flux")
    docs = [d for d in yaml.safe_load_all(raw) if d and d.get("kind") == "GrafanaDashboard"]
    if len(docs) != 1:
        errors.append(f"{rel}: expected one GrafanaDashboard, found {len(docs)}")
        return {}, {}
    return docs[0], json.loads(docs[0]["spec"]["json"].replace("$$", "$"))


def flat(b):
    for p in b.get("panels", []):
        yield p
        yield from p.get("panels", [])


PRINCIPAL = 'principal="${principal}"'
FLEET = 'principal="system:factory"'
# A grouping, sort or rank that would line principals up against each other (SI7).
RANKS = re.compile(r"\b(by|without)\s*\([^)]*\bprincipal\b|\b(topk|bottomk|sort|sort_desc|sort_by_label|sort_by_label_desc|limitk)\s*\(")
# Counters and per-run series the page reads over a range: never increase() or rate() (SI11).
COUNTED = ("maku_factory_charged_usd_total", "maku_factory_prs_opened_total", "maku_factory_pr_outcomes_total",
           "maku_factory_admission_refusals_total", "maku_factory_run_revocations_total",
           "maku_factory_human_wait_seconds_total", "maku_factory_max_cost_usd_total", "gen_ai_client_token_usage_sum")
WANT = {"Today, against its day", "The fleet's day", "Spend in the range", "Spend per day",
        "Tokens by type", "Cache-read share", "Runs · rooms · tasks", "Runs", "Pull requests opened · merged · reverted",
        "Cost per accepted PR", "Refusals", "Revocations", "Waiting for a human now", "Time waited", "Sponsor",
        "Ceilings admitted", "Stopped at the ceiling", "Spend by model", "Spend by model per day", "Tokens by model"}


def check_identity():
    doc, b = board("agent-identity")
    if not b:
        return
    check(doc["spec"].get("folderRef") == "agents", "agent-identity sits in the agents folder (OD-A)")
    check(b.get("uid") == "agent-identity" and b.get("title") == "Spend per identity", "uid agent-identity, titled Spend per identity")
    check(b.get("timezone") == "utc", "the page is in UTC, the ledger's day")
    check("not a score" in b.get("description", ""), "the dashboard's description frames it as cost attribution")
    variables = {v["name"]: v for v in b.get("templating", {}).get("list", [])}
    var = variables.get("principal", {})
    check(var.get("query") == "label_values(maku_factory_charged_usd_total, principal)", "principal comes from the charged counter")
    check(var.get("multi") is False and var.get("includeAll") is False, "principal is single-valued, without All")
    check(set(variables) == {"datasource", "principal"}, f"no other variable: {sorted(variables)}")
    panels = {p["title"]: p for p in flat(b)}
    check(WANT <= set(panels), f"missing panels: {sorted(WANT - set(panels))}")
    for p in flat(b):
        if p.get("type") in ("row", "text"):
            continue
        title = p["title"]
        check(p.get("datasource", {}).get("type") == "prometheus", f"{title}: VictoriaMetrics only")
        for t in p.get("targets", []):
            expr = t.get("expr", "")
            check(t.get("datasource") in (None, p.get("datasource")), f"{title} {t['refId']}: the panel's datasource")
            check(not RANKS.search(expr), f"{title} {t['refId']}: groups, sorts or ranks by principal")
            check(PRINCIPAL in expr or (title == "The fleet's day" and FLEET in expr),
                  f"{title} {t['refId']}: filters on the page's principal")
            check(not re.search(r"(?<!_)\b(increase|rate|irate)\(", expr), f"{title} {t['refId']}: increase_pure, never increase or rate")
            for series in COUNTED:
                for m in re.finditer(re.escape(series), expr):
                    check(expr[:m.start()].rstrip().endswith("increase_pure("),
                          f"{title} {t['refId']}: {series} is read through increase_pure")
        for tr in p.get("transformations", []):
            check("principal" not in json.dumps(tr), f"{title}: a transformation names principal")
    day = panels.get("Spend per day", {})
    check(day.get("interval") == "1d" and all("[1d] offset -1d)" in t["expr"] for t in day.get("targets", [])),
          "Spend per day reads each day forward from its UTC midnight ([1d] offset -1d), so today shows")
    runs = panels.get("Runs", {})
    charge = 'max_over_time(maku_factory_run_charge_info{principal="${principal}"}[$__range])'
    for t in runs.get("targets", []):
        check(charge in t["expr"], f"Runs {t['refId']}: restricted to this principal's runs by the charge info")
    check("/d/agent-run/agent-run?var-run=${__value.text}" in json.dumps(runs.get("fieldConfig", {})),
          "a run_id opens its Agent run page")
    resources = yaml.safe_load((ROOT / DASHBOARDS / "kustomization.yaml").read_text()).get("resources", [])
    check("grafana-dashboard-agent-identity.yaml" in resources, f"{DASHBOARDS}/kustomization.yaml lists the dashboard")


def check_links():
    _, fleet = board("agent-fleet")
    check(any(link.get("tags") == ["agents"] for link in fleet.get("links", [])),
          "agent-fleet reaches Spend per identity through the folder's shared link (by tag)")
    runs = next((p for p in flat(fleet) if p.get("title") == "Runs"), {})
    check("/d/agent-identity/agent-identity?var-principal=${__value.text}" in json.dumps(runs.get("fieldConfig", {})),
          "a payer in the fleet's Runs table opens its Spend per identity page")
    _, factory = board("agent-factory")
    budget = next((p for p in flat(factory) if p.get("title") == "Budget left today"), {})
    check("/d/agent-identity/agent-identity?var-principal=${__field.labels.principal}" in json.dumps(budget.get("fieldConfig", {})),
          "each bar of agent-factory's budget panel opens its principal's page")


for run in (check_identity, check_links):
    run()
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("PASS")
