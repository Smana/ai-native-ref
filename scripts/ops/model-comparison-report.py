#!/usr/bin/env python3
"""Report the paired model comparison (Gemini design L4, plan B6) and its frozen directional rule.

  python3 scripts/ops/model-comparison-report.py --arm-a OWNER/REPO --arm-b OWNER/REPO
      [--context CONTEXT] [--namespace agent-system] [--json] [--out FILE]
  python3 scripts/ops/model-comparison-report.py --arm-a OWNER/REPO --arm-b OWNER/REPO --tasks FILE

The same issues are filed twice: on two scratch copies of one repository (an arm is a repository,
OWNER/REPO), or in one repository with a title suffix per arm (an arm is a suffix in brackets, such
as "[trial A]", as the harness trial filed them). Arm A runs agent-default, arm B the model under
test. Tasks pair by issue title, the first line of spec.text (`# <title>`), the arm's suffix removed. It reads the
fields real Tasks carry (Maku v0.55): status.endedAt, status.outcome, status.usage.costMicroUSD and
.tokens, status.reviewRounds, status.profile.name and .harness, spec.budget, and status.runs[] (role,
verdict, reason, servedModels).

It refuses (exit 2) when a pair's arms differ in anything but the model: workflow (profile.name),
harness (profile.harness) or caps (spec.budget, its model aside: the tier the classifier rated
included). --drop-mismatched instead leaves such pairs out and lists them in the report.

Frozen directional rule (n=10, not a statistical gate), B earns a 30+30 treatmentModel trial when:
  - B's merged count is at least A's minus one;
  - B's USD per merged task (total USD / merged) is at most 1.5 x A's;
  - B has zero signature 400s.

Run ends are read from status.runs[].reason: `budget-*` is a cap, `agent_stuck` a stall, and a
reason naming a thought signature or HTTP 400 a signature 400. Cross-check the 400s with the gateway's
access log (runbook), since a provider error may end a run under another reason.
"""
import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime

MERGED = {"accepted", "merged_human"}
MICRO = 1_000_000
CAPS = ("tier", "runTokens", "taskTokens", "runMinutes", "runMicroUSD", "taskMicroUSD")
MERGED_TOLERANCE = 1
MAX_COST_RATIO = 1.5


def title(task):
    first = ((task.get("spec") or {}).get("text") or "").split("\n", 1)[0]
    return first[2:].strip() if first.startswith("# ") else first.strip()


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def profile(task):
    p = (task.get("status") or {}).get("profile") or {}
    return {"workflow": p.get("name"), "harness": p.get("harness")}


def caps(task):
    b = (task.get("spec") or {}).get("budget") or {}
    return {k: b.get(k) for k in CAPS}


def run_end(reason):
    r = (reason or "").lower()
    if "thought_signature" in r or "signature" in r or "400" in r:
        return "signature400"
    if r.startswith("budget") or "cap" in r:
        return "cap"
    if r == "agent_stuck" or "stall" in r:
        return "stall"
    return None


def models(task):
    """The models a task's implementer runs were served by, else its budget's alias."""
    runs = (task.get("status") or {}).get("runs") or []
    served = sorted({m for r in runs if r.get("role") == "implementer" for m in (r.get("servedModels") or [])})
    return served or [((task.get("spec") or {}).get("budget") or {}).get("model") or "unknown"]


def arm_of(task, arm):
    """The task's title as its pair key when the task belongs to arm, else None."""
    name = title(task)
    if arm.startswith("["):
        return name[:-len(arm)].strip() if name.endswith(arm) else None
    return name if (task.get("spec") or {}).get("repository") == arm else None


def pair(tasks, arm_a, arm_b):
    """{title: {"A": task, "B": task}} for titles filed on both arms, and the unpaired titles."""
    by = {"A": {}, "B": {}}
    for t in tasks:
        for side, arm in (("A", arm_a), ("B", arm_b)):
            if (key := arm_of(t, arm)) is not None:
                by[side][key] = t
    both = sorted(set(by["A"]) & set(by["B"]))
    unpaired = sorted(set(by["A"]) ^ set(by["B"]))
    return {k: {"A": by["A"][k], "B": by["B"][k]} for k in both}, unpaired


def mismatches(pairs):
    out = []
    for name, p in pairs.items():
        for what, read in (("workflow/harness", profile), ("caps", caps)):
            if read(p["A"]) != read(p["B"]):
                out.append((name, f"{name}: {what} differ: A {read(p['A'])}, B {read(p['B'])}"))
    return out


