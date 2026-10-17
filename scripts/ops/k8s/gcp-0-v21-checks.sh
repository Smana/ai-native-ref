#!/usr/bin/env bash
# Runbook 14 step 7: the v2.1 blockers on gcp-0, read-only (kubectl get, logs and port-forward).
#
# usage: gcp-0-v21-checks.sh <kube-context> [--gvisor-nodes N]
#
# One PASS or FAIL line per check, exit 1 on any FAIL. INFO lines are context, never a verdict.
# 7.1: the factory reaches ZITADEL across nodes. 7.2: agents-gvisor scales inside the quota.
# --gvisor-nodes is the agents-gvisor node count to require: 1 for the headroom (default), 2
# during a `large` run. Nothing here cordons, deletes or restarts anything: a co-located factory
# prints the commands for the owner to run.
set -uo pipefail
usage() { sed -n '4p' "$0" >&2; exit 2; }
[ $# -ge 1 ] && [ "${1#-}" = "$1" ] || usage
CTX=$1; shift
GVISOR_NODES=1
while [ $# -gt 0 ]; do
  case "$1" in
    --gvisor-nodes) GVISOR_NODES=${2:?}; shift ;;
    *) usage ;;
  esac
  shift
done
for t in kubectl jq curl; do command -v "$t" >/dev/null || { echo "missing: $t" >&2; exit 2; }; done

k() { kubectl --context "$CTX" "$@"; }
FAILED=0
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; FAILED=1; }
info() { echo "INFO  $*"; }
indent() { sed 's/^/        /'; }

PF_PIDS=()
stop_forwards() { local p; for p in "${PF_PIDS[@]}"; do kill "$p" 2>/dev/null; done; }
trap stop_forwards EXIT
# start_forward <namespace> <pod/… or svc/…> <remote port> <local port>: call it in the parent
# shell, never inside $(…), or the PID never reaches PF_PIDS and the forward outlives the script.
# kubectl, not k: a backgrounded function is a subshell, and killing it leaves kubectl running.
start_forward() {
  kubectl --context "$CTX" -n "$1" port-forward "$2" "$4:$3" >/dev/null 2>&1 &
  PF_PIDS+=($!)
}
# get_local <local port> <path>: one GET through a forward start_forward opened.
get_local() {
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    curl -sf -m 10 "http://127.0.0.1:$1$2" && return 0
    sleep "0.$i"
  done
  return 1
}

echo "context: $CTX  started: $(date -u +%FT%TZ)"
idp=$(k get configmap -n flux-system gke-gcp-0-vars -o jsonpath='{.data.identity_provider_url}' 2>/dev/null)
[ -n "$idp" ] || fail "identity_provider_url is unset in flux-system/gke-gcp-0-vars"

