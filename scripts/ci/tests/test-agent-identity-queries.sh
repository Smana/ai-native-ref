#!/usr/bin/env bash
# requires: promtool python3
#
# Spend per identity, offline proof 7: the agent-identity panels' own queries, read from the
# dashboard JSON, evaluated by promtool on synthetic series shaped as the factory and the gateway
# export them, for two principals at once.
# - Two payers' spends in the range sum to the fleet's day, and alice's share of it reads hers.
# - Alice's run reading 1050 input with 900 cached gives her a 0.857 cache-read share, and bob, who
#   ran nothing, no data; a fleet run's tokens stay out of hers.
# - Three runs in two rooms of one task read 3 runs, 2 rooms, 1 task, though no run is live at once.
# - A counter born today shows on Spend per day, at the UTC midnight Grafana's 1d step stops at.
# - $3 of task spend with 4 merged and 1 reverted reads $1.00 per accepted PR, 3 beside it; under 3 accepted,
#   no value (the panel reads "too few merges") and the count alone.
# The panels run on VictoriaMetrics, where increase_pure counts a series from 0; promtool has none,
# and agrees with increase() on series that start at 0, as these do (test-agent-cost-rules does the same).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp" python3 - <<'PY' || exit 1
import json
import os
import sys

import yaml

root, out = os.environ["ROOT"], os.environ["OUT"]
rel = "observability/base/agent-platform/grafana-dashboard-agent-identity.yaml"
doc = next(d for d in yaml.safe_load_all(open(os.path.join(root, rel))) if d and d.get("kind") == "GrafanaDashboard")
board = json.loads(doc["spec"]["json"])
panels = {p["title"]: p for p in board["panels"]}


def q(title, ref, principal):
    """The panel's query as Grafana runs it for principal over a 1h range ($${…} is Flux's escape)."""
    expr = next(t["expr"] for t in panels[title]["targets"] if t["refId"] == ref)
    expr = expr.replace("$${principal}", principal).replace("$__range", "1h").replace("increase_pure(", "increase(")
    if "$" in expr.replace("$1", ""):
        sys.exit(f"{title} {ref}: a variable this test does not set: {expr}")
    return expr


A, B, F = "github:alice", "github:bob", "system:factory"
X = 'namespace="agent-system", pod="agent-factory-0"'
G = 'gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent="system:serviceaccount:agents:xplane-run-'


def charge(principal, run, task, room):
    labels = f'{X}, run="{run}", principal="{principal}"' + (f', task="{task}"' if task else "") + (f', room="{room}"' if room else "")
    return "agent_factory_run_charge_info{" + labels + "}"


def tokens(run, kind):
    return G + f'{run}", gen_ai_request_model="glm-5.3", gen_ai_token_type="{kind}"' + "}"


