#!/usr/bin/env bash
# requires: jq
#
# scripts/ops/k8s/gcp-0-{platform-gates,v21-checks}.sh against PATH-stubbed kubectl, curl and bao:
# a healthy cluster passes with exit 0, each broken fact is its own FAIL line with exit 1, and
# neither script calls a kubectl verb other than get, logs and port-forward. No test contacts a cluster.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATES="$HERE/../../ops/k8s/gcp-0-platform-gates.sh"
V21="$HERE/../../ops/k8s/gcp-0-v21-checks.sh"
fails=0
fail() { printf 'FAIL  %s\n' "$*" >&2; fails=$((fails + 1)); }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
cat >"$tmp/bin/kubectl" <<'STUB'
#!/usr/bin/env bash
# The fixture cluster: BROKEN=1 breaks one fact per check family.
args=()
while [ $# -gt 0 ]; do
  case "$1" in --context|-n) shift ;; *) args+=("$1") ;; esac
  shift
done
echo "${args[0]}" >>"$CALLS"
set -- "${args[@]}"
ready() { printf '{"type":"Ready","status":"%s","message":"m"}' "$1"; }
B=${BROKEN:-0}
case "$*" in
  "get kustomizations"*)
    s=$([ "$B" = 1 ] && echo False || echo True)
    echo "{\"items\":[{\"metadata\":{\"namespace\":\"flux-system\",\"name\":\"zitadel\"},\"spec\":{},\"status\":{\"conditions\":[$(ready "$s")]}},
      {\"metadata\":{\"namespace\":\"flux-system\",\"name\":\"llm-platform\"},\"spec\":{\"suspend\":true}}]}" ;;
  "get helmreleases"*|"get certificates"*|"get clustersecretstores"*|"get externalsecrets"*)
    echo "{\"items\":[{\"metadata\":{\"namespace\":\"security\",\"name\":\"x\"},\"spec\":{},\"status\":{\"conditions\":[$(ready True)]}}]}" ;;
  "get clusters.postgresql.cnpg.io"*)
    boot='"recovery":{"source":"origin"}'; [ "$B" = 1 ] && boot='"initdb":{}'
    echo "{\"items\":[{\"metadata\":{\"namespace\":\"security\",\"name\":\"xplane-zitadel-cnpg-cluster\"},
      \"spec\":{\"bootstrap\":{$boot},\"externalClusters\":[{\"name\":\"origin\",\"plugin\":{\"parameters\":{\"serverName\":\"zitadel-20260828\"}}}]},
      \"status\":{\"conditions\":[$(ready True),{\"type\":\"ContinuousArchiving\",\"status\":\"True\"}]}}]}" ;;
  "get configmap gke-gcp-0-vars -o json")
    echo '{"data":{"public_domain_name":"gcp.example.io","identity_provider_url":"https://auth.gcp.example.io"}}' ;;
  "get configmap gke-gcp-0-vars -o jsonpath"*) printf 'https://auth.gcp.example.io' ;;
  "get deploy zitadel"*) printf 2 ;;
  "get nodes -o json")
    gv='{"metadata":{"name":"gv-1","labels":{"cloud.google.com/gke-nodepool":"agents-gvisor","sandbox.gke.io/runtime":"gvisor"}},"status":{"conditions":[{"type":"Ready","status":"True"}]}}'
    [ "$B" = 1 ] && gv='{"metadata":{"name":"nap-1","labels":{"cloud.google.com/gke-nodepool":"nap-e2-standard-4-abc","sandbox.gke.io/runtime":"gvisor"}},"status":{"conditions":[{"type":"Ready","status":"True"}]}}'
    echo "{\"items\":[$gv,
      {\"metadata\":{\"name\":\"static-a\",\"labels\":{\"cloud.google.com/gke-nodepool\":\"static\"}},\"status\":{\"conditions\":[{\"type\":\"Ready\",\"status\":\"True\"}]}},
      {\"metadata\":{\"name\":\"static-b\",\"labels\":{\"cloud.google.com/gke-nodepool\":\"static\"}},\"status\":{\"conditions\":[{\"type\":\"Ready\",\"status\":\"True\"}]}}]}" ;;
  "get pods -l app.kubernetes.io/name=agent-factory -o json")
    node=$([ "$B" = 1 ] && echo static-b || echo static-a)
    echo "{\"items\":[{\"metadata\":{\"name\":\"agent-factory-0\"},\"spec\":{\"nodeName\":\"$node\"},
      \"status\":{\"conditions\":[{\"type\":\"Ready\",\"status\":\"True\"}],\"containerStatuses\":[{\"restartCount\":0}]}}]}" ;;
  "get pods -l app.kubernetes.io/name=zitadel"*) printf 'static-b\n' ;;
  "get pods -l app.kubernetes.io/name=room-broker"*) printf 'room-broker-0' ;;
  "get pods -l app.kubernetes.io/name=agents-headroom"*)
    printf 'agents-headroom-0\tRunning\t%s\n' "$([ "$B" = 1 ] && echo nap-1 || echo gv-1)" ;;
  "get ciliumnetworkpolicies.cilium.io agent-factory"*)
    echo '{"spec":{"egress":[{"toEntities":["all"]},{"toFQDNs":[{"matchName":"api.github.com"}],"toPorts":[{}]}]}}' ;;
  "get events -A"*)
    q='{"reason":"TriggeredScaleUp","message":"pod triggered scale-up: agents-gvisor 0->1","involvedObject":{}}'
    [ "$B" = 1 ] && q="$q"',{"reason":"FailedScaleUp","message":"GCE quota exceeded","involvedObject":{"namespace":"agents","name":"run"}}'
    echo "{\"items\":[$q]}" ;;
  "get cronjob"*) echo '{"items":[{"metadata":{"name":"openbao-snapshot"},"status":{}}]}' ;;
  "get "*) echo '{"items":[]}' ;;
  "logs "*--previous*) exit 1 ;;
  "logs "*) echo 'time=t level=INFO msg="agent-factory starting" version=v0.15.2' ;;
  "port-forward "*) exec sleep 30 ;;
  *) echo "unstubbed: $*" >&2; exit 1 ;;
