#!/usr/bin/env bash
# requires: python3
#
# Truthful costs TC3, offline proof 1: the llm-gateway-prices group committed in
# infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml is exactly what scripts/ci/gen-prices.py
# renders from meter.prices (tooling/base/agent-factory/helm-values-configmap.yaml), as AG8 holds
# the budgets' cost string to the same table. A row edited by hand, or a price changed without
# --write, fails here with the diff. The same holds for the agentgateway catalog overlay
# (infrastructure/base/agent-gateway/model-catalog.yaml, cost cross-check XC2). The real tree.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
python3 "$ROOT/scripts/ci/gen-prices.py" "$ROOT"
