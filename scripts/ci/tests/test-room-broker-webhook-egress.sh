#!/usr/bin/env bash
# requires: python3
#
# Factory interfaces F6, R21: the broker's webhook egress is exactly what gen-webhook-egress.py
# renders from the broker's config, base and each overlay, and each cluster subscriber names a
# Service whose selector is its app.kubernetes.io/name. A rule edited by hand, a subscriber added
# without --write, or an overlay patch its kustomization does not list fails here with the diff.
# The real tree.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
python3 -I "$ROOT/scripts/ci/gen-webhook-egress.py" "$ROOT"
