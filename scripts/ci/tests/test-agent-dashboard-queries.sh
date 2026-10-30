#!/usr/bin/env bash
# requires: promtool python3
#
# The queries the Agents overview, the Agent room and the fleet run on, read from the dashboards and
# evaluated by promtool on synthetic series shaped as kube-state-metrics, the factory and the gateway export them.
# - Runs by phase (fleet) and Runs in flight (overview) count a run once, at its latest phase, though two
#   kube-state-metrics pods export it (an old pod's Pending stuck at 1, the new pod's Succeeded or Running).
# - The room's Runs table joins only the runs of the room: its task's, and a room run by its branch agent/<room>.
#   Its spend prices each run's tokens by the meter's price per token, and its tokens read input + output.
# - Landed on the overview: merged = auto + human merged, reverted absent reads nothing (the tile says 0).
# - The models: the identity, run, room and fleet dashboards split a run's tokens and priced spend by the served model
#   (gen_ai_request_model). A run that called two aliases shows both, a principal's figures cover only the runs charged to it.
# - The factory's SC-11 stat reads 0, not No data, with no reverted series and with no auto-merge at all.
# promtool has no increase_pure (VictoriaMetrics: counts a series from 0, as these start at 0, so increase() agrees)
# and no tlast_over_time (read as max_over_time(timestamp(series)[range:1m])).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp" python3 - <<'PY' || exit 1
import json
import os
import re
import sys

import yaml

root, out = os.environ["ROOT"], os.environ["OUT"]
base = "observability/base/agent-platform/grafana-dashboard-"


def board(file):
    doc = next(d for d in yaml.safe_load_all(open(os.path.join(root, base + file + ".yaml"))) if d and d.get("kind") == "GrafanaDashboard")
    return json.loads(doc["spec"]["json"].replace("$$", "$"))


def flat(ps):
    for p in ps:
        yield p
        yield from flat(p.get("panels", []))


def expr(file, title, ref="A"):
    p = next(p for p in flat(board(file)["panels"]) if p.get("title") == title and p.get("targets"))
    return next(t["expr"] for t in p["targets"] if t["refId"] == ref)


def prep(e, **variables):
    e = e.replace("$__range", "1h").replace("increase_pure(", "increase(")
    for k, v in variables.items():
        e = e.replace("${%s}" % k, v)
    e = re.sub(r"tlast_over_time\((agentrun_status_phase\{[^}]*\})\[1h\]\)", r"max_over_time(timestamp(\1)[1h:1m])", e)
    if "$" in e.replace("$1", ""):
        sys.exit(f"a variable this test does not set: {e}")
    return e


def phase(run, ph, pod, values):
    return {"series": f'agentrun_status_phase{{namespace="agents", run_id="{run}", phase="{ph}", pod="{pod}"}}', "values": values}


def info(run, task, role, branch=""):
    b = f', branch="{branch}"' if branch else ""
    return {"series": f'agentrun_info{{namespace="agents", run_id="{run}", task="{task}", role="{role}"{b}}}', "values": "1x30"}


def tok(run, kind, values):
    return {"series": f'gen_ai_client_token_usage_sum{{ar_agent="system:serviceaccount:agents:xplane-run-{run}", gen_ai_request_model="m1", gen_ai_token_type="{kind}"}}', "values": values}


def tokm(run, model, kind, values):
    return {"series": f'gen_ai_client_token_usage_sum{{ar_agent="system:serviceaccount:agents:xplane-run-{run}", gen_ai_request_model="{model}", gen_ai_token_type="{kind}"}}', "values": values}


def charge(run, principal, room=""):
    return {"series": f'maku_factory_run_charge_info{{run="{run}", principal="{principal}", room="{room}", task="{room}"}}', "values": "1x30"}


def mprice(model, kind, v):
    return {"series": f'llm_gateway:charge_usd_per_mtoken{{gen_ai_request_model="{model}", gen_ai_token_type="{kind}"}}', "values": f"{v}x30"}


def price(kind, v):
    return {"series": f'llm_gateway:charge_usd_per_mtoken{{gen_ai_request_model="m1", gen_ai_token_type="{kind}"}}', "values": f"{v}x30"}


