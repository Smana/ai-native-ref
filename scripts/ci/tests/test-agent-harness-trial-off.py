#!/usr/bin/env python3
# requires: python3 kustomize
"""OpenCode adopt plan Tasks 1 & 4 guard: OpenHands stays default in base/gcp-0, no unpinned OpenCode image,
and any future aws-0 harness trial is strictly single-variable.

Until Maku H (opt-in OpenCode) is pinned, base, gcp-0, and aws-0 must carry neither `defaults.harness` nor
`evaluation.treatmentHarness`, and any `runController.images.opencode.tag` must carry a `@sha256:` digest.
"""
import copy
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIGEST_TAG = re.compile(r"^[^@\s]+@sha256:[a-f0-9]{64}$")


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def factories(objects):
    return [o for o in objects if o.get("kind") == "Factory"]


def repositories(objects):
    return [o for o in objects if o.get("kind") == "Repository"]


def broker_releases(objects):
    return [o for o in objects if o.get("kind") == "HelmRelease" and o.get("metadata", {}).get("name") == "room-broker"]


def problems(base, gcp, aws, broker_objs, *, allow_aws_trial=False):
    errs = []
    for label, objs in (("base", base), ("gcp-0", gcp)):
        for f in factories(objs):
            spec = f.get("spec") or {}
            if "harness" in (spec.get("defaults") or {}):
                errs.append(f"{label} Factory sets defaults.harness={spec['defaults']['harness']!r}")
            ev = spec.get("evaluation") or {}
            if "treatmentHarness" in ev:
                errs.append(f"{label} Factory sets evaluation.treatmentHarness={ev['treatmentHarness']!r}")
            if "treatment" in ev:
                errs.append(f"{label} Factory sets evaluation.treatment={ev['treatment']!r}")

    for f in factories(aws):
        spec = f.get("spec") or {}
        if "harness" in (spec.get("defaults") or {}):
            errs.append(f"aws-0 Factory sets defaults.harness={spec['defaults']['harness']!r}")
        ev = spec.get("evaluation") or {}
        if not allow_aws_trial:
            if "treatmentHarness" in ev:
                errs.append(f"aws-0 Factory enables evaluation.treatmentHarness before trial authorization: {ev!r}")
        elif "treatmentHarness" in ev:
            if "treatment" in ev:
                errs.append("aws-0 harness trial cannot run simultaneously with a workflow treatment")
            if ev.get("controlPercent") != 50 or ev.get("treatmentHarness") != "opencode":
                errs.append(f"aws-0 harness trial must be {{controlPercent: 50, treatmentHarness: opencode}}, got {ev!r}")

    if allow_aws_trial:
        base_repos = {r["metadata"]["name"]: r for r in repositories(base)}
        for r in repositories(aws):
            name = r["metadata"]["name"]
            spec = r.get("spec") or {}
            if spec.get("workflow", {}).get("default") != "careful":
                continue
            if spec.get("workflow", {}).get("testFirst") is not True:
                errs.append(f"aws-0 trial repository {name}: workflow.testFirst must be true")
            if not (spec.get("merge") or {}).get("contractCheck"):
                errs.append(f"aws-0 trial repository {name}: merge.contractCheck must be set")
            if name in base_repos:
                base_spec = base_repos[name].get("spec") or {}
                if spec.get("models") != base_spec.get("models") or spec.get("effort") != base_spec.get("effort"):
                    errs.append(f"aws-0 trial repository {name}: models/effort must match shipped base repository")

    for hr in broker_releases(broker_objs):
        images = (((hr.get("spec") or {}).get("values") or {}).get("runController") or {}).get("images") or {}
        oc = images.get("opencode")
        if oc is not None:
            tag = str(oc.get("tag") or "")
            if not DIGEST_TAG.match(tag):
                errs.append(f"room-broker runController.images.opencode.tag {tag!r} must be <version>@sha256:<64 hex>")
            repo = str(oc.get("repository") or "")
            if repo != "ghcr.io/smana/maku-opencode":
                errs.append(f"room-broker runController.images.opencode.repository {repo!r} != ghcr.io/smana/maku-opencode")

    return errs


base = render("tooling/base/agent-factory/resources") + render("tooling/base/agent-factory")
gcp = render("tooling/gcp-0/agent-factory/resources") + render("tooling/gcp-0/agent-factory")
aws = render("tooling/aws-0/agent-factory/resources") + render("tooling/aws-0/agent-factory")
broker = render("infrastructure/base/room-broker")

errors = problems(base, gcp, aws, broker, allow_aws_trial=False)

# Self-tests: prove the guard bites on accidental default, unpinned digest, or confounded trial.
s_base = [{"apiVersion": "maku.ogenki.io/v1alpha1", "kind": "Factory", "metadata": {"name": "f"}, "spec": {"defaults": {"dataClass": "public"}}}]
s_broker_ok = [{
    "kind": "HelmRelease",
    "metadata": {"name": "room-broker"},
    "spec": {"values": {"runController": {"images": {"opencode": {
        "repository": "ghcr.io/smana/maku-opencode",
        "tag": "v0.54.0@sha256:" + "a" * 64,
    }}}}},
}]
assert not problems(s_base, s_base, s_base, s_broker_ok), "valid digest-pinned opt-in should pass"

bad_default = copy.deepcopy(s_base)
bad_default[0]["spec"]["defaults"]["harness"] = "opencode"
assert problems(bad_default, s_base, s_base, s_broker_ok), "defaults.harness in base must fail"

bad_tag = copy.deepcopy(s_broker_ok)
bad_tag[0]["spec"]["values"]["runController"]["images"]["opencode"]["tag"] = "v0.54.0"
assert problems(s_base, s_base, s_base, bad_tag), "tag-only opencode image pin must fail"

valid_trial = copy.deepcopy(s_base)
valid_trial[0]["spec"]["evaluation"] = {"controlPercent": 50, "treatmentHarness": "opencode"}
assert not problems(s_base, s_base, valid_trial, s_broker_ok, allow_aws_trial=True), "single-variable aws-0 trial should pass when enabled"
assert problems(s_base, valid_trial, valid_trial, s_broker_ok, allow_aws_trial=True), "trial in gcp-0 must fail"

confounded = copy.deepcopy(valid_trial)
confounded[0]["spec"]["evaluation"]["treatment"] = "careful-trial"
assert problems(s_base, s_base, confounded, s_broker_ok, allow_aws_trial=True), "confounded workflow+harness trial must fail"

for err in errors:
    print(f"FAIL: {err}")
if errors:
    sys.exit(1)
print("PASS: harness trial is off everywhere, OpenHands stays default, and single-variable/digest guards hold")
