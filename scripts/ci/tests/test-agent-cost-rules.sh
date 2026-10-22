#!/usr/bin/env bash
# requires: promtool python3
#
# Truthful costs, offline proof 3: the costs read through llm_gateway:charge_usd_per_mtoken, evaluated
# by promtool on synthetic series shaped as the agent router's scrape leaves them (vmpodscrape.yaml:
# cache tokens counted inside input). The rules are the committed ones: the generated
# llm-gateway-prices group, AnthropicFleetNearCap, AgentMeterInputExcludesCache, and the agent-run
# dashboard's Cost panel query.
# - The measured reply (input 1050 with 900 read and 50 written, output 10, on Opus) costs $0.00103
#   on the Cost panel.
# - A cache-heavy Opus day of $5 ($20 at list prices) does not fire AnthropicFleetNearCap; $14 does.
#   GLM spend never counts toward it.
# - The meter's input-excludes-cache counter, born at 1, fires AgentMeterInputExcludesCache.
# Annotations are stripped from the copy promtool reads: it compares them exactly, and
# test-agent-alert-annotations owns them.
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


def docs(rel):
    return [d for d in yaml.safe_load_all(open(os.path.join(root, rel))) if isinstance(d, dict)]


def group(rel, name):
    found = [g for d in docs(rel) if d.get("kind") == "VMRule" for g in d["spec"]["groups"] if g["name"] == name]
    if len(found) != 1:
        sys.exit(f"{rel}: expected one group {name}, found {len(found)}")
    return found[0]


def alert(rel, group_name, name):
    found = [r for r in group(rel, group_name)["rules"] if r.get("alert") == name]
    if len(found) != 1:
        sys.exit(f"{rel}: expected one alert {name}, found {len(found)}")
    found[0].pop("annotations", None)
    return found[0]


prices = group("infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml", "llm-gateway-prices")
near = alert("observability/base/agent-platform/vmrule.yaml", "agent-gateway", "AnthropicFleetNearCap")
excludes = alert("observability/base/agent-platform/vmrule-agent-factory.yaml", "agent-factory",
                 "AgentMeterInputExcludesCache")
THRESHOLD = " > 13.6"
if not near["expr"].endswith(THRESHOLD):
    sys.exit(f"AnthropicFleetNearCap no longer ends with{THRESHOLD}: update this test's days")
# The alert's figure, without its threshold, so a test can read the dollars.
fleet = {"record": "test:anthropic_fleet:usd24h", "expr": near["expr"][:-len(THRESHOLD)]}
dashboard = next(d for d in docs("observability/base/agent-platform/grafana-dashboard-agent-run.yaml")
                 if d.get("kind") == "GrafanaDashboard")
panel = next(p for p in json.loads(dashboard["spec"]["json"])["panels"] if p.get("title") == "Cost (USD)")
# The panel as Grafana runs it on run "wire" over a 1h range ($${run} is Flux's escape for ${run}).
query = panel["targets"][0]["expr"].replace("$${run}", "wire").replace("$__range", "1h")
if "$" in query or "'" in query:
    sys.exit(f"the Cost panel's query holds a variable this test does not set: {query}")
yaml.safe_dump({"groups": [prices, {"name": "cost-alerts", "rules": [near, excludes, fleet]}]},
               open(os.path.join(out, "rules.yaml"), "w"), sort_keys=False)
open(os.path.join(out, "panel.promql"), "w").write(query)
PY

PANEL="$(cat "$tmp/panel.promql")"
G='gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent="system:serviceaccount:agents:xplane-run-'
M='agent_factory_meter_input_excludes_cache_runs_total{namespace="agent-system", pod="agent-factory-0"'
cat > "$tmp/tests.yaml" <<EOF
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  # The reply the wire test sends, measured on agentgateway 1.6: input 1050 counts the 900 read and
  # the 50 written. 1050 x 4.00 - 900 x 3.80 + 50 x 1.00 + 10 x 20.00 = 1030 per million. The
  # reasoning series is inside output and has no charge: it adds nothing.
  - interval: 1m
    input_series:
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0 1050x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0 900x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0 50x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0 10x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="reasoning"}', values: '0 4x10'}
    promql_expr_test:
      - expr: '${PANEL}'
        eval_time: 10m
        exp_samples:
          - value: 0.00103
  # A cache-heavy Opus day: 4.75M input with 4.0M read and 0.2M written, 0.05M output. The meter's
  # formula: 0.55M x 4.00 + 4.0M x 0.20 + 0.2M x 5.00 + 0.05M x 20.00 = \$5.00; input at list price
  # would read \$20. GLM-5.3's \$20 that day is not Anthropic's.
  - interval: 1m
    input_series:
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0+95000x50 4750000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0+80000x50 4000000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0+4000x50 200000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0+1000x50 50000x40'}
      - {series: '${G}glm", gen_ai_request_model="glm-5.3", gen_ai_token_type="input"}', values: '0+200000x50 10000000x40'}
      - {series: '${G}glm", gen_ai_request_model="glm-5.3", gen_ai_token_type="output"}', values: '0+20000x50 1000000x40'}
    promql_expr_test:
      - expr: test:anthropic_fleet:usd24h
        eval_time: 90m
        exp_samples:
          - {labels: 'test:anthropic_fleet:usd24h', value: 5}
    alert_rule_test:
      - {eval_time: 90m, alertname: AnthropicFleetNearCap, exp_alerts: []}
  # The same mix at 2.8x: \$14.00, over 80% of B6's \$17. It crosses \$13.60 at about 49 minutes.
  - interval: 1m
    input_series:
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0+266000x50 13300000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0+224000x50 11200000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0+11200x50 560000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0+2800x50 140000x40'}
    promql_expr_test:
      - expr: test:anthropic_fleet:usd24h
        eval_time: 90m
        exp_samples:
          - {labels: 'test:anthropic_fleet:usd24h', value: 14}
    alert_rule_test:
      - {eval_time: 45m, alertname: AnthropicFleetNearCap, exp_alerts: []}
      - eval_time: 90m
        alertname: AnthropicFleetNearCap
        exp_alerts:
          - exp_labels: {severity: warning}
  # The meter counts a run whose input came without its cache tokens. A new series is born at 1
  # (its first increment) and fires at once, until it is an hour old. An hour-old series fires when
  # it moves, and not while it stands still.
  - interval: 1m
    input_series:
      - {series: '${M}, model="claude-opus-5-5"}', values: '_x65 1x135'}
      - {series: '${M}, model="glm-5.3"}', values: '2x200'}
      - {series: '${M}, model="glm-5.3-flash"}', values: '2x100 3x100'}
    alert_rule_test:
      - {eval_time: 64m, alertname: AgentMeterInputExcludesCache, exp_alerts: []}
      - eval_time: 70m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: claude-opus-5-5}
      - eval_time: 110m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: claude-opus-5-5}
          - exp_labels: {severity: warning, model: glm-5.3-flash}
      - eval_time: 130m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: glm-5.3-flash}
      - {eval_time: 170m, alertname: AgentMeterInputExcludesCache, exp_alerts: []}
EOF

cd "$tmp" && promtool test rules tests.yaml
