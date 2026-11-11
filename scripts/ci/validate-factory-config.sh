#!/usr/bin/env bash
# The factory's config, checked by the factory's own Maku (Maku factory resources): for each cloud, the values
# file's `config:` (base's ConfigMap, then the cloud's valuesFrom ConfigMaps) and the Factory, Repository and
# MergePolicy objects its Flux child applies (kustomize build), the Flux variables replaced with placeholders,
# through `maku config validate`: it lays the objects over the file and refuses what the factory would refuse,
# one line each. Then a bite: a class both live and shadow is refused, naming R32.
#
# The binary is the release the HelmRelease's image pins, checked against the sha256 below: a version bump
# without its digest fails here, so bump both. It is cached under $XDG_CACHE_HOME (default ~/.cache).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# maku-linux-amd64 of the release, from its maku.sha256 asset.
MAKU_PIN="v0.43.0"
MAKU_SHA256="9c2f5b548753ab6ae8b5f0ac0e862cbeb594f604e3518ddf3f1eca51df69ebc6"  # pragma: allowlist secret

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

# It bites: docs-links, live on the host, made shadow too, is refused for R32.
python3 - "$tmp/aws-0/manifests.yaml" "$tmp/bite.yaml" <<'PY'
import sys, yaml
docs = [d for d in yaml.safe_load_all(open(sys.argv[1])) if d]
policy = next(d for d in docs if d["kind"] == "MergePolicy" and d["spec"]["repositoryRef"] == "cloud-native-ref")
assert policy["spec"]["classes"]["docs-links"].get("live") is True, "the bite needs docs-links live on the host"
policy["spec"]["classes"]["docs-links"]["shadow"] = True
yaml.safe_dump_all(docs, open(sys.argv[2], "w"), allow_unicode=True)
PY
if out="$("$maku" config validate --config "$tmp/aws-0/config.yaml" "$tmp/bite.yaml" 2>&1)" \
   || ! grep -q 'MergePolicy/cloud-native-ref: Invalid: .*class docs-links: live and shadow never together (R32)' <<<"$out"; then
  echo "FAIL  a class both live and shadow was not refused for R32:"; sed 's/^/      /' <<<"$out"; fails=$((fails + 1))
else
  echo "ok    a class both live and shadow is refused: MergePolicy/cloud-native-ref, R32"
fi
[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
