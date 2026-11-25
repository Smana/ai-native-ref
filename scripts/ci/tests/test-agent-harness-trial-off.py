#!/usr/bin/env python3
# requires: python3 kustomize
"""OpenCode adopt plan Tasks 1 & 4 guard: OpenHands stays the default everywhere, no unpinned OpenCode image,
and the one harness trial is strictly single-variable and runs on one cluster.

No Factory anywhere sets `defaults.harness`. Base and every cluster but TRIAL_CLUSTER carry neither
`evaluation.treatmentHarness` nor `evaluation.treatment`. TRIAL_CLUSTER (gcp-0, the owner's decision of
2026-11-25: aws-0 is torn down) may carry exactly `{controlPercent: 50, treatmentHarness: opencode}` and no
workflow treatment. Any `runController.images.opencode.tag` carries a `@sha256:` digest.
"""
import copy
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIGEST_TAG = re.compile(r"^[^@\s]+@sha256:[a-f0-9]{64}$")
TRIAL_CLUSTER = "gcp-0"
TRIAL = {"controlPercent": 50, "treatmentHarness": "opencode"}


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def factories(objects):
    return [o for o in objects if o.get("kind") == "Factory"]


def repositories(objects):
    return [o for o in objects if o.get("kind") == "Repository"]


def broker_releases(objects):
    return [o for o in objects if o.get("kind") == "HelmRelease" and o.get("metadata", {}).get("name") == "room-broker"]


def problems(clusters, broker_objs, *, trial_cluster=None):
    """clusters maps a label ("base", "gcp-0", "aws-0") to its rendered objects."""
    errs = []
    for label, objs in clusters.items():
        for f in factories(objs):
            spec = f.get("spec") or {}
            if "harness" in (spec.get("defaults") or {}):
                errs.append(f"{label} Factory sets defaults.harness={spec['defaults']['harness']!r}")
            ev = spec.get("evaluation") or {}
            if "treatment" in ev:
                errs.append(f"{label} Factory sets evaluation.treatment={ev['treatment']!r}: no workflow trial beside the harness")
            if "treatmentHarness" not in ev:
                continue
            if label != trial_cluster:
                errs.append(f"{label} Factory sets evaluation.treatmentHarness={ev['treatmentHarness']!r}: only {trial_cluster} runs the trial")
            elif ev != TRIAL:
                errs.append(f"{label} harness trial must be {TRIAL!r} and nothing else, got {ev!r}")

    if trial_cluster in clusters:
        base_repos = {r["metadata"]["name"]: r for r in repositories(clusters.get("base", []))}
        for r in repositories(clusters[trial_cluster]):
            name = r["metadata"]["name"]
            spec = r.get("spec") or {}
            if name in base_repos and spec != (base_repos[name].get("spec") or {}):
                errs.append(f"{trial_cluster} trial repository {name}: differs from base, so the arms would not be the platform's")

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


clusters = {
    "base": render("tooling/base/agent-factory/resources") + render("tooling/base/agent-factory"),
    "gcp-0": render("tooling/gcp-0/agent-factory/resources") + render("tooling/gcp-0/agent-factory"),
    "aws-0": render("tooling/aws-0/agent-factory/resources") + render("tooling/aws-0/agent-factory"),
}
broker = render("infrastructure/base/room-broker")

errors = problems(clusters, broker, trial_cluster=TRIAL_CLUSTER)
gcp_ev = (factories(clusters[TRIAL_CLUSTER])[0].get("spec") or {}).get("evaluation")
if gcp_ev != TRIAL:
    errors.append(f"{TRIAL_CLUSTER} runs the harness trial {TRIAL!r} (owner decision 2026-11-25), got {gcp_ev!r}")

# Self-tests: prove the guard bites on accidental default, unpinned digest, a misplaced or confounded trial.
s_base = [{"apiVersion": "maku.ogenki.io/v1alpha1", "kind": "Factory", "metadata": {"name": "f"}, "spec": {"defaults": {"dataClass": "public"}}}]
s_broker_ok = [{
    "kind": "HelmRelease",
    "metadata": {"name": "room-broker"},
    "spec": {"values": {"runController": {"images": {"opencode": {
        "repository": "ghcr.io/smana/maku-opencode",
        "tag": "v0.54.1@sha256:" + "a" * 64,
    }}}}},
}]
off = {"base": s_base, "gcp-0": s_base, "aws-0": s_base}
assert not problems(off, s_broker_ok, trial_cluster="gcp-0"), "valid digest-pinned opt-in should pass"

bad_default = copy.deepcopy(s_base)
bad_default[0]["spec"]["defaults"]["harness"] = "opencode"
assert problems({**off, "base": bad_default}, s_broker_ok, trial_cluster="gcp-0"), "defaults.harness in base must fail"
assert problems({**off, "gcp-0": bad_default}, s_broker_ok, trial_cluster="gcp-0"), "defaults.harness on the trial cluster must fail"

bad_tag = copy.deepcopy(s_broker_ok)
bad_tag[0]["spec"]["values"]["runController"]["images"]["opencode"]["tag"] = "v0.54.1"
assert problems(off, bad_tag, trial_cluster="gcp-0"), "tag-only opencode image pin must fail"

valid_trial = copy.deepcopy(s_base)
valid_trial[0]["spec"]["evaluation"] = dict(TRIAL)
assert not problems({**off, "gcp-0": valid_trial}, s_broker_ok, trial_cluster="gcp-0"), "single-variable gcp-0 trial should pass"
assert problems({**off, "aws-0": valid_trial}, s_broker_ok, trial_cluster="gcp-0"), "trial on aws-0 must fail"
assert problems({**off, "base": valid_trial}, s_broker_ok, trial_cluster="gcp-0"), "trial in base must fail"

confounded = copy.deepcopy(valid_trial)
confounded[0]["spec"]["evaluation"]["treatment"] = "careful"
assert problems({**off, "gcp-0": confounded}, s_broker_ok, trial_cluster="gcp-0"), "confounded workflow+harness trial must fail"

skewed = copy.deepcopy(valid_trial)
skewed[0]["spec"]["evaluation"]["controlPercent"] = 80
assert problems({**off, "gcp-0": skewed}, s_broker_ok, trial_cluster="gcp-0"), "a trial other than 50/50 must fail"

for err in errors:
    print(f"FAIL: {err}")
if errors:
    sys.exit(1)
print("PASS: OpenHands stays default everywhere, the 50/50 harness trial runs on gcp-0 alone, single-variable and digest guards hold")
