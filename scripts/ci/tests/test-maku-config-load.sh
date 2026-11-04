#!/usr/bin/env bash
# requires: go git tar python3
#
# The pinned Maku's own config loaders read this repository's configs: every cloud's broker config
# (internal/config.Load) and the merged factory values (internal/factory/config.Parse), as a pod would
# at start. A strict key or a new refusal in a chart upgrade then fails here, before a release wedges a
# rollout (Maku v0.33.0 refused an http:// factoryURL without factoryInsecure: nothing offline saw it).
#
# Offline: the source is the pinned tag of a local Maku clone (MAKU_DIR, default ~/Sources/maku), read with
# `git archive`, and its modules come from the Go module cache (GOPROXY=off). Without either this SKIPs (77):
# no network is added to `task check`. test-room-broker-factory-insecure.py holds the same rule, statically,
# wherever this skips.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MAKU_DIR="${MAKU_DIR:-$HOME/Sources/maku}"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tag="$(sed -n 's/.*ghcr.io\/smana\/maku-broker:\(v[0-9.]*\)@sha256.*/\1/p;s/^ *tag: "\(v[0-9.]*\)@sha256.*/\1/p' "$ROOT/infrastructure/base/room-broker/app.yaml" | head -1)"
[ -n "$tag" ] || { echo "FAIL: no maku tag in room-broker/app.yaml"; exit 1; }
git -C "$MAKU_DIR" rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1 || { echo "SKIP: no $tag in $MAKU_DIR"; exit 77; }

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/src" "$tmp/cfg"
git -C "$MAKU_DIR" archive "$tag" go.mod go.sum internal api cmd 2>/dev/null | tar -x -C "$tmp/src" || { echo "SKIP: cannot read $tag"; exit 77; }
mkdir -p "$tmp/src/cmd/zzconfigload"
cat > "$tmp/src/cmd/zzconfigload/main.go" <<'GO'
package main

import (
	"fmt"
	"os"

	brokercfg "github.com/Smana/maku/internal/config"
	factorycfg "github.com/Smana/maku/internal/factory/config"
)

func main() {
	var err error
	switch os.Args[1] {
	case "broker":
		_, err = brokercfg.Load(os.Args[2])
	case "factory":
		_, err = factorycfg.Load(os.Args[2])
	}
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
GO
(cd "$tmp/src" && GOFLAGS=-mod=mod GOPROXY=off GOCACHE="${GOCACHE:-$(go env GOCACHE)}" go build -o "$tmp/load" ./cmd/zzconfigload 2>"$tmp/build.err") \
  || { echo "SKIP: cannot build $tag offline ($(head -c 160 "$tmp/build.err"))"; exit 77; }

# The rendered inputs: Flux's ${var} substituted with values the loaders accept; the factory's merged values
# (the base ConfigMap, then aws-0's internal principal; Helm merges maps and replaces lists).
ROOT="$ROOT" TMP="$tmp/cfg" python3 - <<'PY'
import os, re, yaml
root, out = os.environ["ROOT"], os.environ["TMP"]
subs = {"oidc_issuer_url": "https://issuer.test", "oidc_jwks_uri": "https://issuer.test/keys",
        "identity_provider_url": "https://auth.example.test", "private_domain_name": "priv.example.test",
        "cluster_name": "cluster-0"}
sub = lambda t: re.sub(r"\$\{(\w+)\}", lambda m: subs.get(m.group(1), "unset-var-" + m.group(1)), t)
for cloud in ("base", "aws-0", "gcp-0"):
    open(f"{out}/broker-{cloud}.yaml", "w").write(sub(open(f"{root}/infrastructure/{cloud}/room-broker/config.yaml").read()))
def values(path):
    for d in yaml.safe_load_all(open(path)):
        if d and d.get("kind") == "ConfigMap":
            return yaml.safe_load(d["data"]["values.yaml"])
def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **{k: merge(a.get(k), v) if k in a else v for k, v in b.items()}}
    return b
base = values(f"{root}/tooling/base/agent-factory/helm-values-configmap.yaml")
for name, extra in (("base", None), ("aws-0", "tooling/aws-0/agent-factory/helm-values-internal.yaml"),
                    ("gcp-0", "tooling/gcp-0/agent-factory/helm-values-sponsored.yaml")):
    v = merge(base, values(f"{root}/{extra}")) if extra else base
    open(f"{out}/factory-{name}.yaml", "w").write(sub(yaml.safe_dump(v["config"])))
PY
fails=0
for f in "$tmp"/cfg/broker-*.yaml; do
  if out="$("$tmp/load" broker "$f" 2>&1)"; then echo "ok    $tag loads $(basename "$f")"; else echo "FAIL  $tag refuses $(basename "$f"): $out"; fails=$((fails + 1)); fi
done
for f in "$tmp"/cfg/factory-*.yaml; do
  if out="$("$tmp/load" factory "$f" 2>&1)"; then echo "ok    $tag loads $(basename "$f")"; else echo "FAIL  $tag refuses $(basename "$f"): $out"; fails=$((fails + 1)); fi
done
# It bites: without factoryInsecure the same config is refused, naming factoryURL.
grep -v '^factoryInsecure:' "$tmp/cfg/broker-aws-0.yaml" > "$tmp/cfg/broker-bite.yaml"
if out="$("$tmp/load" broker "$tmp/cfg/broker-bite.yaml" 2>&1)" || ! grep -q 'factoryURL: http:// sends human tokens in the clear' <<<"$out"; then
  echo "FAIL  without factoryInsecure the broker config was not refused for factoryURL: $out"; fails=$((fails + 1))
else echo "ok    without factoryInsecure the config is refused: factoryURL"; fi
[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
