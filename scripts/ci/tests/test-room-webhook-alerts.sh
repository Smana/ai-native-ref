#!/usr/bin/env bash
# requires: promtool python3
#
# RoomWebhookDisabled (factory interfaces F6), evaluated by promtool on synthetic series shaped as the
# broker's scrape leaves them: rooms_webhook_disabled{subscriber} is 1 once three deliveries were given
# up, until its generation is bumped. The alert fires after 1 minute of 1, stays silent at 0, and
# resolves when the series returns to 0. Annotations are stripped from the copy promtool reads: it
# compares them exactly, and test-agent-alert-annotations owns them.
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
         for r in g["rules"] if r.get("alert") == "RoomWebhookDisabled"]
if len(rules) != 1:
    sys.exit(f"{path}: expected one alert RoomWebhookDisabled in group agent-factory, found {len(rules)}")
rules[0].pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "agent-factory", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY

S='rooms_webhook_disabled{namespace="agent-system", pod="room-broker-0", subscriber="slack-app"}'
cat > "$tmp/tests.yaml" <<EOT
rule_files: [rules.yaml]
evaluation_interval: 30s
tests:
  # 0 for 2 minutes (silent), 1 for 5 (fires once it has held 1 minute), 0 again (resolves).
  - interval: 30s
    input_series:
      - {series: '${S}', values: '0x4 1x9 0x10'}
    alert_rule_test:
      - {eval_time: 1m, alertname: RoomWebhookDisabled, exp_alerts: []}
      - {eval_time: 2m30s, alertname: RoomWebhookDisabled, exp_alerts: []}
      - eval_time: 4m
        alertname: RoomWebhookDisabled
        exp_alerts:
          - exp_labels: {severity: warning, subscriber: slack-app}
      - {eval_time: 8m, alertname: RoomWebhookDisabled, exp_alerts: []}
EOT

cd "$tmp" && promtool test rules tests.yaml
