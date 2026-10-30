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
# Reap any forward a broken script leaked, so a failing run cannot hold the stub's ports.
trap '[ -f "$PF_LOG" ] && xargs -r kill <"$PF_LOG" 2>/dev/null; rm -rf "$tmp"' EXIT
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
# KWARN=1: every call warns on stderr, as kubectl does on a deprecated API; the JSON must survive it.
[ "${KWARN:-0}" = 1 ] && echo 'Warning: stub deprecation notice' >&2
# KFAIL=<resource>: `get <resource>` fails, as on a missing CRD or an RBAC denial.
if [ -n "${KFAIL:-}" ] && [ "$1 ${2:-}" = "get $KFAIL" ]; then echo "stub: $KFAIL forbidden" >&2; exit 1; fi
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
  "get deploy agents-headroom"*) printf '%s' "${HEADROOM:-1}" ;;
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
  "port-forward "*) echo $$ >>"$PF_LOG"; exec sleep 30 ;;
  *) echo "unstubbed: $*" >&2; exit 1 ;;
esac
STUB
cat >"$tmp/bin/curl" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do url=$a; done
case "$url" in
  */.well-known/openid-configuration) printf '{"issuer":"https://auth.gcp.example.io"}\n200' ;;
  */metrics) printf 'maku_rooms_authn_jwks_last_refresh_timestamp_seconds{issuer="https://auth.gcp.example.io"} %s\n' \
    "$(awk -v t="$(date +%s)" 'BEGIN {printf "%.9e", t - 60}')" ;;
  */api/v2/alerts*) echo '[]' ;;
  *) exit 7 ;;
esac
STUB
printf '#!/usr/bin/env bash\necho %s\n' "'{\"initialized\":true,\"sealed\":false,\"type\":\"gcpckms\"}'" >"$tmp/bin/bao"
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH" CALLS="$tmp/calls" PF_LOG="$tmp/pf.pids"

for s in "$GATES" "$V21"; do
  name=$(basename "$s")
  bash "$s" >/dev/null 2>"$tmp/err" && fail "$name without a context exits 0"
  grep -q usage "$tmp/err" || fail "$name without a context prints no usage"
  BROKEN=0 bash "$s" ctx >"$tmp/ok" 2>&1 || { fail "$name on a healthy fixture exits non-zero"; sed 's/^/      /' "$tmp/ok" >&2; }
  grep -q '^FAIL' "$tmp/ok" && fail "$name on a healthy fixture prints a FAIL"
  BROKEN=1 bash "$s" ctx >"$tmp/$name.bad" 2>&1 && fail "$name on a broken fixture exits 0"
done
# Both runs of gcp-0-v21-checks.sh opened forwards; its EXIT trap must have reaped every one.
[ -s "$PF_LOG" ] || fail "gcp-0-v21-checks.sh opened no port-forward"
# A killed forward lingers until its SIGTERM lands and it is reaped: allow 2s. A leaked one sleeps 30s.
while read -r pid; do
  for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.2; done
  kill -0 "$pid" 2>/dev/null && fail "a stub port-forward (pid $pid) outlived gcp-0-v21-checks.sh"
done <"$PF_LOG"

# A kubectl warning on stderr must not reach the JSON.
KWARN=1 BROKEN=0 bash "$GATES" ctx >"$tmp/warn" 2>&1 \
  || { fail "gcp-0-platform-gates.sh fails on a kubectl stderr warning"; sed 's/^/      /' "$tmp/warn" >&2; }
# A failed ACME query is a FAIL, never "no 429".
for r in events orders.acme.cert-manager.io; do
  KFAIL=$r BROKEN=0 bash "$GATES" ctx >"$tmp/kfail" 2>&1 && fail "gcp-0-platform-gates.sh exits 0 when get $r fails"
  grep -q "^FAIL .*unreadable: stub: $r forbidden" "$tmp/kfail" || fail "gcp-0-platform-gates.sh prints no FAIL for a failed get $r"
  grep -q "^PASS  no Let's Encrypt 429" "$tmp/kfail" && fail "gcp-0-platform-gates.sh passes the 429 check when get $r fails"
done

# Headroom off (replicas 0, the default) is not a failure: no headroom pod, no gVisor node required.
HEADROOM=0 BROKEN=0 bash "$V21" ctx >"$tmp/off" 2>&1 \
  || { fail "gcp-0-v21-checks.sh fails with the headroom off"; sed 's/^/      /' "$tmp/off" >&2; }
grep -q '^INFO  agents-headroom is off' "$tmp/off" || fail "gcp-0-v21-checks.sh does not report the headroom off"
grep -q '0 required' "$tmp/off" || fail "gcp-0-v21-checks.sh requires a gVisor node with the headroom off"

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
