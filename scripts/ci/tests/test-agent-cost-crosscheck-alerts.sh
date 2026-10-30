#!/usr/bin/env bash
# requires: promtool python3
#
# The cost cross-check (B-2 XC3-XC7), evaluated by promtool on synthetic series shaped as the two
# sides leave them: maku_factory_run_settled_usd{run} (the ledger) and the agent router's
# agentgateway_gen_ai_client_cost_usd_total{ar_agent} (the gateway). An agreeing run is silent;
# 1.5% off fires after 15 minutes; a 0.005 USD gap on a 0.20 USD run is silent (the floor); a run
# still spending is silent; a run with an Envoy series is silent; gateway cost with no ledger
# series fires; a Missing catalog lookup fires AgentGatewayCostUnpriced. Annotations are stripped
# from the copy promtool reads: it compares them exactly, and test-agent-alert-annotations owns them.
# The file carries Flux's `$$1` escape; the copy promtool reads has the `$1` postBuild leaves.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
command -v promtool >/dev/null || { echo "SKIP: promtool not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os
import sys
import yaml

path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule-agent-factory.yaml")
groups = [g for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
          for g in d["spec"]["groups"] if g["name"] == "agent-cost-crosscheck"]
if len(groups) != 1:
    sys.exit(f"{path}: expected one group agent-cost-crosscheck, found {len(groups)}")
rules = groups[0]["rules"]
want = ["agent_cost:gateway_run_usd", "AgentCostCrossCheckMismatch", "AgentGatewayCostUnpriced"]
got = [r.get("record") or r.get("alert") for r in rules]
if got != want:
    sys.exit(f"agent-cost-crosscheck holds {got}, want {want}")
for r in rules:
    r.pop("annotations", None)
    r["expr"] = r["expr"].replace("$$", "$")
yaml.safe_dump({"groups": [{"name": "agent-cost-crosscheck", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY

A='system:serviceaccount:agents:xplane-run-'
G='agentgateway_gen_ai_client_cost_usd_total{namespace="agent-gateway", gen_ai_request_model="claude-opus-5-5", ar_agent="'"$A"
L='maku_factory_run_settled_usd{namespace="agent-system", pod="agent-factory-0", run="'
E='gen_ai_client_token_usage_sum{namespace="envoy-gateway-system", gen_ai_token_type="input", ar_agent="'"$A"
Z="$(printf '0x%s ' 720)"   # 6 h of nothing first: increase() then has no window-edge extrapolation
cat > "$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 30s
tests:
  # Every run spends for 10 minutes (20 scrapes), then stops; the ledger holds its total throughout.
  #  agree: 10.00 both sides.   off: gateway 10.00, ledger 10.15 (1.5%).   floor: 0.20 vs 0.205.
  #  live: still spending, ledger 5 behind.   envoy: 10 vs 12, with an Envoy series.
  #  unseen: gateway 3.00, no ledger series.
  - interval: 30s
    input_series:
      - {series: '${G}agree"}', values: '${Z}0+0.5x20 10x100'}
      - {series: '${L}agree"}', values: '${Z}10x120'}
      - {series: '${G}off"}', values: '${Z}0+0.5x20 10x100'}
      - {series: '${L}off"}', values: '${Z}10.15x120'}
      - {series: '${G}floor"}', values: '${Z}0 0.1 0.2x100'}
      - {series: '${L}floor"}', values: '${Z}0.205x120'}
      - {series: '${G}live"}', values: '${Z}0+0.5x120'}
      - {series: '${L}live"}', values: '${Z}5x120'}
      - {series: '${G}envoy"}', values: '${Z}0+0.5x20 10x100'}
      - {series: '${L}envoy"}', values: '${Z}12x120'}
      - {series: '${E}envoy"}', values: '${Z}0+100x120'}
      - {series: '${G}unseen"}', values: '${Z}0+0.15x19 3x101'}
    alert_rule_test:
      # The run stops 10m in (at 370m); idle from 380m; for 15m: not before 395m.
      - {eval_time: 385m, alertname: AgentCostCrossCheckMismatch, exp_alerts: []}
      - {eval_time: 393m, alertname: AgentCostCrossCheckMismatch, exp_alerts: []}
      - eval_time: 397m
        alertname: AgentCostCrossCheckMismatch
        exp_alerts:
          - exp_labels: {severity: warning, run: off}
          - exp_labels: {severity: warning, run: unseen}
      - eval_time: 403m
        alertname: AgentCostCrossCheckMismatch
        exp_alerts:
          - exp_labels: {severity: warning, run: off}
          - exp_labels: {severity: warning, run: unseen}
      # The unseen run's gauge would be gone by now (1 h after its end): the branch resolves at 40 m.
      - eval_time: 415m
        alertname: AgentCostCrossCheckMismatch
        exp_alerts:
          - exp_labels: {severity: warning, run: off}

  # A Missing lookup, two scrapes of it.
  - interval: 30s
    input_series:
      - {series: 'agentgateway_cost_catalog_lookups_total{namespace="agent-gateway", status="Exact", gen_ai_request_model="claude-opus-5-5", ar_agent="${A}ok"}', values: '0+5x40'}
      - {series: 'agentgateway_cost_catalog_lookups_total{namespace="agent-gateway", status="Missing", gen_ai_request_model="glm-9", ar_agent="${A}bad"}', values: '0 0 0 1 2 2x30'}
    alert_rule_test:
      - {eval_time: 1m, alertname: AgentGatewayCostUnpriced, exp_alerts: []}
      - eval_time: 3m
        alertname: AgentGatewayCostUnpriced
        exp_alerts:
          - exp_labels: {severity: warning, status: Missing, gen_ai_request_model: glm-9, ar_agent: "${A}bad"}
EOT

cd "$tmp" && promtool test rules tests.yaml
