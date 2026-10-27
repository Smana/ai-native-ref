#!/usr/bin/env python3
# requires: python3
"""The agent dashboards' reading conventions, on the real tree. A panel must say what it shows and
must not paint a count red: Grafana's default thresholds are green with red at 80, so a bar of
tokens or runs turns red for being large. A stat or bar gauge therefore sets its colour (fixed, or
thresholds that mean something: a cap, a ratio), and a counter that has no series until its first
event reads 0, not No data."""
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
DASHBOARDS = ROOT / "observability/base/agent-platform"
errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


def board(name):
    docs = [d for d in yaml.safe_load_all((DASHBOARDS / name).read_text()) if d and d.get("kind") == "GrafanaDashboard"]
    return json.loads(docs[0]["spec"]["json"].replace("$$", "$"))


def flat(b):
    for p in b.get("panels", []):
        yield p
        yield from p.get("panels", [])


def panels(file):
    return {p["title"]: p for p in flat(board(file))}


def check_colours():
    for path in sorted(DASHBOARDS.glob("grafana-dashboard*.yaml")):
        for p in flat(board(path.name)):
            if p.get("type") not in ("stat", "bargauge"):
                continue
            d = p.get("fieldConfig", {}).get("defaults", {})
            check("color" in d or "thresholds" in d,
                  f"{path.name}: {p['title']} is a {p['type']} on Grafana's default thresholds (red above 80)")
    ident = panels("grafana-dashboard-agent-identity.yaml")
    # A counter with no series until its first event reads 0.
    for title in ("Refusals", "Revocations", "Stopped at the ceiling", "Time waited"):
        check(ident[title]["fieldConfig"]["defaults"].get("noValue") == "0", f"{title} reads 0 when it has no series")


def check_sponsored():
    b = board("grafana-dashboard-agent-identity.yaml")
    row = next(p for p in b["panels"] if p["type"] == "row" and p["title"].startswith("Sponsored"))
    ident = panels("grafana-dashboard-agent-identity.yaml")
    check(row.get("collapsed") is True and len(row.get("panels", [])) == 3, "the Sponsored row is collapsed, its three panels inside")
    check("off" in ident["Sponsor"]["fieldConfig"]["defaults"].get("noValue", ""), "Sponsor says it is off, not No data")
    ceilings = ident["Ceilings admitted"]
    check(all("agent_factory_max_cost_usd_total" in t["expr"] and "charged_usd" not in t["expr"] for t in ceilings["targets"]),
          "Ceilings admitted shows ceilings only, never task spend under a ceilings title")
    check("off" in ceilings["fieldConfig"]["defaults"].get("noValue", ""), "Ceilings admitted says it is off when F4 is")


def check_gateway_ratio():
    p = panels("grafana-dashboard-agent-gateway.yaml")["5xx ratio by route"]
    expr = p["targets"][0]["expr"]
    check(p["fieldConfig"]["defaults"].get("unit") == "percentunit", "5xx ratio by route is a percentunit")
    check(expr.count("agentgateway_requests_total") == 3 and ") / sum by (route) (rate(agentgateway_requests_total{" in expr
          and 'status=~"5.."' in expr, "5xx ratio by route divides 5xx by all requests, per route")
    check(" * 0) /" in expr, "a route with traffic and no 5xx reads 0, not nothing")


def check_trace_pipeline():
    p = panels("grafana-dashboard-agent-fleet.yaml")["Trace pipeline (agent-traces-collector)"]
    check(len(p["targets"]) == 4, "Trace pipeline keeps its four series")
    for t in p["targets"]:
        # gcp-0 exposes otelcol_receiver_accepted_spans without _total: the name must match either
        check(re.search(r'__name__=~"otelcol_[a-z_]+\(_total\)\?"', t["expr"]), f"Trace pipeline {t['refId']}: the _total suffix is optional")
    check("noValue" in p["fieldConfig"]["defaults"], "Trace pipeline reads 0 for a series that has none (no failed export yet)")


for run in (check_colours, check_sponsored, check_gateway_ratio, check_trace_pipeline):
    run()
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("PASS")
