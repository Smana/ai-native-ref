#!/usr/bin/env bash
# requires: go git tar python3
#
# The pinned Maku's own config loaders read this repository's configs: every cloud's broker config
# (internal/config.Load), the merged factory values (internal/factory/config.Parse) and the Slack App's
# rendered config (internal/slackapp.LoadConfig), as a pod would at start. A strict key or a new refusal in a chart upgrade then fails here, before a release wedges a
# rollout (Maku v0.33.0 refused an http:// factoryURL without factoryInsecure: nothing offline saw it).
#
# A build error that is not the environment's fails: only no clone, no tag or an offline module or toolchain gap skips.
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
# Skip only where the environment cannot build (no clone, no tag); an archive that fails for any other reason fails,
# so a Maku bump that breaks the loader cannot turn this guard off.
git -C "$MAKU_DIR" archive "$tag" go.mod go.sum internal api cmd 2>"$tmp/archive.err" | tar -x -C "$tmp/src"
ps=("${PIPESTATUS[@]}")
if [ "${ps[0]}" -ne 0 ] || [ "${ps[1]}" -ne 0 ]; then
  echo "FAIL: cannot read $tag from $MAKU_DIR: $(head -c 200 "$tmp/archive.err")"; exit 1
fi
mkdir -p "$tmp/src/cmd/zzconfigload"
cat > "$tmp/src/cmd/zzconfigload/main.go" <<'GO'
package main

import (
	"fmt"
	"os"

	brokercfg "github.com/Smana/maku/internal/config"
	factorycfg "github.com/Smana/maku/internal/factory/config"
	"github.com/Smana/maku/internal/slackapp"
)

func main() {
	var err error
	switch os.Args[1] {
	case "broker":
		_, err = brokercfg.Load(os.Args[2])
	case "factory":
		_, err = factorycfg.Load(os.Args[2])
	case "slack":
		_, err = slackapp.LoadConfig(os.Args[2])
	}
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
GO
# build <source dir> <output binary>: 0 built; 77 the environment cannot build (offline module cache missing a
# module, or a toolchain the local Go cannot supply); 1 any other error, which is Maku's or the loader's.
ENV_ERRORS='GOPROXY=off|module lookup disabled|cannot find module providing|no required module provides|requires go >= |toolchain|dial tcp|no such host'
build() {
  (cd "$1" && GOFLAGS=-mod=mod GOPROXY=off GOCACHE="${GOCACHE:-$(go env GOCACHE)}" go build -o "$2" ./cmd/zzconfigload 2>"$tmp/build.err") && return 0
  if grep -Eq "$ENV_ERRORS" "$tmp/build.err"; then return 77; fi
  return 1
}
build "$tmp/src" "$tmp/load"; rc=$?
[ "$rc" -eq 77 ] && { echo "SKIP: cannot build $tag offline ($(head -c 160 "$tmp/build.err"))"; exit 77; }
[ "$rc" -eq 0 ] || { echo "FAIL: $tag's loaders do not build: $(head -c 400 "$tmp/build.err")"; exit 1; }

# The guard cannot be turned off by a broken tree: a syntax error and a renamed loader must FAIL, not skip.
mkdir "$tmp/mut"; cp -a "$tmp/src/." "$tmp/mut/"
printf '\nfunc (\n' >> "$tmp/mut/internal/config/config.go"
build "$tmp/mut" "$tmp/mut-load"; rc=$?
[ "$rc" -eq 1 ] || { echo "FAIL: a syntax error at the tag ended $rc, not a failure"; exit 1; }
cp "$tmp/src/internal/config/config.go" "$tmp/mut/internal/config/config.go"
sed -i 's/^func Load(/func Loadx(/' "$tmp/mut/internal/config/config.go"
build "$tmp/mut" "$tmp/mut-load"; rc=$?
[ "$rc" -eq 1 ] || { echo "FAIL: a renamed config.Load ended $rc, not a failure"; exit 1; }
echo "ok    a syntax error and a renamed Load fail the suite rather than skip it"

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
# The App's config is base's, the declaration's rendering (gcp-0 mounts it unchanged).
app = sub(open(f"{root}/tooling/base/agent-factory/slack-app/config.yaml").read())
open(f"{out}/slack-base.yaml", "w").write(app)
# The bite's copy: its first channel's notify gains an event the App draws no line for.
bite = yaml.safe_load(app)
next(iter(bite["channels"].values())).setdefault("notify", []).append("room.run_ended")
open(f"{out}/bite-slack.yaml", "w").write(yaml.safe_dump(bite, sort_keys=False))
PY
fails=0
for f in "$tmp"/cfg/broker-*.yaml; do
  if out="$("$tmp/load" broker "$f" 2>&1)"; then echo "ok    $tag loads $(basename "$f")"; else echo "FAIL  $tag refuses $(basename "$f"): $out"; fails=$((fails + 1)); fi
done
for f in "$tmp"/cfg/factory-*.yaml; do
  if out="$("$tmp/load" factory "$f" 2>&1)"; then echo "ok    $tag loads $(basename "$f")"; else echo "FAIL  $tag refuses $(basename "$f"): $out"; fails=$((fails + 1)); fi
done
for f in "$tmp"/cfg/slack-*.yaml; do
  if out="$("$tmp/load" slack "$f" 2>&1)"; then echo "ok    $tag loads $(basename "$f")"; else echo "FAIL  $tag refuses $(basename "$f"): $out"; fails=$((fails + 1)); fi
done
# It bites: a notify name the App draws no line for is refused, naming it.
if out="$("$tmp/load" slack "$tmp/cfg/bite-slack.yaml" 2>&1)" || ! grep -q 'notify "room.run_ended" has no line the App posts' <<<"$out"; then
  echo "FAIL  the App config with room.run_ended in a channel's notify was not refused for it: $out"; fails=$((fails + 1))
else echo "ok    room.run_ended in a channel's notify is refused: no line the App posts"; fi
# It bites: without factoryInsecure the same config is refused, naming factoryURL.
grep -v '^factoryInsecure:' "$tmp/cfg/broker-aws-0.yaml" > "$tmp/cfg/broker-bite.yaml"
if out="$("$tmp/load" broker "$tmp/cfg/broker-bite.yaml" 2>&1)" || ! grep -q 'factoryURL: http:// sends human tokens in the clear' <<<"$out"; then
  echo "FAIL  without factoryInsecure the broker config was not refused for factoryURL: $out"; fails=$((fails + 1))
else echo "ok    without factoryInsecure the config is refused: factoryURL"; fi
[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