tests = [
    # Spend: alice $2 of tasks and $0.50 of rooms, bob $1 of rooms; the fleet's day is the sum.
    {"interval": "1m",
     "input_series": [
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="task"}}', "values": "0 2x50"},
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="room"}}', "values": "0 0.5x50"},
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{B}", kind="room"}}', "values": "0 1x50"},
         {"series": f'agent_factory_budget_spent_usd{{{X}, principal="{A}"}}', "values": "0 2.5x50"},
         {"series": f'agent_factory_budget_spent_usd{{{X}, principal="{B}"}}', "values": "0 1x50"},
         {"series": f'agent_factory_budget_spent_usd{{{X}, principal="{F}"}}', "values": "0 3.5x50"},
     ],
     "promql_expr_test": [
         {"expr": q("Spend in the range, by kind", "A", A), "eval_time": "50m",
          "exp_samples": [{"labels": '{kind="task"}', "value": 2}, {"labels": '{kind="room"}', "value": 0.5}]},
         {"expr": f'sum({q("Spend in the range, by kind", "A", A)}) + sum({q("Spend in the range, by kind", "A", B)})',
          "eval_time": "50m", "exp_samples": [{"value": 3.5}]},
         {"expr": q("The fleet's day", "A", A), "eval_time": "50m", "exp_samples": [{"value": 3.5}]},
         {"expr": q("The fleet's day", "C", A), "eval_time": "50m", "exp_samples": [{"value": 2.5 / 3.5}]},
     ]},
    # Spend per day: Grafana evaluates a 1d step at UTC midnight (time 0 here) and stops at the last
    # midnight. The series was born that day: hour 1 onwards, 0.5 more every hour. The query at the
    # midnight, `increase(x[1d] offset -1d)`, reads the day that begins there: by definition of a
    # negative offset, `increase(x[1d])` at midnight + 1d (promtool loads samples up to the evaluation
    # time and cannot read ahead, so the test evaluates that and VictoriaMetrics proves the offset live).
    # It reads the 11.5 spent to date, and nothing for a principal that spent nothing; the unshifted
    # [1d] at the midnight reads nothing, the "No data" the screenshot showed.
    {"interval": "1h",
     "input_series": [
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="task"}}', "values": "_ 0+0.5x30"},
     ],
     "promql_expr_test": [
         {"expr": q("Spend per day", "A", A).replace(" offset -1d", ""), "eval_time": "24h", "exp_samples": [{"labels": '{kind="task"}', "value": 11.5}]},
         {"expr": q("Spend per day", "A", B).replace(" offset -1d", ""), "eval_time": "24h", "exp_samples": []},
         {"expr": q("Spend per day", "A", A).replace(" offset -1d", ""), "eval_time": "0m", "exp_samples": []},
     ]},
    # Tokens: alice's run reads 1050 input with 900 cached; a fleet run's tokens are not hers.
    {"interval": "1m",
     "input_series": [
         {"series": tokens("aaaaaaaa", "input"), "values": "0 1050x50"},
         {"series": tokens("aaaaaaaa", "cached_input"), "values": "0 900x50"},
         {"series": tokens("aaaaaaaa", "output"), "values": "0 10x50"},
         {"series": tokens("cccccccc", "input"), "values": "0 5000x50"},
         {"series": tokens("cccccccc", "cached_input"), "values": "0 100x50"},
         {"series": charge(A, "aaaaaaaa", "3buqdlot", "3buqdlot"), "values": "1x50"},
         {"series": charge(F, "cccccccc", "4buqdlot", "4buqdlot"), "values": "1x50"},
     ],
     "promql_expr_test": [
         {"expr": q("Cache-read share", "A", A), "eval_time": "50m", "exp_samples": [{"value": 900 / 1050}]},
         {"expr": q("Cache-read share", "A", B), "eval_time": "50m", "exp_samples": []},
         {"expr": q("Tokens by type", "A", A), "eval_time": "50m",
          "exp_samples": [{"labels": '{gen_ai_token_type="input"}', "value": 1050},
                          {"labels": '{gen_ai_token_type="cached_input"}', "value": 900},
                          {"labels": '{gen_ai_token_type="output"}', "value": 10}]},
     ]},
    # Work: three runs of one task in two rooms, one after the other; bob's room run is not alice's.
    {"interval": "1m",
     "input_series": [
         {"series": charge(A, "aaaaaaaa", "3buqdlot", "3buqdlot"), "values": "1x20"},
         {"series": charge(A, "bbbbbbbb", "3buqdlot", "3buqdlot"), "values": "_x20 1x20"},
         {"series": charge(A, "cccccccc", "3buqdlot", "4buqdlot"), "values": "_x40 1x10"},
         {"series": charge(B, "dddddddd", "", "5buqdlot"), "values": "1x50"},
     ],
     "promql_expr_test": [
         {"expr": q("Runs · rooms · tasks", "A", A), "eval_time": "50m", "exp_samples": [{"value": 3}]},
         {"expr": q("Runs · rooms · tasks", "B", A), "eval_time": "50m", "exp_samples": [{"value": 2}]},
         {"expr": q("Runs · rooms · tasks", "C", A), "eval_time": "50m", "exp_samples": [{"value": 1}]},
         {"expr": q("Runs · rooms · tasks", "A", B), "eval_time": "50m", "exp_samples": [{"value": 1}]},
         {"expr": q("Runs · rooms · tasks", "C", B), "eval_time": "50m", "exp_samples": []},
     ]},
    # Outcomes: alice's $3 of tasks, 2 merged and 1 reverted; bob's $4, 1 merged and 1 reverted.
    {"interval": "1m",
     "input_series": [
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="task"}}', "values": "0 3x50"},
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="room"}}', "values": "0 7x50"},
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{B}", kind="task"}}', "values": "0 4x50"},
     ] + [
         {"series": f'agent_factory_pr_outcomes_total{{{X}, principal="{who}", class="review", outcome="{o}", repository="Smana/cloud-native-ref"}}',
          "values": "0 1x50"}
         for who, o in ((A, "auto_merged"), (A, "human_merged"), (A, "reverted"), (B, "human_merged"))
     ] + [
         # alice's second merged PR of the range is auto-merged too: 3 merged, 1 reverted = 2 accepted
         {"series": f'agent_factory_pr_outcomes_total{{{X}, principal="{A}", class="docs", outcome="auto_merged", repository="Smana/cloud-native-ref"}}',
          "values": "0 1x50"},
         # bob has 1 accepted: under the floor of 3, it reads no value, never $4 for one lucky merge
     ],
     "promql_expr_test": [
         {"expr": q("Cost per accepted PR", "A", A), "eval_time": "50m", "exp_samples": []},
         {"expr": q("Cost per accepted PR", "B", A), "eval_time": "50m", "exp_samples": [{"value": 2}]},
         {"expr": q("Cost per accepted PR", "A", B), "eval_time": "50m", "exp_samples": []},
         {"expr": q("Cost per accepted PR", "B", B), "eval_time": "50m", "exp_samples": [{"value": 1}]},
     ]},
    # Three accepted PRs (4 merged, 1 reverted) over $3 of tasks read $1.00 each.
    {"interval": "1m",
     "input_series": [
         {"series": f'agent_factory_charged_usd_total{{{X}, principal="{A}", kind="task"}}', "values": "0 3x50"},
     ] + [
         {"series": f'agent_factory_pr_outcomes_total{{{X}, principal="{A}", class="review", outcome="{o}", repository="Smana/cloud-native-ref"}}',
          "values": "0 " + str(n) + "x50"}
         for o, n in (("auto_merged", 3), ("human_merged", 1), ("reverted", 1))
     ],
     "promql_expr_test": [
         {"expr": q("Cost per accepted PR", "A", A), "eval_time": "50m", "exp_samples": [{"value": 1}]},
         {"expr": q("Cost per accepted PR", "B", A), "eval_time": "50m", "exp_samples": [{"value": 3}]},
     ]},
]
open(os.path.join(out, "rules.yaml"), "w").write("groups: []\n")
yaml.safe_dump({"rule_files": ["rules.yaml"], "evaluation_interval": "1m", "tests": tests},
               open(os.path.join(out, "tests.yaml"), "w"), sort_keys=False, width=1000)
PY

cd "$tmp" && promtool test rules tests.yaml
