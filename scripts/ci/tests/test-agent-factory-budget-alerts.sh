#!/usr/bin/env bash
# requires: promtool python3
#
# The factory's daily budget alert (truthful costs TC8), evaluated by promtool on synthetic series
# shaped as the factory's scrape leaves them: maku_factory_budget_{cap,spent}_usd{principal},
# set by the meter's leader (agent-platform v0.17.1). AgentFactoryDailyBudgetHigh fires past 80% of
# a principal's USD cap, not at it; a day overrun past its cap still fires, since spent is
# unclamped; it resolves when the meter records the principal at 0 on the day's first tick.
# Annotations are stripped from the copy promtool reads: it compares them exactly, and
# test-agent-alert-annotations owns them.
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
rules = [r for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
         for g in d["spec"]["groups"] if g["name"] == "agent-factory"
         for r in g["rules"] if r.get("alert") == "AgentFactoryDailyBudgetHigh"]
if len(rules) != 1:
    sys.exit(f"{path}: expected one alert AgentFactoryDailyBudgetHigh in group agent-factory, found {len(rules)}")
rules[0].pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "agent-factory", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY

C='maku_factory_budget_cap_usd{namespace="agent-system", pod="agent-factory-0", principal="'
P='maku_factory_budget_spent_usd{namespace="agent-system", pod="agent-factory-0", principal="'
cat > "$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 30s
tests:
  # The fleet's day, \$42.50: \$34.00 is exactly 80% and stays silent, \$34.01 fires after 5 minutes.
  # A person past their \$8.50 (unclamped, 110%) fires. The meter's day-start 0 resolves both.
  - interval: 30s
    input_series:
      - {series: '${C}system:factory"}', values: '42.5x60'}
      - {series: '${P}system:factory"}', values: '34x20 34.01x30 0x10'}
      - {series: '${C}github:alice"}', values: '8.5x60'}
      - {series: '${P}github:alice"}', values: '2x20 9.35x30 0x10'}
      - {series: '${C}github:bob"}', values: '8.5x60'}
      - {series: '${P}github:bob"}', values: '6.8x60'}
    alert_rule_test:
      - {eval_time: 9m, alertname: AgentFactoryDailyBudgetHigh, exp_alerts: []}
      - {eval_time: 14m, alertname: AgentFactoryDailyBudgetHigh, exp_alerts: []}
      - eval_time: 16m
        alertname: AgentFactoryDailyBudgetHigh
        exp_alerts:
          - exp_labels: {severity: warning, namespace: agent-system, pod: agent-factory-0, principal: "system:factory"}
          - exp_labels: {severity: warning, namespace: agent-system, pod: agent-factory-0, principal: "github:alice"}
      - {eval_time: 26m, alertname: AgentFactoryDailyBudgetHigh, exp_alerts: []}
EOT

cd "$tmp" && promtool test rules tests.yaml
