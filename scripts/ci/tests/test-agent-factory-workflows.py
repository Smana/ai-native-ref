#!/usr/bin/env python3
# requires: python3 kustomize
"""The workflows, their step-up, outcomes and custom roles, and the separated merge policies (workflows
review WF1-WF4, WF9-WF11; Maku v0.54.0's workflows and roles redesign, phases C, E, F and I)."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
SHIPPED = {"quick", "standard", "careful"}
CUSTOM = {"thorough"}  # the one custom workflow (phase I, Task I2): reached by its label alone
WORKFLOW_FIELDS = {"harness", "harnessAllowed", "escalation", "testFirst", "checks"}
LEGACY = {"template", "tier", "loop", "checks"}
RANK = {"scoper": 0, "tester": 1, "implementer": 2, "reviewer": 3}
REQUIRABLE = {"plan", "tests", "judge", "review"}
OUTCOMES = {"change", "plan-first", "review", "report"}
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
    roles = factory.get("roles") or {}
    tiers = factory.get("tiers") or {}
    check(f"{cloud}: Factory.spec.workflows names shipped workflows and thorough",
          set(wf).issubset(SHIPPED | CUSTOM))
    check(f"{cloud}: no templates block (deprecated in Maku v0.54.0)", "templates" not in factory)
    check(f"{cloud}: no loops block: the list form carries the stages", "loops" not in factory)
    check(f"{cloud}: triage.controlPercent is 0",
          (factory.get("triage") or {}).get("controlPercent") == 0)
    for name, w in wf.items():
        stages = w.get("stages") or []
        check(f"{cloud} workflow {name}: a whole definition (description, budget, stages; no legacy key)",
              bool(w.get("description")) and w.get("budget") in tiers and stages and not LEGACY & set(w))
        order = [RANK.get(s["role"], RANK["reviewer"]) for s in stages]
        check(f"{cloud} workflow {name}: one implementer, in order",
              [s["role"] for s in stages].count("implementer") == 1 and order == sorted(order))
        impl = next((s for s in stages if s["role"] == "implementer"), {})
        check(f"{cloud} workflow {name}: the implementer runs the checks and stops a stalled run",
              impl.get("checks") is True and impl.get("stall") is True)
        check(f"{cloud} workflow {name}: the built-in reviewer gates",
              any(s["role"] == "reviewer" for s in stages))
        check(f"{cloud} workflow {name}: no stepUp beside escalation", not ("stepUp" in w and "escalation" in w))
    check(f"{cloud}: the ladder: standard steps up to careful, careful to nothing",
          wf.get("standard", {}).get("stepUp") == "careful" and "stepUp" not in wf.get("careful", {})
          and "escalation" not in wf.get("careful", {}))
    order = ["light", "standard", "frontier"]
    check(f"{cloud}: careful's budget is not below standard's",
          order.index(wf["careful"]["budget"]) >= order.index(wf["standard"]["budget"]))
    careful = {s["role"]: s for s in wf["careful"]["stages"]}
    check(f"{cloud}: careful plans first, gates a plan-first task and splits in four at most",
          careful.get("scoper", {}).get("gate") == {"when": "plan-first"}
          and (careful["scoper"].get("split") or {}).get("maxParts", 0) <= 4)
    check(f"{cloud}: the plan runs on the strong model", (factory.get("scoper") or {}).get("planTier") == "frontier")
    check(f"{cloud}: every custom role only reads", all(r.get("capability") == "read" for r in roles.values()))
    check(f"{cloud}: every custom stage is a declared role",
          all(s["role"] in RANK or s["role"] in roles for w in wf.values() for s in w.get("stages") or []))
    check(f"{cloud}: thorough costs no more than a fair share of the day",
          tiers[wf["thorough"]["budget"]]["taskUSD"]
          <= factory["budgets"]["factoryDailyUSD"] / factory["caps"]["activeTasks"])
    check(f"{cloud}: the stepped-up ceiling is affordable",
          factory["caps"]["concurrentRuns"] * tiers["frontier"]["runUSD"] <= factory["budgets"]["factoryDailyUSD"])
    outcomes = factory.get("outcomes") or []
    check(f"{cloud}: the outcomes offered hold change and only Maku's four",
          "change" in outcomes and set(outcomes) <= OUTCOMES)
    check(f"{cloud}: no harness default on the Factory (OpenCode is a label's alone)",
          "harness" not in (factory.get("defaults") or {}))

for d in docs:
        if d["kind"] == "MergePolicy":
            name, spec = d["metadata"]["name"], d.get("spec") or {}
            bad = WORKFLOW_FIELDS & set(spec)
            check(f"{cloud} MergePolicy/{name}: no workflow fields ({sorted(bad)})", not bad)
            check(f"{cloud} MergePolicy/{name}: requires only stages a class may require",
                  set(spec.get("requires") or []) <= REQUIRABLE)
            check(f"{cloud} MergePolicy/{name}: a required plan has a gate to wait at",
                  "plan" not in (spec.get("requires") or []) or "plan-first" in outcomes)
        if d["kind"] == "Repository":
            name, spec = d["metadata"]["name"], d["spec"]
            rw = spec.get("workflow") or {}
            check(f"{cloud} Repository/{name}: workflow.default is standard",
                  rw.get("default") == "standard")
            check(f"{cloud} Repository/{name}: says how it steps up (auto, ask or off)",
                  rw.get("stepUp") in ("auto", "ask", "off"))
            check(f"{cloud} Repository/{name}: says how its plan gate answers (ask or auto)",
                  rw.get("planGate") in ("ask", "auto"))
            if spec["repository"] == "Smana/cloud-native-ref":
                check(f"{cloud}: the host asks before a step-up and before a plan runs",
                      rw.get("stepUp") == "ask" and rw.get("planGate") == "ask")
            if rw.get("testFirst"):
                check(f"{cloud} Repository/{name}: workflow.testFirst has merge.contractCheck",
                      bool((spec.get("merge") or {}).get("contractCheck")))
            for s in spec.get("schedules") or []:
                check(f"{cloud} Repository/{name} schedule {s['name']}: workflow is quick",
                      s.get("workflow") == "quick")
                check(f"{cloud} Repository/{name} schedule {s['name']}: class only with probe",
                      "class" not in s or "probe" in s)

sys.exit(1 if fails else 0)
