#!/usr/bin/env python3
# requires: python3
"""Offline tests for scripts/ops/harness-trial-report.py (OpenCode adopt plan Tasks 4–5).

Verifies the frozen outcome gate, sample floor (<30 -> indecisive), truthful rescue accounting
(failed original arm stays counted, rescue sits in its own row), exclusions, and CLI fixture mode.
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("harness_trial_report", ROOT / "scripts/ops/harness-trial-report.py")
htr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(htr)

fails = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok or not detail else ' -- ' + str(detail)}")
    if not ok:
        fails.append(name)


def make_task(
    name,
    *,
    cohort="control",
    harness="openhands",
    harness_source="cohort",
    outcome="merged",
    cost_usd=2.0,
    duration_min=20,
    tokens=None,
    rescue_baseline_usd=None,
    counted_cohorts=None,
    extra_spec=None,
    extra_labels=None,
    finished=True,
    critical=False,
):
    end_min = int(duration_min)
    end_hr = end_min // 60
    end_m = end_min % 60
    status = {
        "phase": outcome if finished else "running",
        "outcome": outcome if finished else "",
        "startedAt": "2026-11-20T10:00:00Z",
        "profile": {
            "cohort": cohort,
            "harness": harness,
            "harnessSource": harness_source,
            "workflow": "careful",
        },
        "costMicroUSD": int(round(cost_usd * 1_000_000)),
        "tokens": tokens or {"input": 10000, "output": 2000, "cacheRead": 5000, "cacheWrite": 1000},
    }
    if finished:
        status["finishedAt"] = f"2026-11-20T{10 + end_hr:02d}:{end_m:02d}:00Z"
    if rescue_baseline_usd is not None:
        status["rescueBaselineMicroUSD"] = int(round(rescue_baseline_usd * 1_000_000))
    if counted_cohorts is not None:
        status["outcomeCountedCohorts"] = list(counted_cohorts)
    if critical:
        status["criticalRegression"] = True
    return {
        "apiVersion": "maku.ogenki.io/v1alpha1",
        "kind": "Task",
        "metadata": {
            "name": name,
            "creationTimestamp": "2026-11-20T10:00:00Z",
            "labels": extra_labels or {},
        },
        "spec": extra_spec or {},
        "status": status,
    }


def make_cohort(n_ctrl, ctrl_merged, ctrl_cost, ctrl_dur, n_trt, trt_merged, trt_cost, trt_dur):
    tasks = []
    for i in range(n_ctrl):
        tasks.append(make_task(
            f"ctrl-{i}",
            cohort="control",
            harness="openhands",
            outcome="merged" if i < ctrl_merged else "escalated",
            cost_usd=ctrl_cost,
            duration_min=ctrl_dur,
        ))
    for i in range(n_trt):
        tasks.append(make_task(
            f"trt-{i}",
            cohort="treatment",
            harness="opencode",
            outcome="merged" if i < trt_merged else "escalated",
            cost_usd=trt_cost,
            duration_min=trt_dur,
        ))
    return tasks


print("sample floor")
small = make_cohort(29, 25, 2.0, 20, 29, 25, 1.0, 10)
res = htr.summarize(small)
check("fewer than 30 ended per arm is indecisive even with 50% cost win", res["gate"]["verdict"] == "indecisive", res["gate"])

print("frozen outcome gate")
cost_win = make_cohort(30, 24, 2.0, 20, 30, 23, 1.60, 20)
res = htr.summarize(cost_win)
check(">=15% cost improvement with <=5pp merge delta passes", res["gate"]["verdict"] == "passes", res["gate"])

speed_win = make_cohort(30, 24, 2.0, 20, 30, 24, 2.15, 16)
res = htr.summarize(speed_win)
check(">=15% speed improvement with <=10% cost regression passes", res["gate"]["verdict"] == "passes", res["gate"])

merge_drop = make_cohort(30, 25, 2.0, 20, 30, 23, 1.40, 14)
res = htr.summarize(merge_drop)
check(">5pp merge-rate drop fails even with large cost/speed win", res["gate"]["verdict"] == "does not pass", res["gate"])

cost_reg = make_cohort(30, 24, 2.0, 20, 30, 24, 2.30, 12)
res = htr.summarize(cost_reg)
check(">10% cost regression fails even with 40% speed win", res["gate"]["verdict"] == "does not pass", res["gate"])

no_win = make_cohort(30, 24, 2.0, 20, 30, 24, 1.80, 18)
res = htr.summarize(no_win)
check("<15% improvement on both cost and duration fails", res["gate"]["verdict"] == "does not pass", res["gate"])

crit = make_cohort(30, 24, 2.0, 20, 30, 24, 1.20, 10)
res = htr.summarize(crit, critical_regressions=1)
check("critical regression fails immediately", res["gate"]["verdict"] == "does not pass", res["gate"])

print("truthful rescue accounting")
tasks = make_cohort(30, 24, 2.0, 20, 29, 24, 1.50, 15)
# 30th treatment task failed on OpenCode ($1.50), then rescued via `/factory retry harness=openhands` (+$0.80, merged).
tasks.append(make_task(
    "trt-rescued",
    cohort="rescue",
    harness="openhands",
    harness_source="rescue",
    outcome="merged",
    cost_usd=2.30,
    rescue_baseline_usd=1.50,
    counted_cohorts=["treatment"],
    duration_min=35,
))
res = htr.summarize(tasks)
check("rescued task counts failed original attempt under treatment (30 ended, 24 merged)",
      res["arms"]["treatment"]["ended"] == 30 and res["arms"]["treatment"]["merged"] == 24, res["arms"]["treatment"])
check("rescued task never inflates control trial merges (still 30 ended, 24 merged)",
      res["arms"]["control"]["ended"] == 30 and res["arms"]["control"]["merged"] == 24, res["arms"]["control"])
check("rescue row records the post-rescue spend ($0.80) and merge separately",
      res["arms"]["rescue"]["ended"] == 1 and res["arms"]["rescue"]["merged"] == 1
      and abs(res["arms"]["rescue"]["usd"] - 0.80) < 1e-6, res["arms"]["rescue"])
check("treatment spend includes failed original baseline ($1.50) without double-counting rescue spend",
      abs(res["arms"]["treatment"]["usd"] - (29 * 1.50 + 1.50)) < 1e-6, res["arms"]["treatment"])

print("exclusions and CLI fixtures")
tasks_with_noise = list(cost_win) + [
    make_task("ex-labeled", cohort="labeled", harness="opencode"),
    make_task("ex-scheduled", cohort="treatment", extra_spec={"source": "schedule"}),
    make_task("ex-adopted", cohort="treatment", extra_spec={"adopted": True}),
    make_task("ex-integration", cohort="treatment", extra_spec={"integrationOnly": True}),
    make_task("ex-running", cohort="treatment", finished=False),
]
res = htr.summarize(tasks_with_noise)
check("excluded traffic never alters trial arm counts",
      res["arms"]["control"]["ended"] == 30 and res["arms"]["treatment"]["ended"] == 30, res["arms"])
check("every exclusion category is itemized",
      res["exclusions"] == {"adopted": 1, "integration": 1, "labeled": 1, "not_ended": 1, "scheduled": 1},
      res["exclusions"])

with tempfile.TemporaryDirectory() as td:
    d = pathlib.Path(td)
    (d / "tasks.json").write_text(json.dumps({"items": tasks_with_noise}))
    (d / "meta.json").write_text(json.dumps({"cluster": "aws-0", "maku_version": "v0.54.0@sha256:test"}))
    out_md = d / "report.md"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = htr.main(["--fixtures", str(d), "--out", str(out_md)])
    md = out_md.read_text()
    check("CLI exits 0 and writes markdown report with verdict",
          rc == 0 and "**Verdict:** `passes`" in md and "Rescue (`openhands`)" in md and md == buf.getvalue(),
          (rc, md[:200]))
    check("report renders a Total tokens row immediately after Cache-write tokens",
          md.splitlines()[md.splitlines().index([l for l in md.splitlines() if l.startswith("| Cache-write tokens")][0]) + 1].startswith("| Total tokens"),
          md)

print("status.usage cost and total tokens")
usage_task = make_task(
    "trt-usage-only",
    cohort="treatment",
    harness="opencode",
    outcome="merged",
    cost_usd=0.0,
    tokens={},
)
del usage_task["status"]["costMicroUSD"]
usage_task["status"]["usage"] = {"costMicroUSD": 696292, "tokens": 1931412}
res = htr.summarize([usage_task])
check("a Task priced only via status.usage.costMicroUSD costs $0.696292 and is not unpriced",
      res["arms"]["treatment"]["usd"] == 0.696292 and res["arms"]["treatment"]["unpriced"] == 0,
      res["arms"]["treatment"])
check("status.usage.tokens adds 1,931,412 to the arm total tokens",
      res["arms"]["treatment"]["tokens"]["total"] == 1931412,
      res["arms"]["treatment"]["tokens"])

both_task = make_task(
    "ctrl-both",
    cohort="control",
    outcome="merged",
    cost_usd=1.25,
    tokens={"input": 100, "output": 20, "cacheRead": 0, "cacheWrite": 0},
)
both_task["status"]["usage"] = {"costMicroUSD": 500000, "tokens": 999}
res = htr.summarize([both_task])
check("status.costMicroUSD takes precedence over status.usage.costMicroUSD",
      res["arms"]["control"]["usd"] == 1.25, res["arms"]["control"])
check("status.usage.tokens takes precedence over the tokens map for the total",
      res["arms"]["control"]["tokens"]["total"] == 999, res["arms"]["control"]["tokens"])

split_task = make_task(
    "ctrl-split",
    cohort="control",
    outcome="merged",
    tokens={"input": 100, "output": 20, "cacheRead": 30, "cacheWrite": 10},
)
res = htr.summarize([split_task])
check("without status.usage.tokens the total is the sum of the four token keys",
      res["arms"]["control"]["tokens"]["total"] == 160, res["arms"]["control"]["tokens"])

if fails:
    print("FAIL\n  " + "\n  ".join(fails))
    sys.exit(1)
print("PASS: harness-trial-report")
