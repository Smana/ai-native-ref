#!/usr/bin/env python3
# requires: python3 kustomize
"""The three workflows and the separated merge policies (workflows review WF1-WF4, WF9-WF11)."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
SHIPPED = {"quick", "standard", "careful"}
WORKFLOW_FIELDS = {"harness", "harnessAllowed", "escalation", "testFirst", "checks"}
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


def render(cloud):
    out = subprocess.run(["kustomize", "build", str(ROOT / f"tooling/{cloud}/agent-factory/resources")],
                         capture_output=True, text=True, check=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


for cloud in ("aws-0", "gcp-0"):
    docs = render(cloud)
    factory = next(d for d in docs if d["kind"] == "Factory")["spec"]
    check(f"{cloud}: Factory uses workflows, not harnessProfiles", "harnessProfiles" not in factory)
    wf = factory.get("workflows") or {}
    check(f"{cloud}: Factory.spec.workflows names only shipped workflows",
          set(wf).issubset(SHIPPED))
    check(f"{cloud}: standard and careful set checks: true",
          wf.get("standard", {}).get("checks") is True and wf.get("careful", {}).get("checks") is True)
    check(f"{cloud}: templates has no trio", "trio" not in (factory.get("templates") or {}))
    check(f"{cloud}: triage.controlPercent is 0",
          (factory.get("triage") or {}).get("controlPercent") == 0)
    loops = factory.get("loops") or {}
    check(f"{cloud}: loops has no per-class row", set(loops).issubset({"default", "careful"}))

    for d in docs:
        if d["kind"] == "MergePolicy":
            name, spec = d["metadata"]["name"], d.get("spec") or {}
            bad = WORKFLOW_FIELDS & set(spec)
            check(f"{cloud} MergePolicy/{name}: no workflow fields ({sorted(bad)})", not bad)
            check(f"{cloud} MergePolicy/{name}: no requires", "requires" not in spec)
        if d["kind"] == "Repository":
            name, spec = d["metadata"]["name"], d["spec"]
            rw = spec.get("workflow") or {}
            check(f"{cloud} Repository/{name}: workflow.default is standard",
                  rw.get("default") == "standard")
            if rw.get("testFirst"):
                check(f"{cloud} Repository/{name}: workflow.testFirst has merge.contractCheck",
                      bool((spec.get("merge") or {}).get("contractCheck")))
            for s in spec.get("schedules") or []:
                check(f"{cloud} Repository/{name} schedule {s['name']}: workflow is quick",
                      s.get("workflow") == "quick")
                check(f"{cloud} Repository/{name} schedule {s['name']}: class only with probe",
                      "class" not in s or "probe" in s)

sys.exit(1 if fails else 0)
