#!/usr/bin/env bash
# Push the manifest tree as ghcr.io/smana/ai-native-ref:<tag> and sign its digest keyless.
# Signs the digest, never the tag, so a re-pushed tag cannot inherit the signature.
# Usage: push-artifact.sh <tag> <commit-sha>   (release.yaml and ci.yaml's prerelease)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
tag="${1:?tag}"; sha="${2:?commit sha}"
repo="ghcr.io/smana/ai-native-ref"

rm -rf dist && mkdir dist
cp -a clusters infrastructure security tooling observability apps flux dist/
digest="$(flux push artifact "oci://${repo}:${tag}" \
  --path=dist \
  --source="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-Smana/ai-native-ref}" \
  --revision="${tag}@sha1:${sha}" \
  --output json | jq -r .digest)"
[ -n "$digest" ] && [ "$digest" != null ] || { echo "error: flux push returned no digest" >&2; exit 1; }
cosign sign --yes "${repo}@${digest}"

echo "pushed ${repo}:${tag}@${digest}"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### ${repo}:${tag}"
    echo
    echo "digest: \`${digest}\`"
  } >> "$GITHUB_STEP_SUMMARY"
fi
