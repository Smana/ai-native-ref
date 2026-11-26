#!/usr/bin/env python3
"""Evaluate the gcp-0 OpenCode vs OpenHands 50/50 harness trial against the frozen outcome gate.

  python3 scripts/ops/harness-trial-report.py --context gcp-0 [--namespace agent-system]
      [--since ISO8601] [--until ISO8601] [--vm-url URL] [--critical-regressions N] [--out FILE]
  python3 scripts/ops/harness-trial-report.py --fixtures DIR [--out FILE]

Reads real Task CRs (maku.ogenki.io/v1alpha1) and VictoriaMetrics token/cost series (or DIR/tasks.json,
optional DIR/vm-tokens.json and DIR/meta.json with --fixtures).

Frozen decision rule (docs/superpowers/specs/2026-11-15-opencode-harness-design.md §10, adopt plan Task 5):
  - At least 30 ended tasks in BOTH control (openhands) and treatment (opencode) arms; fewer -> indecisive.
  - Critical security, audit, or recovery regressions = 0.
  - Merge-rate difference (OpenHands - OpenCode) <= 5 percentage points.
  - Cost-per-merged-PR regression <= 10%.
  - Cost-per-merged-PR improvement >= 15% OR median end-to-end task duration improvement >= 15%.

Truthful rescue accounting:
  - A task rescued via `/factory retry harness=openhands` carries cohort=rescue (or harnessSource=rescue)
    while its original failed OpenCode attempt was counted under treatment (or outcomeCountedCohorts).
  - The original failure stays in the original trial arm (never erased); the rescue attempt is reported
    solely in the separate `rescue` row and never counts as an OpenCode or OpenHands trial success.

Excluded traffic (listed explicitly, never counted in either arm):
  - `labeled` cohort (e.g. explicit `harness:opencode` smoke tasks),
  - scheduled, adopted, integration-only, and non-ended tasks.
"""
import argparse
from datetime import datetime, timezone
import json
import pathlib
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request

MIN_ENDED_PER_ARM = 30
MAX_MERGE_RATE_DROP = 0.05
MAX_COST_REGRESSION = 0.10
MIN_WIN_IMPROVEMENT = 0.15
MICRO = 1_000_000.0
VM_PROXY = "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy"

ENDED_PHASES = {"merged", "closed", "escalated", "failed", "aborted", "cancelled", "succeeded", "completed"}
MERGED_OUTCOMES = {"merged"}
TOKEN_KEYS = ("input", "output", "cacheRead", "cacheWrite")
TOTAL_KEY = "total"


