#!/usr/bin/env bash
# requires: promtool python3
#
# Human path AM9: a class the breaker holds for 7 days fires AgentFactoryClassPausedLong, with the
# annotations the rule carries; a class paused for less, or not paused, never does.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os, sys, yaml
path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule-agent-factory.yaml")
rules = [r for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
         for g in d["spec"]["groups"] for r in g["rules"] if r.get("alert") == "AgentFactoryClassPausedLong"]
if len(rules) != 1:
    sys.exit("AgentFactoryClassPausedLong: want exactly one rule")
yaml.safe_dump({"groups": [{"name": "t", "rules": rules}]}, open(os.environ["OUT"], "w"), sort_keys=False)
PY
# Quoted heredoc: ${private_domain_name} stays literal, as in the rule.
cat >"$tmp/tests.yaml" <<'EOT'
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="docs-links"}'
        values: '1x10100'
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="dead-links"}'
        values: '0x10100'
    alert_rule_test:
      - eval_time: 7d1m
        alertname: AgentFactoryClassPausedLong
        exp_alerts:
          - exp_labels: {severity: warning, repository: Smana/cloud-native-ref, class: docs-links}
            exp_annotations:
              summary: "docs-links on Smana/cloud-native-ref has been paused for 7 days"
              description: "The breaker holds the class. Three clean mature merges lift it (recoverAfter), or a maintainer's factory/drill on a drill revert. Read the window: scripts/shadow-merge-tally.sh --repo Smana/cloud-native-ref --class docs-links --outcomes --since <date> in Smana/maku."
              runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#know-before-the-go"
              dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
      - eval_time: 6d
        alertname: AgentFactoryClassPausedLong
        exp_alerts: []
EOT
cd "$tmp" && promtool test rules tests.yaml
