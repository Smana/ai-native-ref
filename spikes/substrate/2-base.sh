#!/usr/bin/env bash
# Namespaces, network policy and the rustfs snapshot store. The bucket credentials never touch git.
source "$(dirname "$0")/env.sh"
kubectl apply -f "$HERE/namespace.yaml"
kubectl -n ate-system get secret rustfs-credentials >/dev/null 2>&1 ||
  kubectl -n ate-system create secret generic rustfs-credentials \
    --from-literal=AWS_ACCESS_KEY_ID=spike --from-literal=AWS_SECRET_ACCESS_KEY="$(openssl rand -hex 24)"
kubectl apply -k "$HERE"
kubectl -n ate-system wait --for=condition=complete job/rustfs-bucket-init --timeout=5m
