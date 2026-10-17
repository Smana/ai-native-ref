#!/usr/bin/env bash
# Builds every image from the tag and pushes it to $REG (upstream publishes none, #2730).
# Memory-capped: the ko builds in a 3G scope, envoy-dataplane in a 3G buildx container, because a
# docker build runs in dockerd, outside any systemd-run scope.
source "$(dirname "$0")/env.sh"
cd "$SUBSTRATE"
KO_DEFAULTPLATFORMS=linux/amd64 VERSION=v0.5.0 GOFLAGS="-mod=vendor -p=1" GOMAXPROCS=1 \
  systemd-run --user --scope -q -p MemoryMax=3G -E KO_DEFAULTPLATFORMS -E VERSION -E GOFLAGS -E GOMAXPROCS \
  "$ATE_SETUP" publish release-images --ko-docker-repo "$REG" || true   # envoy-dataplane fails here: DNS in dockerd's bridge
grep -q CARGO_BUILD_JOBS cmd/dataplane/envoy/Dockerfile ||
  sed -i 's#^WORKDIR /usr/src/dynamic-modules/egress-policy#&\nENV CARGO_BUILD_JOBS=1#' cmd/dataplane/envoy/Dockerfile
docker buildx create --name substrate-spike --driver docker-container --driver-opt memory=3g,memory-swap=3g,network=host
docker buildx build --builder substrate-spike --platform linux/amd64 --network host \
  -t "$REG/envoy-dataplane:v0.5.0" --push cmd/dataplane/envoy
docker buildx rm substrate-spike
