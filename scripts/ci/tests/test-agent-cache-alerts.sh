#!/usr/bin/env bash
# requires: promtool python3
#
# The prompt cache alerts (cache design C1), evaluated by promtool on synthetic series shaped as
# the agent router's scrape leaves them (vmpodscrape.yaml). A dropped marker fires
# AgentCacheReadZero within two scrapes of a run's first 100k input tokens; a share under 60% over
# 15 minutes fires AgentCacheReadShareLow only with 200k input tokens in the window, so one
# condensation does not; public runs (Z.ai) are never selected. Annotations are stripped from the
# copy promtool reads: it compares them exactly, and test-agent-alert-annotations owns them.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os
import sys
import yaml

path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule.yaml")
groups = [g for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
          for g in d["spec"]["groups"] if g["name"] == "agent-cache"]
if not groups:
    sys.exit("no group agent-cache in observability/base/agent-platform/vmrule.yaml")
for rule in groups[0]["rules"]:
    rule.pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "agent-cache", "rules": groups[0]["rules"]}]},
               open(os.environ["OUT"], "w"), sort_keys=False)
PY

S='gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_provider_name="anthropic", ar_agent="system:serviceaccount:agents:xplane-run-'
cat > "$tmp/tests.yaml" <<EOF
rule_files: [rules.yaml]
evaluation_interval: 30s
tests:
  # A dropped marker: input grows 20k a scrape, nothing is ever read.
  - interval: 30s
    input_series:
      - series: '${S}zero", gen_ai_token_type="input"}'
        values: '0+20000x40'
    alert_rule_test:
      - {eval_time: 2m, alertname: AgentCacheReadZero, exp_alerts: []}
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-zero"}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-zero"}
  # A dropped marker whose cached_input series exists at zero (Anthropic answers
  # cache_read_input_tokens: 0 on every reply): the same alerts fire as for an absent series.
  - interval: 30s
    input_series:
      - series: '${S}zeroseries", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}zeroseries", gen_ai_token_type="cached_input"}'
        values: '0x40'
    alert_rule_test:
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-zeroseries"}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-zeroseries"}
  # A run that dropped its marker and then ended: input reaches 120k and stays flat (the gateway
  # keeps exporting the series). It fires at 3m; at 20m the 15m window (5m-20m) holds no increase,
  # so the alert has resolved.
  - interval: 30s
    input_series:
      - series: '${S}ended", gen_ai_token_type="input"}'
        values: '0+20000x6 120000x40'
    alert_rule_test:
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-ended"}
      - {eval_time: 20m, alertname: AgentCacheReadZero, exp_alerts: []}
  # A healthy run: 90% read. Neither fires.
  - interval: 30s
    input_series:
      - series: '${S}ok", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}ok", gen_ai_token_type="cached_input"}'
        values: '0+18000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
    promql_expr_test:
      - expr: agent_run:cache_read_share:ratio15m
        eval_time: 16m
        exp_samples:
          - labels: 'agent_run:cache_read_share:ratio15m{ar_agent="system:serviceaccount:agents:xplane-run-ok"}'
            value: 0.9
  # A gradual loss: 50% read on 600k input over 15 minutes.
  - interval: 30s
    input_series:
      - series: '${S}half", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}half", gen_ai_token_type="cached_input"}'
        values: '0+10000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-half"}
  # The same 50% on 90k input in the window (a condensation in a quiet run): under the volume floor.
  - interval: 30s
    input_series:
      - series: '${S}quiet", gen_ai_token_type="input"}'
        values: '0+3000x40'
      - series: '${S}quiet", gen_ai_token_type="cached_input"}'
        values: '0+1500x40'
    alert_rule_test:
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
  # A public run on Z.ai reads nothing explicit: never selected.
  - interval: 30s
    input_series:
      - series: 'gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_provider_name="zai", ar_agent="system:serviceaccount:agents:xplane-run-public", gen_ai_token_type="input"}'
        values: '0+20000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
EOF

cd "$tmp" && promtool test rules tests.yaml
