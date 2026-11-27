#!/usr/bin/env python3
# requires: python3 kustomize
"""OpenCode is the default harness, and no harness trial runs.

The owner's decision of 2026-11-27 (docs/runbooks/agent-factory/results-harness-paired-trial-2026-11-26.md,
"Decision") overrides the adopt design's 30-per-arm gate: base's Factory sets `defaults.harness: opencode`
and no cluster overrides it. The 50/50 trial ended with it: no Factory carries `evaluation.treatmentHarness`
or `evaluation.treatment`. The OpenCode image, now on every unlabelled run, carries a `@sha256:` digest.
"""
import copy
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIGEST_TAG = re.compile(r"^[^@\s]+@sha256:[a-f0-9]{64}$")
DEFAULT = "opencode"


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def factories(objects):
    return [o for o in objects if o.get("kind") == "Factory"]


def broker_releases(objects):
    return [o for o in objects if o.get("kind") == "HelmRelease" and o.get("metadata", {}).get("name") == "room-broker"]


def problems(clusters, broker_objs):
    """clusters maps a label ("base", "gcp-0", "aws-0") to its rendered objects."""
    errs = []
    for label, objs in clusters.items():
        fs = factories(objs)
        if not fs:
            errs.append(f"{label} renders no Factory")
        for f in fs:
            spec = f.get("spec") or {}
            got = (spec.get("defaults") or {}).get("harness")
            if got != DEFAULT:
                errs.append(f"{label} Factory defaults.harness={got!r}, want {DEFAULT!r} (owner decision 2026-11-27)")
            ev = spec.get("evaluation") or {}
            for key in ("treatmentHarness", "treatment"):
                if key in ev:
                    errs.append(f"{label} Factory sets evaluation.{key}={ev[key]!r}: the harness trial ended with the cutover")

    for hr in broker_releases(broker_objs):
        images = (((hr.get("spec") or {}).get("values") or {}).get("runController") or {}).get("images") or {}
        oc = images.get("opencode")
        if oc is None:
            errs.append("room-broker runController.images.opencode is unset: the default harness has no image")
            continue
        tag = str(oc.get("tag") or "")
        if not DIGEST_TAG.match(tag):
            errs.append(f"room-broker runController.images.opencode.tag {tag!r} must be <version>@sha256:<64 hex>")
        repo = str(oc.get("repository") or "")
        if repo != "ghcr.io/smana/maku-opencode":
            errs.append(f"room-broker runController.images.opencode.repository {repo!r} != ghcr.io/smana/maku-opencode")
    return errs


clusters = {
    "base": render("tooling/base/agent-factory/resources") + render("tooling/base/agent-factory"),
    "gcp-0": render("tooling/gcp-0/agent-factory/resources") + render("tooling/gcp-0/agent-factory"),
    "aws-0": render("tooling/aws-0/agent-factory/resources") + render("tooling/aws-0/agent-factory"),
}
broker = render("infrastructure/base/room-broker")
errors = problems(clusters, broker)

# Self-tests: the guard bites on a missing default, a trial left on, and an unpinned image.
s_ok = [{"apiVersion": "maku.ogenki.io/v1alpha1", "kind": "Factory", "metadata": {"name": "f"},
         "spec": {"defaults": {"dataClass": "public", "harness": "opencode"}}}]
s_broker_ok = [{"kind": "HelmRelease", "metadata": {"name": "room-broker"},
                "spec": {"values": {"runController": {"images": {"opencode": {
                    "repository": "ghcr.io/smana/maku-opencode", "tag": "v0.58.0@sha256:" + "a" * 64}}}}}}]
ok = {"base": s_ok, "gcp-0": s_ok, "aws-0": s_ok}
assert not problems(ok, s_broker_ok), "opencode default with a pinned image should pass"

no_default = copy.deepcopy(s_ok)
del no_default[0]["spec"]["defaults"]["harness"]
assert problems({**ok, "gcp-0": no_default}, s_broker_ok), "a Factory without defaults.harness must fail"
openhands = copy.deepcopy(s_ok)
openhands[0]["spec"]["defaults"]["harness"] = "openhands"
assert problems({**ok, "aws-0": openhands}, s_broker_ok), "a cluster overriding the default must fail"
trial = copy.deepcopy(s_ok)
trial[0]["spec"]["evaluation"] = {"controlPercent": 50, "treatmentHarness": "openhands"}
assert problems({**ok, "gcp-0": trial}, s_broker_ok), "a harness trial left on must fail"
bad_tag = copy.deepcopy(s_broker_ok)
bad_tag[0]["spec"]["values"]["runController"]["images"]["opencode"]["tag"] = "v0.58.0"
assert problems(ok, bad_tag), "a tag-only opencode image must fail"
no_image = copy.deepcopy(s_broker_ok)
del no_image[0]["spec"]["values"]["runController"]["images"]["opencode"]
assert problems(ok, no_image), "a missing opencode image must fail"

for err in errors:
    print(f"FAIL: {err}")
if errors:
    sys.exit(1)
print("PASS: OpenCode is the default harness on every cluster, no harness trial runs, and its image is pinned by digest")
