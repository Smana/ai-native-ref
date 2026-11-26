#!/usr/bin/env python3
# requires: python3
"""Offline tests for scripts/ops/model-comparison-report.py (Gemini plan B6).

Every Task derives from model-comparison-fixtures/task-gcp-0.json, a real Task read from gcp-0 on
2026-11-26 (Maku v0.55), trimmed: only the fields Tasks carry, never invented ones (the harness
trial report's lesson, results-harness-paired-trial-2026-11-26.md).
"""
import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("model_comparison_report", ROOT / "scripts/ops/model-comparison-report.py")
mcr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcr)
REAL = json.loads((pathlib.Path(__file__).parent / "model-comparison-fixtures/task-gcp-0.json").read_text())
A, B = "Smana/scratch-a", "Smana/scratch-b"
fails = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok or not detail else ' -- ' + str(detail)}")
    if not ok:
        fails.append(name)


def task(repo, n, *, outcome="accepted", usd=1.0, minutes=60, model="agent-default", reasons=("agent_finished",),
         verdict="approve", ended=True, rounds=None):
    t = copy.deepcopy(REAL)
    t["metadata"]["name"] = f"{repo[-1]}{n}"
    t["metadata"]["creationTimestamp"] = "2026-11-27T10:00:00Z"
    t["spec"]["repository"] = repo
    t["spec"]["text"] = f"# issue {n}\n\nbody"
    t["spec"]["budget"]["model"] = model
    s = t["status"]
    s["outcome"] = outcome
    s["usage"]["costMicroUSD"] = int(usd * 1_000_000)
    s["endedAt"] = f"2026-11-27T{10 + minutes // 60:02d}:{minutes % 60:02d}:00Z"
    if not ended:
        s.pop("endedAt")
    if rounds is not None:
        s["reviewRounds"] = rounds
    s["runs"] = [{"id": f"r{i}", "role": "implementer", "trigger": "initial", "reason": r, "tokens": 10, "costMicroUSD": 1}
                 for i, r in enumerate(reasons)] + [{"id": "rv", "role": "reviewer", "trigger": "review",
                                                     "reason": "agent_finished", "verdict": verdict}]
    return t


def world(b_outcomes, b_usd=1.0, b_reasons=("agent_finished",)):
    ts = [task(A, n) for n in range(10)]
    ts += [task(B, n, outcome=o, usd=b_usd, model="gemini-standard", reasons=b_reasons) for n, o in enumerate(b_outcomes)]
    return ts


print("the real Task's fields")
r = mcr.arm_summary([REAL])
check("a real Done/accepted Task counts as ended and merged", r["ended"] == 1 and r["merged"] == 1, r)
check("its cost is status.usage.costMicroUSD", r["usd_total"] == 0.273143, r["usd_total"])
check("its duration runs from creationTimestamp to status.endedAt (65 min 2 s)", round(r["median_duration_min"] * 60) == 3902, r)
check("its reviewer verdict counts", r["verdicts"] == {"approve": 1}, r["verdicts"])
check("its model falls back to spec.budget.model", r["models"] == ["agent-default"], r["models"])
check("merged_human counts as merged, closed does not", mcr.arm_summary(
    [task(A, 1, outcome="merged_human"), task(A, 2, outcome="closed")])["merged"] == 1)
check("a Task without endedAt is not ended", mcr.arm_summary([task(A, 1, ended=False)])["ended"] == 0)

print("pairing")
pairs, unpaired = mcr.pair([task(A, 1), task(B, 1), task(A, 2), task(B, 3), task("Smana/other", 1)], A, B)
check("pairs by issue title across the two repositories", list(pairs) == ["issue 1"], list(pairs))
check("lists the titles filed on one arm only", unpaired == ["issue 2", "issue 3"], unpaired)

t1, t2 = task(A, 1), task(A, 1)
t1["spec"]["text"], t2["spec"]["text"] = "# fix(x): y [trial A]\n", "# fix(x): y [trial B]\n"
pairs, _ = mcr.pair([t1, t2, task(A, 2)], "[trial A]", "[trial B]")
check("or by title suffix in one repository, the suffix removed", list(pairs) == ["fix(x): y"], list(pairs))

