#!/usr/bin/env python3
# requires: python3 kustomize
"""The workflow comparison is opt-in; no shipped cloud carries its evaluation overlay."""
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
assert "evaluation" not in factory("tooling/aws-0/agent-factory/resources")
print("ok    no cloud carries the workflow evaluation overlay")
sys.exit(0)