OLD, NEW1, NEW2 = "ksm-old", "ksm-new1", "ksm-new2"
series = [
    # aaaaaaaa: stale Pending on the old pod, Succeeded on both new pods (an HA pair): one Succeeded
    phase("aaaaaaaa", "Pending", OLD, "1x10"), phase("aaaaaaaa", "Succeeded", NEW1, "_x12 1x17"), phase("aaaaaaaa", "Succeeded", NEW2, "_x12 1x17"),
    # cccccccc: Running on the new pod while the old pod's Pending is stale: one Running
    phase("cccccccc", "Pending", OLD, "1x10"), phase("cccccccc", "Running", NEW1, "_x12 1x17"), phase("cccccccc", "Succeeded", NEW1, "_x12 0x17"),
    # dddddddd: a run of another room
    phase("dddddddd", "Running", NEW1, "1x30"),
    info("aaaaaaaa", "room1", "impl"), info("cccccccc", "room1", "review"), info("dddddddd", "room2", "impl"),
    # a room run: no task, on the branch agent/room3
    info("eeeeeeee", "", "impl", branch="agent/room3"),
    # tokens: aaaaaaaa read 1M input and 100k output at 2 and 10 USD per Mtoken: 2 + 1 = 3 USD
    tok("aaaaaaaa", "input", "0 1000000x30"), tok("aaaaaaaa", "output", "0 100000x30"),
    tok("dddddddd", "input", "0 500000x30"),
    price("input", 2), price("output", 10),
    # models: ffffffff (room4, charged to alice) called m1 and m2; aaaaaaaa is alice's, dddddddd bob's
    info("ffffffff", "room4", "impl"),
    charge("aaaaaaaa", "github:alice", "room1"), charge("dddddddd", "github:bob", "room2"), charge("ffffffff", "github:alice", "room4"),
    tokm("ffffffff", "m1", "input", "0 1000000x30"), tokm("ffffffff", "m2", "input", "0 500000x30"), tokm("ffffffff", "m2", "output", "0 100000x30"),
    mprice("m2", "input", 4), mprice("m2", "output", 20),
    # the broker-wide factory counters
    {"series": 'maku_factory_pr_outcomes_total{outcome="auto_merged", class="deps"}', "values": "0 4x30"},
    {"series": 'maku_factory_pr_outcomes_total{outcome="human_merged", class="review"}', "values": "0 2x30"},
    {"series": 'maku_factory_pr_outcomes_total{outcome="approved_merged", class="review"}', "values": "0 1x30"},
    {"series": 'maku_factory_prs_opened_total{principal="github:alice"}', "values": "0 7x30"},
]


def rows(e, want, t="29m"):
    return {"expr": e, "eval_time": t, "exp_samples": want}


def ph(*pairs):
    return [{"labels": '{phase="%s"}' % p, "value": v} for p, v in pairs]


def runs(*ids):
    return [{"labels": '{run_id="%s"}' % r, "value": v} for r, v in ids]


room1 = dict(room="room1")


def by_model(*pairs, extra=""):
    return [{"labels": '{%sgen_ai_request_model="%s"}' % (extra, m), "value": v} for m, v in pairs]


def run_model(*rows_):
    return [{"labels": '{gen_ai_request_model="%s", run_id="%s"}' % (m, r), "value": v} for r, m, v in rows_]