print("the arms differ only in model")
for name, edit in (("workflow", lambda t: t["status"]["profile"].update({"name": "careful"})),
                   ("harness", lambda t: t["status"]["profile"].update({"harness": "openhands"})),
                   ("caps", lambda t: t["spec"]["budget"].update({"runMicroUSD": 1}))):
    b = task(B, 1, model="gemini-standard")
    edit(b)
    r, bad = mcr.report([task(A, 1), b], A, B)
    check(f"refuses arms that differ in {name}", r is None and len(bad) == 1, bad)
b = task(B, 2, model="gemini-standard")
b["spec"]["budget"]["tier"] = "frontier"
r, bad = mcr.report([task(A, 1), task(B, 1, model="gemini-standard"), task(A, 2), b], A, B, drop_mismatched=True)
check("--drop-mismatched leaves out a pair the classifier rated differently, and names it",
      r is not None and r["pairs"] == 1 and r["dropped"] == ["issue 2"], r and r["dropped"])
r, bad = mcr.report([task(A, 1), task(B, 1, model="gemini-standard")], A, B)
check("accepts arms that differ in the model only", r is not None and not bad, bad)

print("the frozen directional rule")
r, _ = mcr.report(world(["accepted"] * 9 + ["closed"]), A, B)
check("B one merge short, same cost, no 400: earns a trial",
      r["verdict"].startswith("B earns") and r["A"]["merged"] == 10 and r["B"]["merged"] == 9, r["verdict"])
r, _ = mcr.report(world(["accepted"] * 8 + ["closed"] * 2), A, B)
check("B two merges short: does not earn one", r["verdict"] == "B does not earn a trial" and not r["clauses"]["merged"], r)
r, _ = mcr.report(world(["accepted"] * 10, b_usd=1.6), A, B)
check("B at 1.6x the USD per merged task: does not earn one", not r["clauses"]["cost"], r["clauses"])
r, _ = mcr.report(world(["accepted"] * 10, b_usd=1.5), A, B)
check("B at exactly 1.5x: the cost clause holds", r["clauses"]["cost"], r["clauses"])
r, _ = mcr.report(world(["accepted"] * 10, b_reasons=("agent_finished", "provider 400: thought_signature missing")), A, B)
check("one signature 400 on B: does not earn one", not r["clauses"]["signature400"] and r["B"]["ends"]["signature400"] == 10, r["B"]["ends"])
r, _ = mcr.report(world(["accepted"] * 10, b_reasons=("budget-run", "agent_stuck")), A, B)
check("budget-run is a cap and agent_stuck a stall", r["B"]["ends"] == {"cap": 10, "signature400": 0, "stall": 10}, r["B"]["ends"])
ts = [task(A, n, outcome="closed") for n in range(3)] + [task(B, n, model="gemini-standard") for n in range(3)]
r, _ = mcr.report(ts, A, B)
check("A merging nothing is indecisive", r["verdict"].startswith("indecisive"), r["verdict"])

print("the CLI")
with tempfile.TemporaryDirectory() as d:
    f = pathlib.Path(d, "tasks.json")
    f.write_text(json.dumps({"items": world(["accepted"] * 10)}))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = mcr.main(["--arm-a", A, "--arm-b", B, "--tasks", str(f), "--json"])
    data = json.loads(out.getvalue())
    check("--tasks --json exits 0 with both arms", code == 0 and data["pairs"] == 10 and data["B"]["models"] == ["gemini-standard"], data)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        mcr.main(["--arm-a", A, "--arm-b", B, "--tasks", str(f)])
    check("Markdown carries the verdict", "**Verdict:** B earns a 30+30 treatmentModel trial" in out.getvalue(), out.getvalue())
    bad = world(["accepted"] * 10)
    bad[-1]["status"]["profile"]["harness"] = "openhands"
    f.write_text(json.dumps({"items": bad}))
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = mcr.main(["--arm-a", A, "--arm-b", B, "--tasks", str(f)])
    check("a mismatched pair exits 2 and names it", code == 2 and "issue 9" in err.getvalue(), err.getvalue())

if fails:
    print(f"\n{len(fails)} failure(s)")
    sys.exit(1)
print("\nall passed")
