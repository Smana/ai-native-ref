#!/usr/bin/env bash
# Every child reads the ai-native-ref artifact (H1). check-ai-boundary.py cannot catch a
# child pointing back at a host source: ExternalArtifact/* and GitRepository/flux-system
# are host sources it allows.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
if git grep --untracked -nE 'kind: (ExternalArtifact|GitRepository)' -- 'clusters/*.yaml'; then
  echo "error: a child names a host source; use OCIRepository/ai-native-ref" >&2
  exit 1
fi
echo "sources: every child reads OCIRepository/ai-native-ref"