alice, bob = dict(principal="github:alice"), dict(principal="github:bob")
tests = [{"interval": "1m", "input_series": series, "promql_expr_test": [
    # fleet: each run once at its latest phase, 4 runs seen but dddd/eeee are Running / absent
    rows(prep(expr("agent-fleet", "Runs by phase")), ph(("Succeeded", 1), ("Running", 2))),
    # overview: in flight = cccccccc and dddddddd (Running), not aaaaaaaa (Succeeded) or the stale Pendings
    rows(prep(expr("agents-overview", "Runs in flight")), [{"value": 2}]),
    # room1 holds aaaaaaaa and cccccccc only
    rows(prep(expr("agent-room", "Runs", "A"), **room1), [{"value": 2}]),
    rows(prep(expr("agent-room", "Runs of this room", "B"), **room1), [{"labels": '{phase="Succeeded", run_id="aaaaaaaa"}', "value": 1}, {"labels": '{phase="Running", run_id="cccccccc"}', "value": 1}]),
    rows(prep(expr("agent-room", "Runs by phase", "A"), **room1), ph(("Succeeded", 1), ("Running", 1))),
    # a room run is found by its branch
    rows(prep(expr("agent-room", "Runs", "A"), room="room3"), [{"value": 1}]),
    # priced spend of aaaaaaaa: 1M x 2 + 0.1M x 10 = 3 USD; room2's dddddddd: 0.5M x 2 = 1 USD
    rows(prep(expr("agent-room", "Spend", "A"), **room1), [{"value": 3}]),
    rows(prep(expr("agent-room", "Spend", "A"), room="room2"), [{"value": 1}]),
    rows(prep(expr("agent-room", "Tokens", "A"), **room1), [{"value": 1100000}]),
    rows(prep(expr("agent-room", "Runs of this room", "E"), **room1), runs(("aaaaaaaa", 3))),
    # models, identity page: only the runs charged to the principal, each model apart (m1 = 3 + 2 USD, m2 = 2 + 2 USD)
    rows(prep(expr("agent-identity", "Spend by model"), **alice), by_model(("m1", 5), ("m2", 4))),
    rows(prep(expr("agent-identity", "Spend by model"), **bob), by_model(("m1", 1))),
    rows(prep(expr("agent-identity", "Tokens by model"), **alice), by_model(("m1", 2100000), ("m2", 600000))),
    rows(prep(expr("agent-identity", "Tokens by model"), **bob), by_model(("m1", 500000))),
    rows(prep(expr("agent-identity", "Runs", "G"), **alice), run_model(("aaaaaaaa", "m1", 1100000), ("ffffffff", "m1", 1000000), ("ffffffff", "m2", 600000))),
    # run page: the models of one run, its cost split by model adds up to the Cost tile
    rows(prep(expr("agent-run", "Models"), run="ffffffff"), by_model(("m1", 1000000), ("m2", 600000))),
    rows(prep(expr("agent-run", "Cost by model"), run="ffffffff"), by_model(("m1", 2), ("m2", 4))),
    rows(prep(expr("agent-run", "Cost (USD)"), run="ffffffff"), [{"value": 6}]),
    # room page: each run of the room with its models
    rows(prep(expr("agent-room", "Runs of this room", "H"), room="room4"), run_model(("ffffffff", "m1", 1000000), ("ffffffff", "m2", 600000))),
    # fleet: spend by model and by the principal each run is charged to
    rows(prep(expr("agent-fleet", "Spend by model and principal")),
         [{"labels": '{gen_ai_request_model="m1", principal="github:alice"}', "value": 5}, {"labels": '{gen_ai_request_model="m2", principal="github:alice"}', "value": 4},
          {"labels": '{gen_ai_request_model="m1", principal="github:bob"}', "value": 1}]),
    # landed: 4 auto + 2 human + 1 approved merged; no reverted series at all
    rows(prep(expr("agents-overview", "PRs merged")), [{"value": 7}]),
    rows(prep(expr("agents-overview", "PRs reverted")), []),
    rows(prep(expr("agents-overview", "PRs opened")), [{"value": 7}]),
    # SC-11 reads 0 (4 auto-merges, no revert), and 0 again with no auto-merge series at all
    rows(prep(expr("agent-factory", "Reverted after auto-merge (SC-11: ≤ 5 %)")), [{"value": 0}]),
]}, {"interval": "1m", "input_series": [{"series": 'maku_factory_pr_outcomes_total{outcome="human_merged"}', "values": "0 1x30"}], "promql_expr_test": [
    rows(prep(expr("agent-factory", "Reverted after auto-merge (SC-11: ≤ 5 %)")), [{"value": 0}]),
]}]
open(os.path.join(out, "rules.yaml"), "w").write("groups: []\n")
yaml.safe_dump({"rule_files": ["rules.yaml"], "evaluation_interval": "1m", "tests": tests},
               open(os.path.join(out, "tests.yaml"), "w"), sort_keys=False, width=100000)
PY

cd "$tmp" && promtool test rules tests.yaml
