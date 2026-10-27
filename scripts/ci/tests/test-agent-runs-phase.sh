#!/usr/bin/env bash
# requires: promtool python3
#
# The agent dashboards' runs tables take each run's latest phase only. When kube-state-metrics is
# replaced, the old pod's agentrun_status_phase{phase="Pending"} series ends at 1 and never reads 0,
# and the new pod's Succeeded series says the run is done: two rows for one run. The four joins
# (agent-fleet Runs B, agent-identity Runs C, agent-run Run B and Runs of this task or room B)
# are read from the dashboards and evaluated by promtool on that shape.
# - run aaaaaaaa: stale Pending (old pod, ended at 1) beside Succeeded (new pod): one row, Succeeded.
# - run bbbbbbbb: Running then Succeeded in one pod (Running reads 0 after): one row, Succeeded.
# - run cccccccc: still Running on the new pod while the old pod's Pending is stale: one row, Running.
# promtool has no tlast_over_time (VictoriaMetrics only, and its experimental ts_of_last_over_time does not
# switch on): the test reads it as max_over_time(timestamp(series)[range:1m]).
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
base = "observability/base/agent-platform/grafana-dashboard-agent-"


def board(name):
    doc = next(d for d in yaml.safe_load_all(open(os.path.join(root, base + name + ".yaml"))) if d and d.get("kind") == "GrafanaDashboard")
    return json.loads(doc["spec"]["json"])


def flat(ps):
    for p in ps:
        yield p
        yield from flat(p.get("panels", []))


def expr(name, title, ref):
    p = next(p for p in flat(board(name)["panels"]) if p.get("title") == title and p.get("targets"))
    return next(t["expr"] for t in p["targets"] if t["refId"] == ref)


def prep(e, **variables):
    e = e.replace("$__range", "1h")
    # label_set(v, "phase", "Suspended") is VictoriaMetrics': promtool's equivalent
    e = e.replace("label_set(", "label_replace(").replace(', "phase", "Suspended")', ', "phase", "Suspended", "run_id", ".*")')
    for k, v in variables.items():
        e = e.replace("$${%s}" % k, v)
    # tlast_over_time(sel[r]) is VictoriaMetrics': the timestamp of the last sample, which timestamp()
    # of an instant selector gives promtool at every step
    e = re.sub(r"tlast_over_time\((agentrun_status_phase\{[^}]*\})\[1h\]\)", r"max_over_time(timestamp(\1)[1h:1m])", e)
    if "$" in e.replace("$1", ""):
        sys.exit(f"a variable this test does not set: {e}")
    return e


def phase(run, phase, pod, values):
    return {"series": f'agentrun_status_phase{{namespace="agents", run_id="{run}", phase="{phase}", pod="{pod}"}}', "values": values}


OLD, NEW = "kube-state-metrics-llvl6", "kube-state-metrics-l8wcc"
# One sample a minute for 30 minutes. The old pod's Pending stops at 1 after 10 minutes.
series = [
    phase("aaaaaaaa", "Pending", OLD, "1x10"), phase("aaaaaaaa", "Succeeded", NEW, "_x12 1x17"), phase("aaaaaaaa", "Pending", NEW, "_x12 0x17"),
    phase("bbbbbbbb", "Running", NEW, "1x10 0x19"), phase("bbbbbbbb", "Succeeded", NEW, "0x10 1x19"),
    phase("cccccccc", "Pending", OLD, "1x10"), phase("cccccccc", "Running", NEW, "_x12 1x17"), phase("cccccccc", "Succeeded", NEW, "_x12 0x17"),
    # the payer's join key for the identity page
    {"series": 'agent_factory_run_charge_info{principal="github:alice", run="aaaaaaaa"}', "values": "1x30"},
    {"series": 'agent_factory_run_charge_info{principal="github:alice", run="bbbbbbbb"}', "values": "1x30"},
    {"series": 'agent_factory_run_charge_info{principal="github:alice", run="cccccccc"}', "values": "1x30"},
    # the task page's join key
    {"series": 'agentrun_info{namespace="agents", run_id="aaaaaaaa", task="t1", role="impl"}', "values": "1x30"},
    {"series": 'agentrun_info{namespace="agents", run_id="bbbbbbbb", task="t1", role="review"}', "values": "1x30"},
    {"series": 'agentrun_info{namespace="agents", run_id="cccccccc", task="t1", role="impl"}', "values": "1x30"},
]


def rows(e, want):
    return {"expr": e, "eval_time": "29m",
            "exp_samples": [{"labels": '{phase="%s", run_id="%s"}' % (ph, run), "value": 1} for run, ph in want]}


ALL = [("aaaaaaaa", "Succeeded"), ("bbbbbbbb", "Succeeded"), ("cccccccc", "Running")]
tests = [{"interval": "1m", "input_series": series, "promql_expr_test": [
    rows(prep(expr("fleet", "Runs", "B")), ALL),
    rows(prep(expr("identity", "Runs", "C"), principal="github:alice"), ALL),
    rows(prep(expr("run", "Runs of this task or room", "B"), task="t1", branch="none"), ALL),
    # the run page's own query, one run at a time
    rows(prep(expr("run", "Run", "B"), run="aaaaaaaa"), [("aaaaaaaa", "Succeeded")]),
    rows(prep(expr("run", "Run", "B"), run="cccccccc"), [("cccccccc", "Running")]),
]}]
open(os.path.join(out, "rules.yaml"), "w").write("groups: []\n")
yaml.safe_dump({"rule_files": ["rules.yaml"], "evaluation_interval": "1m", "tests": tests},
               open(os.path.join(out, "tests.yaml"), "w"), sort_keys=False, width=100000)
PY

cd "$tmp" && promtool test rules tests.yaml
