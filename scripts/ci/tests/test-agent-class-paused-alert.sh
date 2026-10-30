#!/usr/bin/env bash
# requires: promtool python3
#
# Human path AM9: a class the breaker holds for 7 days fires AgentFactoryClassPausedLong, with the
# annotations the rule carries; a class paused for less, not paused, absent, shadow, unarmed or
# class="" never does. The live set in the rule's regex is derived from the factory's config.
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
# The live classes of the config (live: true, or monitored and not shadow) must be the rule's regex.
import re
cm = yaml.safe_load(open(os.path.join(os.environ["ROOT"], "tooling/base/agent-factory/helm-values-configmap.yaml")))
vals = yaml.safe_load(cm["data"]["values.yaml"])
live = set()
for repo in vals["config"]["repositories"]:
    if repo["name"] != "Smana/cloud-native-ref":
        if any(not (c or {}).get("shadow") and ((c or {}).get("live") or (c or {}).get("monitor")) for c in repo["classes"].values()):
            sys.exit("%s has a live class: the alert selects Smana/cloud-native-ref only" % repo["name"])
        continue
    live = {n for n, c in repo["classes"].items() if not (c or {}).get("shadow") and ((c or {}).get("live") or (c or {}).get("monitor"))}
m = re.search(r'class=~"([^"]+)"', rules[0]["expr"])
if not m or set(m.group(1).split("|")) != live:
    sys.exit("alert regex %s != live classes in the config %s" % (m and m.group(1), sorted(live)))
# The dashboard's "Classes paused" tile counts the same live set.
dash = yaml.safe_load(open(os.path.join(os.environ["ROOT"], "observability/base/agent-platform/grafana-dashboard-agent-factory.yaml")))
import json
panel = [pn for pn in json.loads(dash["spec"]["json"] if "spec" in dash else dash["data"][next(iter(dash["data"]))])["panels"] if pn.get("title") == "Classes paused"]
if len(panel) != 1 or ('class=~"%s"' % m.group(1)) not in panel[0]["targets"][0]["expr"].replace('\\"', '"'):
    sys.exit("the Classes paused panel must select the alert's live classes %s" % m.group(1))
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
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="alert-rules"}'
        values: '0x10100'
      # shadow and unarmed classes, and the empty class, paused for 8 days: no alert
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="dead-links"}'
        values: '1x11600'
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="tests"}'
        values: '1x11600'
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class=""}'
        values: '1x11600'
      - series: 'maku_factory_class_paused{repository="Smana/ai-native-ref",class="docs-links"}'
        values: '1x11600'
      # a live class paused 8 days fires
      - series: 'maku_factory_class_paused{repository="Smana/cloud-native-ref",class="revert"}'
        values: '1x11600'
    alert_rule_test:
      - eval_time: 7d1m
        alertname: AgentFactoryClassPausedLong
        exp_alerts:
          - exp_labels: {severity: warning, repository: Smana/cloud-native-ref, class: docs-links}
            exp_annotations:
              summary: "docs-links on Smana/cloud-native-ref has been paused for 7 days"
              description: "The breaker holds the class. Three clean mature merges lift it (recoverAfter); factory/drill lifts it only if added before factory/revert, or on a rebuilt factory. Read the window: scripts/shadow-merge-tally.sh --repo Smana/cloud-native-ref --class docs-links --outcomes --since <date> in Smana/maku. The gauge keeps its last value, so a class with no monitor can stay at 1 after it recovered: it clears at the class's next decision or watched merge. Check the class's labels and recent PRs before acting."
              runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#know-before-the-go"
              dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
          - exp_labels: {severity: warning, repository: Smana/cloud-native-ref, class: revert}
            exp_annotations:
              summary: "revert on Smana/cloud-native-ref has been paused for 7 days"
              description: "The breaker holds the class. Three clean mature merges lift it (recoverAfter); factory/drill lifts it only if added before factory/revert, or on a rebuilt factory. Read the window: scripts/shadow-merge-tally.sh --repo Smana/cloud-native-ref --class revert --outcomes --since <date> in Smana/maku. The gauge keeps its last value, so a class with no monitor can stay at 1 after it recovered: it clears at the class's next decision or watched merge. Check the class's labels and recent PRs before acting."
              runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/12-live-auto-merge-drill.md#know-before-the-go"
              dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
      - eval_time: 6d
        alertname: AgentFactoryClassPausedLong
        exp_alerts: []
EOT
cd "$tmp" && promtool test rules tests.yaml
