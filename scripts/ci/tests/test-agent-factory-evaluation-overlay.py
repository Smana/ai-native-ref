#!/usr/bin/env python3
# requires: python3 kustomize
"""Comparison 1 (WF9): aws-0 carries the standard-vs-careful evaluation overlay; base and gcp-0 do not."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]


def factory(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)],
                         capture_output=True, text=True, check=True).stdout
    return next(d["spec"] for d in yaml.safe_load_all(out) if d and d["kind"] == "Factory")


assert "evaluation" not in factory("tooling/base/agent-factory/resources")
assert "evaluation" not in factory("tooling/gcp-0/agent-factory/resources")
ev = factory("tooling/aws-0/agent-factory/resources").get("evaluation")
assert ev == {
    "controlPercent": 70,
    "treatment": "careful",
}, ev
print("ok    aws-0 evaluation overlay is careful at 30% (controlPercent: 70); base and gcp-0 carry none")
sys.exit(0)
