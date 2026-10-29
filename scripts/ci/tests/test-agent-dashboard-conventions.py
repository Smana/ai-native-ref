#!/usr/bin/env python3
# requires: python3
"""The agent dashboards' reading conventions, on the real tree. A panel must say what it shows and
must not paint a count red: Grafana's default thresholds are green with red at 80, so a bar of
tokens or runs turns red for being large. A stat or bar gauge therefore sets its colour (fixed, or
thresholds that mean something: a cap, a ratio), and a counter that has no series until its first
event reads 0, not No data.

The folder reads as one tool: every dashboard carries the "agents" tag and the shared top-bar link (a
dashboards-by-tag link, so a new dashboard joins every bar without an edit), every panel says what it shows,
and a counter the meter or the gateway resets is never read through a bare increase() over a range: the
series of a run or a payer is born inside the range, and increase() drops its first value (SI11)."""
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


UIDS = {"agents-overview", "agent-fleet", "agent-factory", "agent-gateway", "agent-identity", "agent-room", "agent-run"}
# Counters (and histogram parts) the meter, the factory or the gateway resets or births inside a range.
RESET = re.compile(r"(?<!_)\bincrease\(\s*(agent_factory_\w+|gen_ai_client_token_usage_sum|gen_ai_server_request_duration_seconds_(?:count|sum|bucket))\b[^\[]*\[([^\]]+)\]")


def all_boards():
    for path in sorted(DASHBOARDS.glob("grafana-dashboard*.yaml")):
        yield path.name, board(path.name)


def check_folder():
    seen = {}
    for name, b in all_boards():
        seen[b["uid"]] = name
        check(b.get("tags") == ["agents"], f"{name}: tagged agents")
        shared = [x for x in b.get("links", []) if x.get("type") == "dashboards" and x.get("tags") == ["agents"]]
        check(len(shared) == 1 and shared[0].get("keepTime") is True and shared[0].get("includeVars") is True and shared[0].get("asDropdown") is False,
              f"{name}: carries the shared top-bar link (dashboards tagged agents, keepTime, includeVars)")
        for p in flat(b):
            if p.get("type") == "row":
                continue
            check(len(p.get("description", "").strip()) >= 20, f"{name}: {p['title']} has a description")
            for t in p.get("targets", []):
                for m in RESET.finditer(t.get("expr", "")):
                    check(m[2] == "$__rate_interval", f"{name}: {p['title']} {t['refId']}: increase({m[1]}[{m[2]}]) is unbounded: increase_pure")
    check(set(seen) == UIDS, f"the folder holds exactly {sorted(UIDS)}, found {sorted(seen)} (agent-platform is retired)")
    resources = yaml.safe_load((DASHBOARDS / "kustomization.yaml").read_text())["resources"]
    check(sorted(r for r in resources if r.startswith("grafana-dashboard")) == sorted(seen.values()), "kustomization lists every dashboard file, and only those")
    for path in DASHBOARDS.glob("vmrule*.yaml"):
        check("/d/agent-platform" not in path.read_text(), f"{path.name}: no alert points at the retired agent-platform dashboard")
        for uid in re.findall(r"/d/([a-z-]+)\"", path.read_text()):
            check(uid in UIDS, f"{path.name}: dashboard annotation /d/{uid} is a dashboard of the folder")


