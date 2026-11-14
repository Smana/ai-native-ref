#!/usr/bin/env bash
# The factory's config, checked by the factory's own Maku (Maku factory resources): for each cloud, the values
# file's `config:` (base's ConfigMap, then the cloud's valuesFrom ConfigMaps) and the Factory, Repository and
# MergePolicy objects its Flux child applies (kustomize build), the Flux variables replaced with placeholders,
# through `maku config validate`: it lays the objects over the file and refuses what the factory would refuse,
# one line each. Then a bite: a mode written on a MergePolicy is refused (B4).
#
# The binary is the release the HelmRelease's image pins, checked against the sha256 below: a version bump
# without its digest fails here, so bump both. It is cached under $XDG_CACHE_HOME (default ~/.cache).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# maku-linux-amd64 of the release, from its maku.sha256 asset.
MAKU_PIN="v0.47.0"
MAKU_SHA256="a0bd0ab62e9c1747cae9771e3ee06a289634a1d185cfe8ea9e3b42e856fd28f3"  # pragma: allowlist secret

python3 -c 'import yaml' 2>/dev/null || { echo "FAIL: PyYAML is not installed" >&2; exit 1; }
values="tooling/base/agent-factory/helm-values-configmap.yaml"
version="$(python3 -c '
import sys, yaml
cm = yaml.safe_load(open(sys.argv[1]))
print(yaml.safe_load(cm["data"]["values.yaml"])["image"]["tag"].partition("@")[0])' "$values")"
if [ "$version" != "$MAKU_PIN" ]; then
  echo "FAIL: the HelmRelease's image is $version, this script's maku is $MAKU_PIN: bump MAKU_PIN and MAKU_SHA256 with it" >&2
  exit 1
fi

cache="${XDG_CACHE_HOME:-$HOME/.cache}/ai-native-ref/maku/$MAKU_PIN"
maku="$cache/maku-linux-amd64"
if ! echo "$MAKU_SHA256  $maku" | sha256sum -c --status - 2>/dev/null; then
  mkdir -p "$cache"
  curl -fsSL --retry 3 --retry-delay 2 -o "$maku.part" \
    "https://github.com/Smana/maku/releases/download/$MAKU_PIN/maku-linux-amd64"
  echo "$MAKU_SHA256  $maku.part" | sha256sum -c --quiet - || { rm -f "$maku.part"; echo "FAIL: maku $MAKU_PIN does not match MAKU_SHA256" >&2; exit 1; }
  chmod +x "$maku.part"
  mv "$maku.part" "$maku"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fails=0
for cloud in aws-0 gcp-0; do
  kustomize build "tooling/$cloud/agent-factory/resources" > "$tmp/$cloud-objects.yaml"
  python3 scripts/ci/factory_config.py render "$cloud" "$tmp/$cloud-objects.yaml" "$tmp/$cloud"
  if out="$("$maku" config validate --config "$tmp/$cloud/config.yaml" "$tmp/$cloud/manifests.yaml" 2>&1)"; then
    echo "ok    $cloud: $out"
  else
    echo "FAIL  $cloud: maku $MAKU_PIN refuses the config:"; sed 's/^/      /' <<<"$out"; fails=$((fails + 1))
  fi
done

# It bites: a mode written on a MergePolicy, docs-links made shadow there, is refused: the mode is the
# binding's (Maku reusable merge policies, B4). A binding that does not resolve drops its class without
# refusing anything, so scripts/ci/tests/test-agent-resolved-classes.sh, which compares the resolved
# classes with their snapshot, is what catches that.
python3 - "$tmp/aws-0/manifests.yaml" "$tmp/bite.yaml" <<'PY'
import sys, yaml
docs = [d for d in yaml.safe_load_all(open(sys.argv[1])) if d]
policy = next(d for d in docs if d["kind"] == "MergePolicy" and d["metadata"]["name"] == "docs-links")
assert "repositoryRef" not in policy["spec"], "the bite needs docs-links as a class policy"
policy["spec"]["shadow"] = True
yaml.safe_dump_all(docs, open(sys.argv[2], "w"), allow_unicode=True)
PY
if out="$("$maku" config validate --config "$tmp/aws-0/config.yaml" "$tmp/bite.yaml" 2>&1)" \
   || ! grep -q "MergePolicy/docs-links: Invalid: class docs-links: mode is the binding's" <<<"$out"; then
  echo "FAIL  a mode on a MergePolicy was not refused (B4):"; sed 's/^/      /' <<<"$out"; fails=$((fails + 1))
else
  echo "ok    a mode on a MergePolicy is refused: MergePolicy/docs-links, B4"
fi
[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
