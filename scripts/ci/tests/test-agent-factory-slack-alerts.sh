#!/usr/bin/env bash
# requires: promtool python3
#
# The Slack decision path's two alerts, evaluated by promtool on synthetic series shaped as the
# scrapes leave them: maku_rooms_slack_decisions_total{result, decision} from the broker, and
# factory_slack_requests_total{route, outcome} from the App.
#
# Both are aggregates by necessity — neither counter carries a user, a principal, a room or an
# approval, and this gate is where that stays true: a label that would make the design's
# per-person clauses computable fails here first (the selectors below match the shipped
# expressions exactly). See the group's comment in the VMRule.
#
# The boundary is exact on purpose. A burst that starts from zero inside the window leaves
# increase() nothing to extrapolate on that edge — its counter zero-point rule pins the start — so
# five approvals in ten minutes read 5 and stay silent under `> 5`, and six read 6 and fire.
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
wanted = ("SlackDecisionsSpike", "SlackCardUpdatesFailing")
groups = [g for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
          for g in d["spec"]["groups"] if g["name"] == "agent-factory"]
rules = [r for g in groups for r in g["rules"] if r.get("alert") in wanted]
missing = [w for w in wanted if w not in {r["alert"] for r in rules}]
if missing:
    sys.exit(f"{path}: no alert {', '.join(missing)} in group agent-factory")
# Annotations are stripped from the copy promtool reads: it compares them exactly, and
# test-agent-alert-annotations owns them.
for rule in rules:
    rule.pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "agent-factory", "rules": rules}]},
               open(os.environ["OUT"], "w"), sort_keys=False)
PY

D='maku_rooms_slack_decisions_total{namespace="agent-system", pod="room-broker-0", result="approved", decision="approve"}'
E='factory_slack_requests_total{namespace="agent-system", pod="factory-slack-app-0", route="'
cat > "$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  # Five approvals inside ten minutes read exactly 5 through increase() and stay silent: "> 5" is
  # the boundary, and it holds at the burst and ten minutes later.
  - interval: 1m
    input_series:
      - {series: '${D}', values: '0x10 5x40'}
    alert_rule_test:
      - {eval_time: 10m, alertname: SlackDecisionsSpike, exp_alerts: []}
      - {eval_time: 15m, alertname: SlackDecisionsSpike, exp_alerts: []}
      - {eval_time: 21m, alertname: SlackDecisionsSpike, exp_alerts: []}
  # Six in ten minutes fires, and resolves once the burst has aged out: the rule is a rate over
  # ten minutes, not a total.
  - interval: 1m
    input_series:
      - {series: '${D}', values: '0x10 6x40'}
    alert_rule_test:
      - {eval_time: 10m, alertname: SlackDecisionsSpike, exp_alerts: []}
      - {eval_time: 15m, alertname: SlackDecisionsSpike, exp_alerts: [{exp_labels: {severity: warning}}]}
      - {eval_time: 22m, alertname: SlackDecisionsSpike, exp_alerts: []}
  # The App failing an approval-card update: one route's errors hold the alert pending for the
  # hour, so a single flapping card never pages, and an hour of them does.
  - interval: 1m
    input_series:
      - {series: '${E}interactions", outcome="error"}', values: '0x20 1+1x100'}
    alert_rule_test:
      - {eval_time: 19m, alertname: SlackCardUpdatesFailing, exp_alerts: []}
      - {eval_time: 75m, alertname: SlackCardUpdatesFailing, exp_alerts: []}
      - {eval_time: 90m, alertname: SlackCardUpdatesFailing, exp_alerts: [{exp_labels: {severity: warning}}]}
  # The same hour on the webhook route, which the expression's route regex must also cover.
  - interval: 1m
    input_series:
      - {series: '${E}webhooks", outcome="error"}', values: '0x20 1+1x100'}
    alert_rule_test:
      - {eval_time: 75m, alertname: SlackCardUpdatesFailing, exp_alerts: []}
      - {eval_time: 90m, alertname: SlackCardUpdatesFailing, exp_alerts: [{exp_labels: {severity: warning}}]}
  # A route outside the regex (events, whose failures are counted by another alert) never fires.
  - interval: 1m
    input_series:
      - {series: '${E}events", outcome="error"}', values: '0x20 1+1x100'}
    alert_rule_test:
      - {eval_time: 90m, alertname: SlackCardUpdatesFailing, exp_alerts: []}
EOT

cd "$tmp" && promtool test rules tests.yaml
