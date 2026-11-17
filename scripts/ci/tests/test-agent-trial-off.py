#!/usr/bin/env python3
# requires: python3 kustomize
"""CP13: base carries no trial; aws-0 carries at most one single-field trial per workflow."""
import copy
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def factories(objects):
    return [o for o in objects if o.get("kind") == "Factory"]


def workflows(objects):
    out = {}
    for factory in factories(objects):
        spec = factory.get("spec", {})
        out.update(spec.get("workflows") or spec.get("harnessProfiles") or {})
    return out


def treatments(objects):
    out = []
    for factory in factories(objects):
        value = factory.get("spec", {}).get("evaluation", {}).get("treatment")
        if value:
            out.append(value)
    for cm in (o for o in objects if o.get("kind") == "ConfigMap"):
        raw = cm.get("data", {}).get("values.yaml")
        if raw:
            value = (yaml.safe_load(raw).get("maku-factory", {}).get("config", {}).get("evaluation", {}) or {}).get("treatment")
            if value:
                out.append(value)
    return out


def diff_fields(shipped, trial):
    return [key for key in set(shipped) | set(trial) if shipped.get(key) != trial.get(key)]


def problems(base, aws):
    problems = []
    base_workflows, aws_workflows = workflows(base), workflows(aws)
    for name in base_workflows:
        if name.endswith("-trial"):
            problems.append(f"base workflow {name} is a trial")
    if treatments(base):
        problems.append(f"base carries evaluation.treatment {treatments(base)}")
    trials = [name for name in aws_workflows if name.endswith("-trial")]
    seen = set()
    for name in trials:
        shipped_name = name.removesuffix("-trial")
        if shipped_name in seen:
            problems.append(f"more than one trial for workflow {shipped_name}")
        seen.add(shipped_name)
        if shipped_name not in aws_workflows:
            problems.append(f"{name} has no shipped workflow {shipped_name}")
            continue
        fields = diff_fields(aws_workflows[shipped_name], aws_workflows[name])
        if len(fields) != 1:
            problems.append(f"{name} differs from {shipped_name} in {fields}, want exactly one field")
    active = treatments(aws)
    if len(active) > 1:
        problems.append(f"aws-0 carries more than one evaluation.treatment: {active}")
    for name in active:
        if name not in trials and name not in ("careful", "quick"):
            problems.append(f"evaluation.treatment {name} names no trial workflow")
    return problems


base_resources = render("tooling/base/agent-factory/resources")
aws_resources = render("tooling/aws-0/agent-factory/resources")
base = base_resources + render("tooling/base/agent-factory")
aws = aws_resources + render("tooling/aws-0/agent-factory")
errors = problems(base, aws)

# The guard bites: a valid one-field trial is admitted; leaving it in base or changing two fields is not.
control = [{"apiVersion": "maku.ogenki.io/v1alpha1", "kind": "Factory",
            "metadata": {"name": "test"}, "spec": {"workflows": {"standard": {"template": "pair"}}}}]
trial = copy.deepcopy(control)
trial[0]["spec"]["workflows"]["standard-trial"] = {"template": "pair", "effort": {"reviewer": "medium"}}
trial[0]["spec"]["evaluation"] = {"treatment": "standard-trial"}
assert not problems(control, trial), problems(control, trial)
assert problems(trial, trial), "a trial in base was not refused"
two_fields = copy.deepcopy(trial)
two_fields[0]["spec"]["workflows"]["standard-trial"]["models"] = {"reviewer": "tier-standard"}
assert problems(control, two_fields), "a two-field trial was not refused"

for problem in errors:
    print(f"FAIL: {problem}")
if errors:
    sys.exit(1)
print("PASS: base has no trial; any aws-0 trial is single-field and selected by its treatment")
