#!/usr/bin/env python3
# requires: python3 kustomize
"""CP4: aws-0 schedules one warm gVisor node; the base and gcp-0 stay off.

The pre-pulled images are the run-controller's runController.images.harness and .bridge pins in
infrastructure/base/room-broker/helmrelease.yaml, the run path since R3.
"""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def one(objects, kind, name):
    hits = [o for o in objects if o.get("kind") == kind and o.get("metadata", {}).get("name") == name]
    assert len(hits) == 1, f"{kind}/{name}: found {len(hits)}"
    return hits[0]


def run_images():
    hr = one(render("infrastructure/base/room-broker"), "HelmRelease", "room-broker")
    images = hr["spec"]["values"]["runController"]["images"]
    return {f"{image['repository']}:{image['tag']}" for image in images.values()}


def headroom_images(objects):
    pod = one(objects, "Deployment", "agents-headroom")["spec"]["template"]["spec"]
    return {c["image"] for c in pod.get("initContainers", []) + pod["containers"]}


aws = render("infrastructure/aws-0/karpenter-nodepools-agents/headroom")
base = render("infrastructure/base/karpenter-nodepools-agents/headroom")

so = one(aws, "ScaledObject", "agents-headroom")
assert so["metadata"]["namespace"] == "agent-system"
assert so["spec"]["scaleTargetRef"] == {"name": "agents-headroom"}
assert (so["spec"]["minReplicaCount"], so["spec"]["maxReplicaCount"]) == (0, 1)
assert so["spec"]["triggers"] == [{"type": "cron", "metadata": {
    "timezone": "Europe/Paris", "start": "0 8 * * 1-5", "end": "0 19 * * 1-5", "desiredReplicas": "1"}}]
assert "replicas" not in one(aws, "Deployment", "agents-headroom")["spec"], "Flux must not own the scheduled replicas"

assert one(base, "Deployment", "agents-headroom")["spec"]["replicas"] == 0
assert not any(o["kind"] == "ScaledObject" for o in base), "the base must not warm gcp-0 by inheritance"
assert headroom_images(aws) == run_images(), f"headroom images {headroom_images(aws)} != run images {run_images()}"
print("PASS: aws-0 owns the weekday schedule; base stays off; headroom pre-pulls the run images")
