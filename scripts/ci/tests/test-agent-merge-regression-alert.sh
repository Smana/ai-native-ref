#!/usr/bin/env bash
# requires: promtool python3
#
# Merge gate classes MC7, offline proof 13: one regression verdict fires
# AgentFactoryMergeRegression; healthy and inconclusive verdicts never do.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os, sys, yaml
path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule-agent-factory.yaml")
rules = [r for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
         for g in d["spec"]["groups"] for r in g["rules"] if r.get("alert") == "AgentFactoryMergeRegression"]
if len(rules) != 1:
    sys.exit("AgentFactoryMergeRegression: want exactly one rule")
rules[0].pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "t", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY
S='maku_factory_monitor_verdicts_total{class="dead-links", repository="Smana/cloud-native-ref"'
cat >"$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - {series: '${S}, verdict="regression"}', values: '0 0 1 1 1'}
      - {series: '${S}, verdict="healthy"}', values: '0 1 2 3 4'}
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentFactoryMergeRegression, exp_alerts: [{exp_labels: {severity: warning, class: dead-links, repository: Smana/cloud-native-ref}}]}
  - interval: 1m
    input_series:
      - {series: '${S}, verdict="inconclusive"}', values: '0 1 2 3 4'}
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentFactoryMergeRegression, exp_alerts: []}
EOT
cd "$tmp" && promtool test rules tests.yaml
