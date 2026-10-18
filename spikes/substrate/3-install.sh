#!/usr/bin/env bash
# The upstream installer: CRDs, cluster RBAC, SandboxConfig, ValidatingAdmissionPolicies,
# podcertificate-controller-system, and the ate-system control plane with its generated CA and JWT
# Secrets. It is why this directory is not a plain kustomization.
source "$(dirname "$0")/env.sh"
cfg=$(mktemp)
sed "s#REGISTRY#$REG#" "$HERE/substrate-install.yaml" > "$cfg"
cd "$SUBSTRATE"
ATE_CONFIG=$cfg systemd-run --user --scope -q -p MemoryMax=2G -E KUBECONFIG -E ATE_CONFIG \
  "$ATE_SETUP" deploy ate-system