def check_drilldown():
    """Overview -> Fleet -> Identity -> Room -> Run: a row or tile opens the next dashboard down."""
    def links(file, title):
        p = panels(file)[title]
        return json.dumps([p.get("links", []), p.get("fieldConfig", {})])
    check("/d/agent-room/agent-room?var-room=" in links("grafana-dashboard-agents-overview.yaml", "Waiting for a human"), "overview: a waiting task opens its room")
    for tile, dash in (("Factory", "agent-factory"), ("Spent today", "agent-identity"), ("Runs in flight", "agent-fleet"),
                       ("Approvals pending", "agent-room"), ("Router 5xx now", "agent-gateway")):
        check(f"/d/{dash}/{dash}" in links("grafana-dashboard-agents-overview.yaml", tile), f"overview: {tile} opens {dash}")
    for file, title in (("grafana-dashboard-agent-fleet.yaml", "Runs"), ("grafana-dashboard-agent-identity.yaml", "Runs"), ("grafana-dashboard-agent-room.yaml", "Runs of this room")):
        check("/d/agent-run/agent-run?var-run=" in links(file, title), f"{file}: {title}: a run id opens its run")
    for file, title in (("grafana-dashboard-agent-fleet.yaml", "Runs"), ("grafana-dashboard-agent-identity.yaml", "Runs")):
        check("/d/agent-room/agent-room?var-room=" in links(file, title), f"{file}: {title}: a room opens its dashboard")
    for file, title in (("grafana-dashboard-agent-fleet.yaml", "Runs"), ("grafana-dashboard-agent-room.yaml", "Runs of this room")):
        check("/d/agent-identity/agent-identity?var-principal=" in links(file, title), f"{file}: {title}: a payer opens its spend page")
    run = board("grafana-dashboard-agent-run.yaml")
    urls = " ".join(x.get("url", "") for x in run["links"])
    check("/d/agent-identity/agent-identity?var-principal=" in urls and "/d/agent-room/agent-room?var-room=" in urls, "agent-run links up to its payer and its room")
    room = board("grafana-dashboard-agent-room.yaml")
    check(any(x.get("url", "").startswith("https://rooms.${private_domain_name}/r/${room}") for x in room["links"]), "agent-room links to the room page")
    check({v["name"] for v in room["templating"]["list"]} == {"datasource", "room"}, "agent-room has one variable: room")


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
    check(all("maku_factory_max_cost_usd_total" in t["expr"] and "charged_usd" not in t["expr"] for t in ceilings["targets"]),
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


def check_models():
    # The served model (gen_ai_request_model; agentrun_info's model is the agent-default alias) on the identity, run, room and fleet pages.
    want = {"grafana-dashboard-agent-identity.yaml": ("Spend by model", "Spend by model per day", "Tokens by model"),
            "grafana-dashboard-agent-run.yaml": ("Models", "Cost by model"),
            "grafana-dashboard-agent-fleet.yaml": ("Spend by model and principal",)}
    for file, titles in want.items():
        ps = panels(file)
        for title in titles:
            p = ps.get(title)
            check(p is not None, f"{file}: {title} exists")
            if p is None:
                continue
            check(all("gen_ai_request_model" in t["expr"] for t in p["targets"]), f"{title}: splits by the served model")
            d = p.get("fieldConfig", {}).get("defaults", {})
            if p["type"] in ("stat", "bargauge"):
                check(d.get("color", {}).get("fixedColor") in ("blue", "text"), f"{title}: a neutral fixed colour, not a verdict")
    # a model column of a Runs table joins the models of a run in one cell: groupBy run_id, unique models
    for file, title, ref in (("grafana-dashboard-agent-identity.yaml", "Runs", "G"), ("grafana-dashboard-agent-room.yaml", "Runs of this room", "H")):
        p = panels(file)[title]
        check(any(t["refId"] == ref and "gen_ai_request_model" in t["expr"] for t in p["targets"]), f"{title}: query {ref} reads the models")
        group = next((tr for tr in p["transformations"] if tr["id"] == "groupBy"), {})
        check(group.get("options", {}).get("fields", {}).get("gen_ai_request_model", {}).get("aggregations") == ["uniqueValues"],
              f"{title}: the model column joins the unique models of a run")
        renames = next((tr for tr in p["transformations"][::-1] if tr["id"] == "organize"), {}).get("options", {}).get("renameByName", {})
        check(renames.get("gen_ai_request_model (uniqueValues)") == "model", f"{title}: the column is named model")


def check_effort():
    # maku_rooms_run_info{run, model, effort} (broker, one series per live run): the effort column of the room's runs table,
    # the run page's facts table and the fleet's breakdown; max_over_time over the range, since a finished run has no series.
    room = panels("grafana-dashboard-agent-room.yaml")["Runs of this room"]
    check(any(t["refId"] == "I" and "maku_rooms_run_info" in t["expr"] and "max_over_time" in t["expr"] and "effort" in t["expr"] for t in room["targets"]), "Runs of this room: query I reads the effort of maku_rooms_run_info over the range")
    group = next((tr for tr in room["transformations"] if tr["id"] == "groupBy"), {})
    check("effort" in group.get("options", {}).get("fields", {}), "Runs of this room: effort is aggregated per run")
    keep = next(tr for tr in room["transformations"] if tr["id"] == "filterFieldsByName")["options"]["include"]["names"]
    check("effort" in keep, "Runs of this room: the effort column is kept")
    renames = next((tr for tr in room["transformations"][::-1] if tr["id"] == "organize"), {}).get("options", {}).get("renameByName", {})
    check(renames.get("effort (lastNotNull)") == "effort", "Runs of this room: the column is named effort")
    run = panels("grafana-dashboard-agent-run.yaml")["Run"]
    check(any("maku_rooms_run_info" in t["expr"] and "max_over_time" in t["expr"] and 'run="${run}"' in t["expr"] for t in run["targets"]), "Run: a query reads this run's effort from maku_rooms_run_info")
    names = next(t for t in run["transformations"] if t["id"] == "filterFieldsByName")["options"]["include"]["names"]
    check("effort" in names and "model" in names, "Run: effort and the claimed model are in the facts table")
    fleet = panels("grafana-dashboard-agent-fleet.yaml").get("Runs by effort")
    check(fleet is not None and all("maku_rooms_run_info" in t["expr"] and "max_over_time" in t["expr"] and "by (effort)" in t["expr"] for t in fleet["targets"]), "fleet: Runs by effort counts maku_rooms_run_info by effort over the range")


for run in (check_folder, check_drilldown, check_colours, check_sponsored, check_gateway_ratio, check_trace_pipeline, check_models, check_effort):
    run()
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("PASS")
