#!/usr/bin/env bash
# requires: kustomize python3
#
# Reusable merge policies (Maku B17): no migration changes a class the gate decides on. For each
# cloud, the pinned Maku resolves the classes of the objects its Flux child applies
# (`maku config validate --resolved`), and they must equal the snapshot captured from origin/main
# before the first migration, fixtures/resolved-classes-<cloud>.json. Then scripts/ci/factory_config.py's
# own resolution (the B4 table in Python, which every suite reading the classes relies on) must
# equal Maku's on the same manifests. A deliberate class change updates the snapshot in the same
# pull request.
#
# The binary is validate-factory-config.sh's: the release the HelmRelease pins, cached by it. Without
# the cache (no network in this run) this SKIPs.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT" || exit 1
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
pin="$(sed -n 's/^MAKU_PIN="\(.*\)"/\1/p' scripts/ci/validate-factory-config.sh)"
maku="${XDG_CACHE_HOME:-$HOME/.cache}/ai-native-ref/maku/$pin/maku-linux-amd64"
[ -x "$maku" ] || { echo "SKIP: no maku $pin cached (scripts/ci/validate-factory-config.sh downloads it)"; exit 77; }

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fails=0
for cloud in aws-0 gcp-0; do
  kustomize build "tooling/$cloud/agent-factory/resources" > "$tmp/$cloud-objects.yaml" || { echo "FAIL: kustomize build $cloud"; exit 1; }
  python3 scripts/ci/factory_config.py render "$cloud" "$tmp/$cloud-objects.yaml" "$tmp/$cloud"
  if ! "$maku" config validate --config "$tmp/$cloud/config.yaml" --resolved "$tmp/$cloud/manifests.yaml" > "$tmp/$cloud.json" 2>"$tmp/$cloud.err"; then
    echo "FAIL  $cloud: maku $pin refuses the config:"; sed 's/^/      /' "$tmp/$cloud.err"; fails=$((fails + 1)); continue
  fi
  if diff -u "scripts/ci/tests/fixtures/resolved-classes-$cloud.json" "$tmp/$cloud.json" > "$tmp/$cloud.diff"; then
    echo "ok    $cloud: the resolved classes equal the snapshot"
  else
    echo "FAIL  $cloud: a resolved class changed (fixtures/resolved-classes-$cloud.json):"; sed 's/^/      /' "$tmp/$cloud.diff" | head -60; fails=$((fails + 1))
  fi
  if out="$(python3 - "$cloud" "$tmp/$cloud.json" <<'PY'
import json, re, sys
sys.path.insert(0, "scripts/ci")
import factory_config

UNITS = {"h": 3600, "m": 60, "s": 1}


def seconds(v):
    parts = re.fullmatch(r"((\d+)h)?((\d+)m)?((\d+)s)?", v)
    return sum(int(n) * UNITS[u] for n, u in ((parts[2], "h"), (parts[4], "m"), (parts[6], "s")) if n) if parts and v else v


def canon(v, key=""):
    """Maku's JSON omits the zero values; a Go duration prints as 168h0m0s, the YAML as 168h."""
    if isinstance(v, dict):
        out = {k: canon(x, k) for k, x in v.items()}
        return {k: x for k, x in out.items() if x not in (None, False, 0, "", [], {})}
    if isinstance(v, list):
        return [canon(x) for x in v]
    if isinstance(v, str) and key in ("within", "followUpWindow"):
        return seconds(v)
    return v


cloud, maku = sys.argv[1], json.load(open(sys.argv[2]))
py = {r["name"]: r.get("classes") or {} for r in factory_config.config(cloud=cloud)["repositories"]}
bad = [f"{repo} {cls}" for repo in sorted(set(maku) | set(py)) for cls in sorted(set(maku.get(repo, {})) | set(py.get(repo, {})))
       if canon(maku.get(repo, {}).get(cls)) != canon(factory_config.yaml.safe_load(factory_config.substitute(
           factory_config.yaml.safe_dump(py.get(repo, {}).get(cls)), cloud)))]
print(", ".join(bad))
sys.exit(1 if bad else 0)
PY
)"; then
    echo "ok    $cloud: factory_config.py resolves every class as Maku does"
  else
    echo "FAIL  $cloud: factory_config.py and Maku resolve differently: $out"; fails=$((fails + 1))
  fi
done
[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
