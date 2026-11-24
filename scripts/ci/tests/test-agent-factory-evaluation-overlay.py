#!/usr/bin/env python3
# requires: python3 kustomize
"""The workflow comparison is opt-in; no shipped cloud carries its evaluation overlay."""
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
REPO_ROOT = ROOT.parent if ROOT.name == ".composite" else ROOT
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


def factory(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)],
                         capture_output=True, text=True, check=True).stdout
    return next(d["spec"] for d in yaml.safe_load_all(out) if d and d["kind"] == "Factory")


no_overlay = all(
    "evaluation" not in factory(p)
    for p in (
        "tooling/base/agent-factory/resources",
        "tooling/gcp-0/agent-factory/resources",
        "tooling/aws-0/agent-factory/resources",
    )
)
check("no cloud carries the workflow evaluation overlay", no_overlay)

runbook = (REPO_ROOT / "docs/runbooks/agent-factory/27-workflow-comparison.md").read_text()
results = (REPO_ROOT / "docs/runbooks/agent-factory/results-workflow-comparison-1.md").read_text()

stale_fields = [
    ".spec.harnessProfile",
    ".status.cohort",
    ".status.costMicroUSD",
    "SHA-256",
    "treatmentPercent",
    "cohort: none",
]
bad_fields = [f for f in stale_fields if f in runbook]
check(f"the runbook reads fields that exist (found: {bad_fields})", not bad_fields)

stale_results = [s for s in ("collecting", "Pending 40 tasks") if s in results]
check(f"the results file is not \"collecting\" (found: {stale_results})", not stale_results)

tooling_paths = sorted(set(re.findall(r"tooling/[A-Za-z0-9_./-]+", runbook)))
missing_paths = [p for p in tooling_paths if not (REPO_ROOT / p.rstrip(".,;:)")).exists()]
check(f"the runbook names no file that is gone (missing: {missing_paths})", not missing_paths)

sys.exit(1 if fails else 0)
