#!/usr/bin/env bash
# requires: python3
#
# Capability profiles design, gate 5: the MCP Allow lists committed in
# infrastructure/base/agent-gateway/mcp.yaml and the model rules in policy-capabilities.yaml are
# exactly what scripts/ci/gen-capabilities.py renders from infrastructure/base/agent-gateway/profiles/,
# as AG8 holds the budgets' cost string to meter.prices. A list or a rule edited by hand, or a profile
# changed without --write, fails here with the diff. The real tree.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
python3 "$ROOT/scripts/ci/gen-capabilities.py" "$ROOT"