def arm_summary(tasks):
    ended = [t for t in tasks if (t.get("status") or {}).get("endedAt")]
    merged = [t for t in ended if (t.get("status") or {}).get("outcome") in MERGED]
    usd = [((t.get("status") or {}).get("usage") or {}).get("costMicroUSD", 0) / MICRO for t in ended]
    merged_usd = [((t.get("status") or {}).get("usage") or {}).get("costMicroUSD", 0) / MICRO for t in merged]
    durations = []
    for t in ended:
        start, end = ts((t.get("metadata") or {}).get("creationTimestamp")), ts(t["status"]["endedAt"])
        if start and end and end >= start:
            durations.append((end - start).total_seconds() / 60)
    verdicts, ends = {}, {"cap": 0, "signature400": 0, "stall": 0}
    for t in tasks:
        for r in (t.get("status") or {}).get("runs") or []:
            if r.get("role") == "reviewer" and r.get("verdict"):
                verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
            if kind := run_end(r.get("reason")):
                ends[kind] += 1
    rounds = [(t.get("status") or {}).get("reviewRounds") or 0 for t in merged]
    total = round(sum(usd), 6)
    return {
        "tasks": len(tasks), "ended": len(ended), "merged": len(merged),
        "merged_share": len(merged) / len(ended) if ended else None,
        "usd_total": total,
        "usd_per_merged": total / len(merged) if merged else None,
        "usd_per_merged_median": statistics.median(merged_usd) if merged_usd else None,
        "median_duration_min": statistics.median(durations) if durations else None,
        "verdicts": dict(sorted(verdicts.items())),
        "median_review_rounds": statistics.median(rounds) if rounds else None,
        "ends": ends,
        "models": sorted({m for t in tasks for m in models(t)}),
        "tokens": sum(((t.get("status") or {}).get("usage") or {}).get("tokens", 0) for t in tasks),
    }


def rule(a, b):
    """The frozen directional rule's verdict, with each clause."""
    clauses = {
        "merged": b["merged"] >= a["merged"] - MERGED_TOLERANCE,
        "cost": (b["usd_per_merged"] is not None and a["usd_per_merged"] is not None
                 and b["usd_per_merged"] <= MAX_COST_RATIO * a["usd_per_merged"]),
        "signature400": b["ends"]["signature400"] == 0,
    }
    if a["merged"] == 0:
        return "indecisive: arm A merged nothing, so no cost ratio exists", clauses
    return ("B earns a 30+30 treatmentModel trial" if all(clauses.values())
            else "B does not earn a trial"), clauses


def report(tasks, arm_a, arm_b, drop_mismatched=False):
    pairs, unpaired = pair(tasks, arm_a, arm_b)
    bad = mismatches(pairs)
    dropped = sorted({name for name, _ in bad})
    if bad and not drop_mismatched:
        return None, [line for _, line in bad]
    pairs = {k: v for k, v in pairs.items() if k not in dropped}
    a = arm_summary([p["A"] for p in pairs.values()])
    b = arm_summary([p["B"] for p in pairs.values()])
    verdict, clauses = rule(a, b)
    return {"arm_a": arm_a, "arm_b": arm_b, "pairs": len(pairs), "unpaired": unpaired, "dropped": dropped,
            "A": a, "B": b, "verdict": verdict, "clauses": clauses}, []


def fmt(v):
    return "n/a" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)


def markdown(r):
    rows = [("tasks", "tasks"), ("ended", "ended"), ("merged", "merged"), ("merged share", "merged_share"),
            ("USD total", "usd_total"), ("USD per merged (total / merged)", "usd_per_merged"),
            ("USD per merged (median)", "usd_per_merged_median"), ("median duration (min)", "median_duration_min"),
            ("median review rounds (merged)", "median_review_rounds"), ("tokens", "tokens")]
    out = [f"# Model comparison: {r['arm_a']} (A) vs {r['arm_b']} (B)", "",
           f"{r['pairs']} pairs; unpaired titles: {', '.join(r['unpaired']) or 'none'}; "
           f"dropped (arms differ in more than the model): {', '.join(r['dropped']) or 'none'}", "",
           "| | A | B |", "|---|---|---|"]
    out += [f"| {label} | {fmt(r['A'][k])} | {fmt(r['B'][k])} |" for label, k in rows]
    for k in ("cap", "signature400", "stall"):
        out.append(f"| runs ended by {k} | {r['A']['ends'][k]} | {r['B']['ends'][k]} |")
    out.append(f"| reviewer verdicts | {r['A']['verdicts']} | {r['B']['verdicts']} |")
    out.append(f"| models | {', '.join(r['A']['models'])} | {', '.join(r['B']['models'])} |")
    out += ["", f"**Verdict:** {r['verdict']}", ""]
    out += [f"- {k}: {'holds' if ok else 'fails'}" for k, ok in r["clauses"].items()]
    return "\n".join(out) + "\n"


def kubectl_tasks(context, namespace):
    cmd = ["kubectl"] + (["--context", context] if context else []) + [
        "get", "tasks.maku.ogenki.io", "-n", namespace, "-o", "json"]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout).get("items") or []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm-a", required=True, help="arm A (agent-default): OWNER/REPO, or a title suffix such as '[trial A]'")
    ap.add_argument("--arm-b", required=True, help="arm B (the model under test): OWNER/REPO, or a title suffix")
    ap.add_argument("--context", help="kubectl context")
    ap.add_argument("--namespace", default="agent-system")
    ap.add_argument("--tasks", help="a `kubectl get tasks -o json` file instead of the cluster")
    ap.add_argument("--drop-mismatched", action="store_true", help="leave out pairs whose arms differ in more than the model")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    ap.add_argument("--out", help="also write the report to PATH")
    args = ap.parse_args(argv)
    if args.tasks:
        with open(args.tasks, encoding="utf-8") as f:
            tasks = json.load(f).get("items") or []
    else:
        tasks = kubectl_tasks(args.context, args.namespace)
    r, bad = report(tasks, args.arm_a, args.arm_b, args.drop_mismatched)
    if bad:
        print("refused: the arms differ in more than the model", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 2
    text = json.dumps(r, indent=2, sort_keys=True) + "\n" if args.json else markdown(r)
    sys.stdout.write(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
