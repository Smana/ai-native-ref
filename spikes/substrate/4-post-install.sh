#!/usr/bin/env bash
# GKE Sandbox toleration and the S3 backend, then the worker pool, the atespace and the templates.
source "$(dirname "$0")/env.sh"
kubectl -n ate-system patch daemonset atelet --patch-file "$HERE/patches/atelet.yaml"
kubectl -n ate-system patch deployment ate-api-server --patch-file "$HERE/patches/ate-api-server.yaml"
kubectl -n ate-system rollout status daemonset/atelet --timeout=5m
kubectl -n ate-system rollout status deployment/ate-api-server --timeout=5m
node_a=$(kubectl get nodes -l cloud.google.com/gke-nodepool=substrate-gvisor -o jsonpath='{.items[0].metadata.name}')
worker="$REG/ateom-gvisor@$(regctl manifest digest "$REG/ateom-gvisor:v0.5.0")"
sed -e "s#WORKER_IMAGE#$worker#" -e "s#NODE_OP#In#" -e "s#NODE_A#$node_a#" "$HERE/workerpools.yaml" | kubectl apply -f -
"$KUBECTL_ATE" create atespace substrate-spike
for t in cold:DISABLED warm:ENABLED; do
  sed -e "s#TEMPLATE_NAME#openhands-${t%%:*}#g" -e "s#GOLDEN_MODE#GOLDEN_SNAPSHOT_MODE_${t#*:}#" "$HERE/actor/template.yaml" |
    "$KUBECTL_ATE" create actor-template -f -
done
