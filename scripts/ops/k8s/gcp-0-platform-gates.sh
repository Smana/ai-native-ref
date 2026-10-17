#!/usr/bin/env bash
# Runbook 14 step 4: gcp-0's platform gates, read-only (kubectl get and logs, plus HTTPS GETs).
#
# usage: gcp-0-platform-gates.sh <kube-context> [--zitadel-seed NAME|none] [--bao-addr URL]
#
# One PASS or FAIL line per check, exit 1 on any FAIL. INFO lines are context, never a verdict.
# --zitadel-seed is the objectStoreRecovery path ZITADEL's database must have restored (option A's
# zitadel-20260828 by default); `none` expects a fresh initdb (option C). OpenBao is a VM outside
# GKE, reached over the tailnet: --bao-addr defaults to $VAULT_ADDR, then bao.priv.gcp.ogenki.io,
# and $VAULT_CACERT is honoured.
set -uo pipefail
usage() { sed -n '4p' "$0" >&2; exit 2; }
[ $# -ge 1 ] && [ "${1#-}" = "$1" ] || usage
CTX=$1; shift
SEED=zitadel-20260828
BAO_ADDR=${VAULT_ADDR:-https://bao.priv.gcp.ogenki.io:8200}
while [ $# -gt 0 ]; do
  case "$1" in
    --zitadel-seed) SEED=${2:?}; shift ;;
    --bao-addr) BAO_ADDR=${2:?}; shift ;;
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

# gate <label> <kubectl get args...>: PASS when the list is non-empty and every unsuspended item's
# Ready condition is True. Suspended items are listed as INFO.
gate() {
  local label=$1 json bad n susp; shift
  json=$(k get "$@" -o json 2>&1) || { fail "$label: $json"; return; }
  n=$(jq '.items | length' <<<"$json")
  [ "$n" -gt 0 ] || { fail "$label: none found"; return; }
  susp=$(jq -r '[.items[] | select(.spec.suspend == true) | "\(.metadata.namespace)/\(.metadata.name)"] | join(" ")' <<<"$json")
  [ -z "$susp" ] || info "$label suspended: $susp"
  bad=$(jq -r '.items[] | select(.spec.suspend != true)
    | ([.status.conditions[]? | select(.type == "Ready")][0]) as $r
    | select(($r.status // "Unknown") != "True")
    | "\(.metadata.namespace // "-")/\(.metadata.name): \(($r.message // "no Ready condition")[0:160])"' <<<"$json")
  if [ -z "$bad" ]; then pass "$label: $n, every unsuspended one Ready"; else fail "$label not Ready:"; indent <<<"$bad"; fi
}

echo "context: $CTX  started: $(date -u +%FT%TZ)"

echo "== Flux"
gate "Kustomizations" kustomizations.kustomize.toolkit.fluxcd.io -A
gate "HelmReleases" helmreleases.helm.toolkit.fluxcd.io -A

echo "== Certificates (ZITADEL's in security, the Gateways' in infrastructure)"
for ns in security infrastructure; do
  gate "Certificates in $ns" certificates.cert-manager.io -n "$ns"
  # Let's Encrypt allows five certificates per identifier set per week; its 429 surfaces here,
  # and later as "ZITADEL not ready".
  hits=$( { k get events -n "$ns" -o json | jq -r '.items[]
              | select(.message // "" | test("rateLimited|too many certificates|\\b429\\b"; "i"))
              | "\(.involvedObject.kind)/\(.involvedObject.name): \(.message[0:200])"'
            k get orders.acme.cert-manager.io -n "$ns" -o json | jq -r '.items[]
              | select(.status.state == "errored" or .status.state == "invalid")
              | "Order/\(.metadata.name) \(.status.state): \((.status.reason // "")[0:200])"'
          } 2>/dev/null | sort -u)
  if [ -z "$hits" ]; then pass "no Let's Encrypt 429 or failed Order in $ns"; else fail "ACME trouble in $ns:"; indent <<<"$hits"; fi
done

echo "== External Secrets"
gate "ClusterSecretStores (OpenBao and Secret Manager, seen from the cluster)" clustersecretstores.external-secrets.io
gate "ExternalSecrets" externalsecrets.external-secrets.io -A

echo "== CNPG"
if json=$(k get clusters.postgresql.cnpg.io -A -o json 2>&1); then
  [ "$(jq '.items | length' <<<"$json")" -gt 0 ] || fail "CNPG: no Cluster found"
  zitadel_boot=""
  while IFS=$'\t' read -r name ready arch boot; do
    if [ "$ready" = True ]; then pass "CNPG $name Ready, bootstrap $boot"; else fail "CNPG $name Ready=$ready, bootstrap $boot"; fi
    case "$arch" in
      -) ;;
      True) pass "CNPG $name continuous archiving" ;;
      *) fail "CNPG $name ContinuousArchiving=$arch" ;;
    esac
    case "$name" in security/xplane-zitadel*) zitadel_boot=$boot ;; esac
  done < <(jq -r '.items[]
      | ([.status.conditions[]? | select(.type == "Ready")][0].status // "Unknown") as $ready
      | ([.status.conditions[]? | select(.type == "ContinuousArchiving")][0].status // "-") as $arch
      | (if .spec.bootstrap.recovery then
           (.spec.bootstrap.recovery.source) as $s
           | "recovery:" + ([.spec.externalClusters[]? | select(.name == $s)
               | .plugin.parameters.serverName // .barmanObjectStore.serverName][0] // $s)
         elif .spec.bootstrap.pg_basebackup then "pg_basebackup"
         else "initdb" end) as $boot
      | [.metadata.namespace + "/" + .metadata.name, $ready, $arch, $boot] | @tsv' <<<"$json")
  want=$([ "$SEED" = none ] && echo initdb || echo "recovery:$SEED")
  if [ "$zitadel_boot" = "$want" ]; then pass "ZITADEL's database bootstrapped from $want"
  else fail "ZITADEL's database bootstrap is '${zitadel_boot:-absent}', expected $want"; fi
else
  fail "CNPG: $json"
fi

echo "== ZITADEL"
vars=$(k get configmap -n flux-system gke-gcp-0-vars -o json 2>/dev/null || echo '{}')
domain=$(jq -r '.data.public_domain_name // empty' <<<"$vars")
idp=$(jq -r '.data.identity_provider_url // empty' <<<"$vars")
if [ -n "$domain" ] && [ "$idp" = "https://auth.$domain" ]; then pass "the cluster consumes its own IdP: $idp"
else fail "identity_provider_url '${idp:-unset}' is not https://auth.${domain:-<public_domain_name unset>} (gke-gcp-0-vars)"; fi
ready=$(k get deploy -n security zitadel -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
if [ "${ready:-0}" -ge 1 ]; then pass "ZITADEL: $ready ready replica(s)"; else fail "ZITADEL: no ready replica"; fi
if [ -n "$domain" ]; then
  url="https://auth.$domain/.well-known/openid-configuration"
  out=$(curl -sS -m 15 -w '\n%{http_code}' "$url" 2>&1)
  code=${out##*$'\n'}
  issuer=$(jq -r '.issuer // empty' 2>/dev/null <<<"${out%$'\n'*}")
  if [ "$code" = 200 ] && [ "$issuer" = "https://auth.$domain" ]; then pass "discovery $url: 200, issuer $issuer"
  else fail "discovery $url: HTTP $code, issuer '${issuer:-none}'"; fi
fi

echo "== OpenBao ($BAO_ADDR, over the tailnet)"
# A hang is OpenBao 2.6's core deadlock, never the VPN (host security/AGENTS.md).
if command -v bao >/dev/null; then
  status=$(VAULT_ADDR=$BAO_ADDR timeout 20 bao status -format=json 2>&1); rc=$?
else
  status=$(timeout 20 curl -sS ${VAULT_CACERT:+--cacert "$VAULT_CACERT"} "$BAO_ADDR/v1/sys/seal-status" 2>&1); rc=$?
fi
sealed=$(jq -r '.sealed' 2>/dev/null <<<"$status")
init=$(jq -r '.initialized' 2>/dev/null <<<"$status")
if [ "$rc" = 124 ]; then fail "OpenBao status hung for 20s: a core deadlock, not the VPN"
elif [ "$sealed" = false ] && [ "$init" = true ]; then pass "OpenBao initialized, sealed=false ($(jq -r '.type // "?"' <<<"$status") seal)"
else fail "OpenBao initialized=${init:-?} sealed=${sealed:-?}: $(head -c 200 <<<"$status")"; fi
snap=$(k get cronjob -n security -o json 2>/dev/null | jq -r '.items[] | select(.metadata.name | test("openbao-snapshot"))
  | "\(.metadata.name) lastSuccessfulTime=\(.status.lastSuccessfulTime // "never")"')
info "snapshot CronJob (fires 04:00 UTC; F1's live re-run): ${snap:-none found}"

echo "== Nodes by pool"
nodes=$(k get nodes -o json 2>&1) || { fail "nodes: $nodes"; nodes='{"items":[]}'; }
jq -r '.items[] | [(.metadata.labels["cloud.google.com/gke-nodepool"] // "?"),
    (.metadata.labels["node.kubernetes.io/instance-type"] // "?"),
    (.metadata.labels["sandbox.gke.io/runtime"] // "runc")] | @tsv' <<<"$nodes" \
  | sort | uniq -c | while read -r n pool type rt; do info "$pool  $type  $rt  x$n"; done
notready=$(jq -r '.items[] | select(([.status.conditions[]? | select(.type == "Ready")][0].status) != "True") | .metadata.name' <<<"$nodes")
if [ -z "$notready" ]; then pass "every node Ready"; else fail "nodes not Ready:"; indent <<<"$notready"; fi
cordoned=$(jq -r '[.items[] | select(.spec.unschedulable == true) | .metadata.name] | join(" ")' <<<"$nodes")
[ -z "$cordoned" ] || info "cordoned: $cordoned"
static=$(jq '[.items[] | select(.metadata.labels["cloud.google.com/gke-nodepool"] == "static")] | length' <<<"$nodes")
if [ "$static" -ge 2 ]; then pass "static pool: $static nodes"; else fail "static pool: $static nodes, expected 2"; fi

echo "finished: $(date -u +%FT%TZ)"
if [ "$FAILED" != 0 ]; then echo "SOME CHECKS FAILED"; exit 1; fi
echo "ALL CHECKS PASSED"
