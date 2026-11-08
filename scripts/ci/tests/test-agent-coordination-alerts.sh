#!/usr/bin/env bash
# requires: promtool python3
#
# v4 coordination's alerts on synthetic series shaped as Maku's scrape leaves them: every
# maku_factory_coordination_* counter is born at its first increment, so a first failure or
# refusal must fire, and a family filed inside the window counts as a state change.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
command -v promtool >/dev/null || { echo "SKIP: promtool not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os, sys, yaml
path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule-agent-factory.yaml")
wanted = ("AgentFactoryCoordinationRecoveryRequired", "AgentFactoryCoordinationIntegrationFailed", "AgentFactoryCoordinationAuthorizationLost",
          "AgentFactoryCoordinationStalled")
rules = [r for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
         for g in d["spec"]["groups"] for r in g["rules"] if r.get("alert") in wanted]
if sorted(r["alert"] for r in rules) != sorted(wanted):
    sys.exit(f"{path}: want exactly one of each of {', '.join(wanted)}")
# promtool compares annotations exactly; test-agent-alert-annotations owns them.
for rule in rules:
    rule.pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "t", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY

I='maku_factory_coordination_integration_runs_total{repository="Smana/a", purpose="final"'
R='maku_factory_coordination_admission_refusals_total{repository="Smana/b"'
T='maku_factory_tasks{repository="Smana/a", source="issue", predicted_class="", tier="", principal=""'
F='maku_factory_coordination_families_total{repository="Smana/a"'
cat >"$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  # A recovery standing past 15 minutes fires; one under it, or a primary with none, does not.
  - interval: 1m
    input_series:
      - {series: 'maku_factory_coordination_recovery_age_seconds{repository="Smana/a"}', values: '840 900 960 1020'}
      - {series: 'maku_factory_coordination_recovery_age_seconds{repository="Smana/b"}', values: '60 120 180 240'}
    alert_rule_test:
      - {eval_time: 1m, alertname: AgentFactoryCoordinationRecoveryRequired, exp_alerts: []}
      - {eval_time: 2m, alertname: AgentFactoryCoordinationRecoveryRequired, exp_alerts: [{exp_labels: {severity: warning, repository: Smana/a}}]}
  # A first failure fires on its own series' birth; a pass never does.
  - interval: 1m
    input_series:
      - {series: '${I}, result="checks_failed"}', values: '_ _ 1 1 1'}
      - {series: '${I}, result="passed"}', values: '1 2 3 4 5'}
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentFactoryCoordinationIntegrationFailed, exp_alerts: [{exp_labels: {severity: warning, repository: Smana/a, purpose: final, result: checks_failed}}]}
      - {eval_time: 30m, alertname: AgentFactoryCoordinationIntegrationFailed, exp_alerts: []}
  - interval: 1m
    input_series:
      - {series: '${I}, result="infrastructure_failed"}', values: '1x10 2x10'}
    alert_rule_test:
      - {eval_time: 12m, alertname: AgentFactoryCoordinationIntegrationFailed, exp_alerts: [{exp_labels: {severity: warning, repository: Smana/a, purpose: final, result: infrastructure_failed}}]}
  # Lost authority fires; a stale plan is a refusal, not lost authority.
  - interval: 1m
    input_series:
      - {series: '${R}, reason="repository_permission"}', values: '_ _ 1 1 1'}
      - {series: '${R}, reason="stale_plan"}', values: '_ _ 1 1 1'}
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentFactoryCoordinationAuthorizationLost, exp_alerts: [{exp_labels: {severity: warning, repository: Smana/b, reason: repository_permission}}]}
  # Stalled: a family filed at 0 and nothing after; silent inside the 24 h, firing past it.
  - interval: 1m
    input_series:
      - {series: '${T}, phase="Coordinating"}', values: '1x1600'}
      - {series: '${F}, outcome="filed"}', values: '1x1600'}
    alert_rule_test:
      - {eval_time: 1380m, alertname: AgentFactoryCoordinationStalled, exp_alerts: []}
      - {eval_time: 1530m, alertname: AgentFactoryCoordinationStalled, exp_alerts: [{exp_labels: {severity: warning, repository: Smana/a}}]}
  # A plan version confirmed at 20 h is a state change at 25.5 h; no Coordinating parent, no alert.
  - interval: 1m
    input_series:
      - {series: '${T}, phase="Coordinating"}', values: '1x1600'}
      - {series: '${F}, outcome="filed"}', values: '1x1600'}
      - {series: 'maku_factory_coordination_plan_versions_total{repository="Smana/a", outcome="confirmed"}', values: '_x1199 1x400'}
      - {series: '${T}, phase="Implementing"}', values: '1x1600'}
    alert_rule_test:
      - {eval_time: 1530m, alertname: AgentFactoryCoordinationStalled, exp_alerts: []}
EOT
cd "$tmp" && promtool test rules tests.yaml
