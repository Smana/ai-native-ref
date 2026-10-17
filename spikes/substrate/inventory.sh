#!/usr/bin/env bash
# Lists every cluster-scoped object as kind/<none>/name, sorted. Everything namespaced the spike
# creates lives in ate-system, podcertificate-controller-system or substrate-spike and goes with
# them, so the cluster-scoped diff against inventory-before.txt is the rest of the cleanup list.
# Kinds the cluster derives on its own (identities, IPs, nodes, PVs) are left out as noise.
set -euo pipefail
kubectl api-resources --verbs=list --namespaced=false -o name |
  grep -vE '^(ciliumidentities|ipaddresses|csinodes|certificatesigningrequests|volumeattachments|nodes|persistentvolumes|componentstatuses)' |
  while read -r r; do
    kubectl get "$r" --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | awk -v r="$r" '{print r "/<none>/" $1}'
  done | sort