echo "== 7.1 the factory reaches the IdP across nodes"
pods=$(k get pods -n agent-system -l app.kubernetes.io/name=agent-factory -o json 2>/dev/null || echo '{"items":[]}')
zitadel_nodes=$(k get pods -n security -l app.kubernetes.io/name=zitadel --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' 2>/dev/null | sort -u)
[ -n "$zitadel_nodes" ] || fail "no Running ZITADEL pod in security"
info "ZITADEL on: $(tr '\n' ' ' <<<"$zitadel_nodes")"
[ "$(jq '.items | length' <<<"$pods")" -gt 0 ] || fail "no agent-factory pod in agent-system"
while IFS=$'\t' read -r pod node ready restarts; do
  if [ "$ready" = True ]; then pass "$pod Ready on $node (restarts: $restarts)"; else fail "$pod Ready=$ready on $node (restarts: $restarts)"; fi
  if grep -qxF "$node" <<<"$zitadel_nodes"; then
    fail "$pod shares $node with ZITADEL: a co-located fetch succeeds under any policy, so it proves nothing"
    indent <<EOF
to move it (the owner, by hand; this script changes nothing):
kubectl --context $CTX cordon $node
kubectl --context $CTX -n agent-system delete pod $pod
kubectl --context $CTX uncordon $node   # once the new pod is Ready elsewhere
EOF
  else
    pass "$pod on $node, which runs no ZITADEL pod"
  fi
  # The human verifier is eager (agent-platform internal/app/factory.go): the start line is logged
  # only after ZITADEL's JWKS was fetched, and a failed fetch exits with "initial JWKS fetch".
  logs=$(k logs -n agent-system "$pod" -c agent-factory 2>/dev/null)
  prev=$(k logs -n agent-system "$pod" -c agent-factory --previous 2>/dev/null)
  if grep -q 'agent-factory starting' <<<"$logs"; then
    pass "$pod logged its start, so the human JWKS from $idp loaded"
  else
    fail "$pod has not logged 'agent-factory starting': the human JWKS has not loaded"
  fi
  jwks_err=$(grep -h 'initial JWKS fetch' <<<"$logs"$'\n'"$prev" | tail -1)
  [ -z "$jwks_err" ] || fail "$pod JWKS fetch error: ${jwks_err:0:240}"
done < <(jq -r '.items[] | [.metadata.name, (.spec.nodeName // "unscheduled"),
    ([.status.conditions[]? | select(.type == "Ready")][0].status // "Unknown"),
    ([.status.containerStatuses[]?.restartCount] | add // 0)] | @tsv' <<<"$pods")

cnp=$(k get ciliumnetworkpolicies.cilium.io -n agent-system agent-factory -o json 2>/dev/null || echo '{}')
portless=$(jq '[.spec.egress[]? | select(.toEntities == ["all"] and .toPorts == null)] | length' <<<"$cnp")
fqdn=$(jq -r '[.spec.egress[]?.toFQDNs[]?.matchName | select(startswith("auth."))] | join(" ")' <<<"$cnp")
if [ "$portless" -ge 1 ] && [ -z "$fqdn" ]; then pass "live CNP agent-factory: a portless toEntities [all], no IdP FQDN rule"
else fail "live CNP agent-factory: $portless portless toEntities [all] rule(s), IdP FQDN rules: ${fqdn:-none}"; fi

# The broker's gauge is the issuer's last JWKS fetch; RoomAuthnJWKSStale fires at 6h.
broker=$(k get pods -n agent-system -l app.kubernetes.io/name=room-broker --field-selector=status.phase=Running \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$broker" ]; then
  fail "no Running room-broker pod"
elif start_forward agent-system "pod/$broker" 9090 19090 && metrics=$(get_local 19090 /metrics); then
  last=$(awk -v want="rooms_authn_jwks_last_refresh_timestamp_seconds{issuer=\"$idp\"}" '$1 == want {printf "%d\n", $2}' <<<"$metrics")
  if [ -z "$last" ]; then fail "room-broker $broker: no JWKS refresh gauge for $idp"
  else
    # A Go client prints the gauge in exponent form (1.7607e+09): awk made it an integer.
    age=$(( $(date +%s) - last ))
    if [ "$age" -lt 21600 ]; then pass "room-broker $broker fetched $idp's JWKS ${age}s ago"
    else fail "room-broker $broker last fetched $idp's JWKS ${age}s ago (over 6h)"; fi
  fi
else
  fail "room-broker $broker: /metrics unreachable through a port-forward"
fi

start_forward observability svc/vmalertmanager-victoria-metrics-k8s-stack 9093 19093
alerts=$(get_local 19093 '/api/v2/alerts?active=true') \
  || { fail "VMAlertmanager unreachable through a port-forward"; alerts='[]'; }
for a in RoomAuthnJWKSStale RoomAuthnHumanIssuerNeverFetched; do
  n=$(jq --arg a "$a" '[.[] | select(.labels.alertname == $a)] | length' <<<"$alerts")
  if [ "$n" = 0 ]; then pass "$a not firing"; else fail "$a firing ($n)"; fi
done
info "RoomAuthnHumanIssuerNeverFetched needs 30m to fire: re-run 30m after the broker's start"
info "the roomctl call to :8082 is the owner's, with a human token (runbook 11 step 3)"

echo "== 7.2 agents-gvisor scales inside the CPU quota"
nodes=$(k get nodes -o json 2>/dev/null || echo '{"items":[]}')
gv=$(jq '[.items[] | select(.metadata.labels["cloud.google.com/gke-nodepool"] == "agents-gvisor")
  | select(([.status.conditions[]? | select(.type == "Ready")][0].status) == "True")] | length' <<<"$nodes")
if [ "$gv" -ge "$GVISOR_NODES" ]; then pass "agents-gvisor: $gv Ready node(s), $GVISOR_NODES required"
else fail "agents-gvisor: $gv Ready node(s), $GVISOR_NODES required"; fi
stray=$(jq -r '.items[] | select(.metadata.labels["sandbox.gke.io/runtime"] == "gvisor")
  | select(.metadata.labels["cloud.google.com/gke-nodepool"] != "agents-gvisor")
  | "\(.metadata.name) (pool \(.metadata.labels["cloud.google.com/gke-nodepool"] // "?"), \(.metadata.labels["node.kubernetes.io/instance-type"] // "?"))"' <<<"$nodes")
if [ -z "$stray" ]; then pass "no gVisor node outside agents-gvisor (no nap-e2-standard-4 fallback)"
else fail "gVisor nodes outside agents-gvisor, the NAP fallback that cannot hold a large run:"; indent <<<"$stray"; fi

headroom=$(k get pods -n agent-system -l app.kubernetes.io/name=agents-headroom \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.spec.nodeName}{"\n"}{end}' 2>/dev/null)
[ -n "$headroom" ] || fail "no agents-headroom pod in agent-system"
while IFS=$'\t' read -r pod phase node; do
  [ -n "$pod" ] || continue
  pool=$(jq -r --arg n "$node" '.items[] | select(.metadata.name == $n) | .metadata.labels["cloud.google.com/gke-nodepool"] // "?"' <<<"$nodes")
  if [ "$phase" = Running ] && [ "$pool" = agents-gvisor ]; then pass "$pod Running on agents-gvisor node $node"
  else fail "$pod $phase on ${node:-no node} (pool ${pool:-none}), expected Running on agents-gvisor"; fi
done <<<"$headroom"

events=$(k get events -A -o json 2>/dev/null || echo '{"items":[]}')
up=$(jq -r '.items[] | select(.reason == "TriggeredScaleUp" and (.message | test("agents-gvisor")))
  | "\(.lastTimestamp // .eventTime // "-") \(.message[0:200])"' <<<"$events" | sort -u)
info "TriggeredScaleUp to agents-gvisor: ${up:-none in the event window}"
quota=$(jq -r '.items[] | select((.reason | test("FailedScaleUp|FailedToScaleUp|ScaleUpFailed"))
    or (.message // "" | test("quota exceeded|QUOTA_EXCEEDED"; "i")))
  | "\(.lastTimestamp // .eventTime // "-") \(.involvedObject.namespace // "-")/\(.involvedObject.name) \(.reason): \(.message[0:200])"' <<<"$events" | sort -u)
if [ -z "$quota" ]; then pass "no FailedScaleUp or quota event"; else fail "scale-up failures:"; indent <<<"$quota"; fi
info "events live about 1h: run this right after the scale-up. The durable record is GKE's"
info "cluster-autoscaler-visibility log (messageId scale.up.error.quota.exceeded) in Cloud Logging"

echo "finished: $(date -u +%FT%TZ)"
if [ "$FAILED" != 0 ]; then echo "SOME CHECKS FAILED"; exit 1; fi
echo "ALL CHECKS PASSED"