esac
STUB
cat >"$tmp/bin/curl" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do url=$a; done
case "$url" in
  */.well-known/openid-configuration) printf '{"issuer":"https://auth.gcp.example.io"}\n200' ;;
  */metrics) printf 'rooms_authn_jwks_last_refresh_timestamp_seconds{issuer="https://auth.gcp.example.io"} %s\n' \
    "$(awk -v t="$(date +%s)" 'BEGIN {printf "%.9e", t - 60}')" ;;
  */api/v2/alerts*) echo '[]' ;;
  *) exit 7 ;;
esac
STUB
printf '#!/usr/bin/env bash\necho %s\n' "'{\"initialized\":true,\"sealed\":false,\"type\":\"gcpckms\"}'" >"$tmp/bin/bao"
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH" CALLS="$tmp/calls"

for s in "$GATES" "$V21"; do
  name=$(basename "$s")
  bash "$s" >/dev/null 2>"$tmp/err" && fail "$name without a context exits 0"
  grep -q usage "$tmp/err" || fail "$name without a context prints no usage"
  BROKEN=0 bash "$s" ctx >"$tmp/ok" 2>&1 || { fail "$name on a healthy fixture exits non-zero"; sed 's/^/      /' "$tmp/ok" >&2; }
  grep -q '^FAIL' "$tmp/ok" && fail "$name on a healthy fixture prints a FAIL"
  BROKEN=1 bash "$s" ctx >"$tmp/$name.bad" 2>&1 && fail "$name on a broken fixture exits 0"
done
# $tmp/ok is gcp-0-v21-checks.sh's: the gauge, in exponent form, reads as 60s old.
grep -qE "JWKS (59|60|61|62)s ago" "$tmp/ok" || fail "the broker's JWKS gauge age is misread"

expect() { # file pattern
  grep -q "^FAIL .*$2" "$1" || fail "$(basename "$1") lacks a FAIL for: $2"
}
expect "$tmp/gcp-0-platform-gates.sh.bad" "Kustomizations not Ready"
expect "$tmp/gcp-0-platform-gates.sh.bad" "bootstrap is 'initdb', expected recovery:zitadel-20260828"
expect "$tmp/gcp-0-v21-checks.sh.bad" "shares static-b with ZITADEL"
expect "$tmp/gcp-0-v21-checks.sh.bad" "gVisor nodes outside agents-gvisor"
expect "$tmp/gcp-0-v21-checks.sh.bad" "scale-up failures"
expect "$tmp/gcp-0-v21-checks.sh.bad" "agents-headroom-0 Running on nap-1"
grep -q 'kubectl --context ctx cordon static-b' "$tmp/gcp-0-v21-checks.sh.bad" || fail "the co-location hint names no cordon command"

bad_verbs=$(sort -u "$CALLS" | grep -vxE 'get|logs|port-forward')
[ -z "$bad_verbs" ] || fail "a script called kubectl verbs beyond get/logs/port-forward: $bad_verbs"

[ "$fails" -eq 0 ] || exit 1
echo "gcp-0 check scripts: healthy passes, broken fails per fact, read-only verbs only"