def parse_ts(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _task_phase(task):
    status = task.get("status") or {}
    return str(status.get("phase") or status.get("state") or "").strip().lower()


def _task_outcome(task):
    status = task.get("status") or {}
    outcome = str(status.get("outcome") or "").strip().lower()
    if outcome:
        return outcome
    phase = _task_phase(task)
    if phase == "merged":
        return "merged"
    if phase in ("escalated", "failed", "closed", "aborted", "cancelled"):
        return phase
    return ""


def _is_ended(task):
    status = task.get("status") or {}
    if status.get("finishedAt") or status.get("completedAt"):
        return True
    return _task_phase(task) in ENDED_PHASES or _task_outcome(task) in ENDED_PHASES


def _duration_minutes(task):
    meta = task.get("metadata") or {}
    status = task.get("status") or {}
    start = parse_ts(status.get("startedAt") or meta.get("creationTimestamp"))
    end = parse_ts(status.get("finishedAt") or status.get("completedAt"))
    if not start or not end or end < start:
        return None
    return (end - start).total_seconds() / 60.0


def _cost_usd(task):
    status = task.get("status") or {}
    if "costMicroUSD" in status and status["costMicroUSD"] is not None:
        return float(status["costMicroUSD"]) / MICRO
    if "spendMicroUSD" in status and status["spendMicroUSD"] is not None:
        return float(status["spendMicroUSD"]) / MICRO
    if "usd" in status and status["usd"] is not None:
        return float(status["usd"])
    usage = status.get("usage") or {}
    if "costMicroUSD" in usage and usage["costMicroUSD"] is not None:
        return float(usage["costMicroUSD"]) / MICRO
    return None


def _tokens(task):
    status = task.get("status") or {}
    tok = status.get("tokens") or {}
    toks = {k: int(tok.get(k) or 0) for k in TOKEN_KEYS}
    usage = status.get("usage") or {}
    if "tokens" in usage and usage["tokens"] is not None:
        toks["total"] = int(usage["tokens"])
    else:
        toks["total"] = sum(toks.values())
    return toks


def _exclusion_reason(task, since=None, until=None):
    spec = task.get("spec") or {}
    status = task.get("status") or {}
    meta = task.get("metadata") or {}
    labels = meta.get("labels") or {}
    profile = status.get("profile") or {}
    cohort = str(profile.get("cohort") or "").strip().lower()
    workflow = str(profile.get("workflow") or spec.get("workflow") or "").strip().lower()

    created = parse_ts(meta.get("creationTimestamp") or status.get("startedAt"))
    if since and created and created < since:
        return "outside_window"
    if until and created and created >= until:
        return "outside_window"
    if not _is_ended(task):
        return "not_ended"
    if spec.get("scheduled") or spec.get("source") == "schedule" or labels.get("maku.ogenki.io/scheduled") == "true":
        return "scheduled"
    if spec.get("adopted") or status.get("adopted") or labels.get("maku.ogenki.io/adopted") == "true":
        return "adopted"
    if spec.get("integrationOnly") or workflow == "integration" or labels.get("maku.ogenki.io/integration") == "true":
        return "integration"
    if cohort == "labeled":
        return "labeled"
    return None


def _empty_arm():
    return {
        "ended": 0,
        "merged": 0,
        "usd": 0.0,
        "unpriced": 0,
        "durations_min": [],
        "tokens": {k: 0 for k in TOKEN_KEYS + (TOTAL_KEY,)},
    }


def _finalize_arm(arm):
    ended = arm["ended"]
    merged = arm["merged"]
    usd = round(arm["usd"], 6)
    durations = sorted(arm["durations_min"])
    return {
        "ended": ended,
        "merged": merged,
        "merge_rate": (merged / ended) if ended else None,
        "usd": usd,
        "cost_per_merged_usd": (usd / merged) if merged else None,
        "median_duration_min": statistics.median(durations) if durations else None,
        "unpriced": arm["unpriced"],
        "tokens": dict(arm["tokens"]),
    }


def summarize(tasks, *, vm_tokens=None, since=None, until=None, critical_regressions=0, min_ended=MIN_ENDED_PER_ARM):
    """Aggregate tasks into control (openhands), treatment (opencode), rescue, and exclusions, then evaluate gate."""
    arms = {
        "control": _empty_arm(),
        "treatment": _empty_arm(),
        "rescue": _empty_arm(),
    }
    exclusions = {}
    inferred_critical = 0

    for task in tasks:
        reason = _exclusion_reason(task, since=since, until=until)
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue

        status = task.get("status") or {}
        profile = status.get("profile") or {}
        cohort = str(profile.get("cohort") or "").strip().lower()
        harness_source = str(profile.get("harnessSource") or "").strip().lower()
        outcome = _task_outcome(task)
        merged = outcome in MERGED_OUTCOMES
        dur = _duration_minutes(task)
        cost = _cost_usd(task)
        toks = _tokens(task)

        ann = (task.get("metadata") or {}).get("annotations") or {}
        if str(ann.get("maku.ogenki.io/critical-regression") or "").lower() == "true" or status.get("criticalRegression"):
            inferred_critical += 1

        if cohort == "rescue" or harness_source == "rescue":
            # Original failed OpenCode attempt stays counted under its original arm (default: treatment).
            counted_cohorts = [str(c).strip().lower() for c in (status.get("outcomeCountedCohorts") or [])]
            orig_arm = "treatment"
            if "control" in counted_cohorts and "treatment" not in counted_cohorts:
                orig_arm = "control"

            baseline_micro = status.get("rescueBaselineMicroUSD")
            orig_cost = (float(baseline_micro) / MICRO) if baseline_micro is not None else None
            rescue_cost = None
            if cost is not None and orig_cost is not None:
                rescue_cost = max(0.0, cost - orig_cost)
            elif cost is not None:
                # If no baseline was recorded, attribute spend conservatively to the failed original arm.
                orig_cost = cost
                rescue_cost = 0.0

            arms[orig_arm]["ended"] += 1
            if orig_cost is None:
                arms[orig_arm]["unpriced"] += 1
            else:
                arms[orig_arm]["usd"] += orig_cost

            arms["rescue"]["ended"] += 1
            if merged:
                arms["rescue"]["merged"] += 1
            if rescue_cost is None:
                arms["rescue"]["unpriced"] += 1
            else:
                arms["rescue"]["usd"] += rescue_cost
            if dur is not None:
                arms["rescue"]["durations_min"].append(dur)
            for k in TOKEN_KEYS + (TOTAL_KEY,):
                arms["rescue"]["tokens"][k] += toks[k]
            continue

        if cohort not in ("control", "treatment"):
            exclusions[f"cohort:{cohort or 'none'}"] = exclusions.get(f"cohort:{cohort or 'none'}", 0) + 1
            continue

        bucket = arms[cohort]
        bucket["ended"] += 1
        if merged:
            bucket["merged"] += 1
        if cost is None:
            bucket["unpriced"] += 1
        else:
            bucket["usd"] += cost
        if dur is not None:
            bucket["durations_min"].append(dur)
        for k in TOKEN_KEYS + (TOTAL_KEY,):
            bucket["tokens"][k] += toks[k]

    # Merge optional VictoriaMetrics token readings when provided by arm.
    if isinstance(vm_tokens, dict):
        for arm_name in ("control", "treatment", "rescue"):
            src = vm_tokens.get(arm_name)
            if isinstance(src, dict):
                for k in TOKEN_KEYS:
                    if k in src and src[k] is not None:
                        arms[arm_name]["tokens"][k] = int(src[k])

    summary_arms = {name: _finalize_arm(data) for name, data in arms.items()}
    total_critical = int(critical_regressions) + inferred_critical
    gate = evaluate_gate(summary_arms["control"], summary_arms["treatment"], total_critical, min_ended=min_ended)
    return {
        "arms": summary_arms,
        "exclusions": dict(sorted(exclusions.items())),
        "critical_regressions": total_critical,
        "gate": gate,
    }


def evaluate_gate(control, treatment, critical_regressions, *, min_ended=MIN_ENDED_PER_ARM):
    """Apply the frozen replacement gate. Returns verdict in {'passes', 'does not pass', 'indecisive'}."""
    reasons = []
    if critical_regressions > 0:
        reasons.append(f"critical regressions = {critical_regressions} (must be 0)")

    sample_ok = control["ended"] >= min_ended and treatment["ended"] >= min_ended
    if not sample_ok:
        reasons.append(
            f"insufficient sample: control={control['ended']}, treatment={treatment['ended']} (need >= {min_ended} ended each)"
        )
        verdict = "does not pass" if critical_regressions > 0 else "indecisive"
        return {
            "verdict": verdict,
            "sample_ok": False,
            "critical_ok": critical_regressions == 0,
            "merge_rate_ok": None,
            "cost_regression_ok": None,
            "win_ok": None,
            "merge_rate_drop": None,
            "cost_delta_pct": None,
            "duration_delta_pct": None,
            "reasons": reasons,
        }

    merge_drop = control["merge_rate"] - treatment["merge_rate"]
    merge_ok = merge_drop <= MAX_MERGE_RATE_DROP + 1e-12
    if not merge_ok:
        reasons.append(f"merge-rate drop {merge_drop * 100:.2f}pp exceeds 5.00pp limit")

    c_cost = control["cost_per_merged_usd"]
    t_cost = treatment["cost_per_merged_usd"]
    if c_cost is None or t_cost is None or c_cost <= 0:
        cost_delta_pct = None
        cost_reg_ok = False
        cost_win = False
        reasons.append("cost per merged PR unavailable (0 merged PRs in at least one arm)")
    else:
        cost_delta_pct = (t_cost - c_cost) / c_cost
        cost_reg_ok = cost_delta_pct <= MAX_COST_REGRESSION + 1e-12
        cost_win = cost_delta_pct <= -MIN_WIN_IMPROVEMENT + 1e-12
        if not cost_reg_ok:
            reasons.append(f"cost-per-merged-PR regression {cost_delta_pct * 100:.2f}% exceeds 10.00% limit")

    c_dur = control["median_duration_min"]
    t_dur = treatment["median_duration_min"]
    if c_dur is None or t_dur is None or c_dur <= 0:
        dur_delta_pct = None
        dur_win = False
    else:
        dur_delta_pct = (t_dur - c_dur) / c_dur
        dur_win = dur_delta_pct <= -MIN_WIN_IMPROVEMENT + 1e-12

    win_ok = cost_win or dur_win
    if not win_ok:
        c_str = "n/a" if cost_delta_pct is None else f"{-cost_delta_pct * 100:.2f}%"
        d_str = "n/a" if dur_delta_pct is None else f"{-dur_delta_pct * 100:.2f}%"
        reasons.append(f"no >=15% win (cost improvement={c_str}, median duration improvement={d_str})")

    passes = (critical_regressions == 0) and merge_ok and cost_reg_ok and win_ok
    return {
        "verdict": "passes" if passes else "does not pass",
        "sample_ok": True,
        "critical_ok": critical_regressions == 0,
        "merge_rate_ok": merge_ok,
        "cost_regression_ok": cost_reg_ok,
        "win_ok": win_ok,
        "merge_rate_drop": merge_drop,
        "cost_delta_pct": cost_delta_pct,
        "duration_delta_pct": dur_delta_pct,
        "reasons": reasons,
    }


def _fmt_pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_usd(value):
    return "n/a" if value is None else f"${value:.2f}"


def _fmt_min(value):
    return "n/a" if value is None else f"{value:.1f} min"


def render(result, *, cluster="gcp-0", maku_version="unknown", window="all"):
    ctrl = result["arms"]["control"]
    trt = result["arms"]["treatment"]
    rsc = result["arms"]["rescue"]
    gate = result["gate"]

    lines = [
        f"# Harness Trial Report — {cluster}",
        "",
        f"Cluster `{cluster}` · Maku `{maku_version}` · Window `{window}`",
        "",
        f"**Verdict:** `{gate['verdict']}`",
        "",
        "## Cohort Summary",
        "",
        "| Metric | Control (`openhands`) | Treatment (`opencode`) | Rescue (`openhands`) |",
        "|---|---|---|---|",
        f"| Ended tasks | {ctrl['ended']} | {trt['ended']} | {rsc['ended']} |",
        f"| Merged PRs | {ctrl['merged']} | {trt['merged']} | {rsc['merged']} |",
        f"| Merge rate | {_fmt_pct(ctrl['merge_rate'])} | {_fmt_pct(trt['merge_rate'])} | {_fmt_pct(rsc['merge_rate'])} |",
        f"| Total spend (USD) | {_fmt_usd(ctrl['usd'])} | {_fmt_usd(trt['usd'])} | {_fmt_usd(rsc['usd'])} |",
        f"| Cost per merged PR | {_fmt_usd(ctrl['cost_per_merged_usd'])} | {_fmt_usd(trt['cost_per_merged_usd'])} | {_fmt_usd(rsc['cost_per_merged_usd'])} |",
        f"| Median end-to-end duration | {_fmt_min(ctrl['median_duration_min'])} | {_fmt_min(trt['median_duration_min'])} | {_fmt_min(rsc['median_duration_min'])} |",
        f"| Unpriced tasks | {ctrl['unpriced']} | {trt['unpriced']} | {rsc['unpriced']} |",
        f"| Input tokens | {ctrl['tokens']['input']:,} | {trt['tokens']['input']:,} | {rsc['tokens']['input']:,} |",
        f"| Output tokens | {ctrl['tokens']['output']:,} | {trt['tokens']['output']:,} | {rsc['tokens']['output']:,} |",
        f"| Cache-read tokens | {ctrl['tokens']['cacheRead']:,} | {trt['tokens']['cacheRead']:,} | {rsc['tokens']['cacheRead']:,} |",
        f"| Cache-write tokens | {ctrl['tokens']['cacheWrite']:,} | {trt['tokens']['cacheWrite']:,} | {rsc['tokens']['cacheWrite']:,} |",
        f"| Total tokens | {ctrl['tokens'][TOTAL_KEY]:,} | {trt['tokens'][TOTAL_KEY]:,} | {rsc['tokens'][TOTAL_KEY]:,} |",
        f"| Critical security/audit/recovery regressions | — | {result['critical_regressions']} | — |",
        "",
        "## Frozen Gate Checks",
        "",
        f"- Sample floor (>= {MIN_ENDED_PER_ARM} ended per arm): **{'PASS' if gate['sample_ok'] else 'INDECISIVE'}**",
        f"- Critical regressions == 0: **{'PASS' if gate['critical_ok'] else 'FAIL'}** ({result['critical_regressions']})",
        f"- Merge-rate delta (OpenHands - OpenCode <= 5pp): **{_gate_flag(gate['merge_rate_ok'])}**",
        f"- Cost-per-merged-PR regression <= 10%: **{_gate_flag(gate['cost_regression_ok'])}**",
        f"- >= 15% improvement (cost or median duration): **{_gate_flag(gate['win_ok'])}**",
    ]
    if gate["reasons"]:
        lines.append("")
        lines.append("Notes:")
        for reason in gate["reasons"]:
            lines.append(f"- {reason}")

    lines.extend(["", "## Exclusions", ""])
    if result["exclusions"]:
        for key, count in result["exclusions"].items():
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _gate_flag(value):
    if value is None:
        return "N/A"
    return "PASS" if value else "FAIL"


def _kubectl_tasks(context, namespace):
    cmd = ["kubectl"]
    if context:
        cmd.extend(["--context", context])
    cmd.extend(["get", "tasks.maku.ogenki.io", "-n", namespace, "-o", "json"])
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(res.stdout)
    return data.get("items") or []


def _query_vm(promql, context, vm_url):
    qs = urllib.parse.urlencode({"query": promql})
    if vm_url:
        with urllib.request.urlopen(f"{vm_url.rstrip('/')}/api/v1/query?{qs}", timeout=30) as resp:
            return json.load(resp)
    cmd = ["kubectl"]
    if context:
        cmd.extend(["--context", context])
    cmd.extend(["get", "--raw", f"{VM_PROXY}/api/v1/query?{qs}"])
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(res.stdout)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(
            "usage: harness-trial-report.py --context CONTEXT [--namespace NAMESPACE] [--out FILE] | "
            "--fixtures DIR [--out FILE]   (input: JSON lines of ended Task CRs, e.g. tasks.jsonl)",
            file=sys.stderr,
        )
        return 2
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--context", default="gcp-0", help="kubectl context name")
    ap.add_argument("--namespace", default="agent-system", help="Task CR namespace")
    ap.add_argument("--maku-version", default="unknown", help="Maku release version/digest for report header")
    ap.add_argument("--since", help="UTC ISO-8601 window start (inclusive)")
    ap.add_argument("--until", help="UTC ISO-8601 window end (exclusive)")
    ap.add_argument("--vm-url", help="VictoriaMetrics base URL (default: kubectl service proxy)")
    ap.add_argument("--critical-regressions", type=int, default=0, help="Verified critical security/audit/recovery regressions")
    ap.add_argument("--fixtures", help="Read DIR/tasks.json (and optional DIR/vm-tokens.json, DIR/meta.json) offline")
    ap.add_argument("--out", help="Write Markdown report to PATH in addition to stdout")
    args = ap.parse_args(argv)

    since = parse_ts(args.since) if args.since else None
    until = parse_ts(args.until) if args.until else None
    cluster = args.context
    maku_version = args.maku_version
    vm_tokens = None
    critical = args.critical_regressions

    if args.fixtures:
        root = pathlib.Path(args.fixtures)
        tasks_doc = json.loads((root / "tasks.json").read_text())
        tasks = tasks_doc.get("items", tasks_doc) if isinstance(tasks_doc, dict) else tasks_doc
        vm_path = root / "vm-tokens.json"
        if vm_path.exists():
            vm_tokens = json.loads(vm_path.read_text())
        meta_path = root / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            cluster = meta.get("cluster", cluster)
            maku_version = meta.get("maku_version", maku_version)
            critical += int(meta.get("critical_regressions", 0))
    else:
        tasks = _kubectl_tasks(args.context, args.namespace)

    window = f"{args.since or 'start'} to {args.until or 'now'}"
    result = summarize(tasks, vm_tokens=vm_tokens, since=since, until=until, critical_regressions=critical)
    report = render(result, cluster=cluster, maku_version=maku_version, window=window)
    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
