#!/usr/bin/env python3
"""Compares one UTC day's factory ledger with the cost agentgateway priced, per run (cost cross-check XC3, XC4).

  python3 scripts/ops/cost-crosscheck.py --day YYYYMMDD [--namespace agent-system] [--vm-url URL]

Ledger side: ConfigMap agent-factory-ledger-usd-<day>, read with kubectl: each `settled.<runId>` is the
micro-USD the factory charged to that run that day. Gateway side: VictoriaMetrics' query API (through the
API server's service proxy, or --vm-url directly): the increase over the day of
agentgateway_gen_ai_client_cost_usd_total by run, the gateway's own price of every response from the
agent-model-catalog overlay. A run with a token series outside agentgateway (Envoy prices nothing) is
left out and listed (XC7).

Agreement, XC4: abs(ledger - gateway) <= max(1% x gateway, floor); the floor is $0.01 per run and
$0.10 for the day's total. Exit 0 all within, 1 one run or the total outside, 2 a source unreadable.
The day's total is compared on the ledger's `spent` column (XC3), less the settled entries of the runs left
out; the sum of the `settled.<run>` entries is printed beside it, and a gap between the two is said so, never
failed on. `spent` per principal is printed for reference: the gateway has no principal label.
Exit 2 also for a VictoriaMetrics body that is not a success or a value that is NaN or infinite.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

REL = Decimal("0.01")
RUN_FLOOR = Decimal("0.01")
DAY_FLOOR = Decimal("0.10")
RUN_AGENT = r"system:serviceaccount:agents:xplane-run-.+"
RUN_ID = re.compile(r".*xplane-run-(.+)$")
VM_PROXY = "/api/v1/namespaces/observability/services/vmsingle-victoria-metrics-k8s-stack:8428/proxy"
MICRO = Decimal(1_000_000)


def within(ledger, gateway, floor):
    """XC4: the two numbers agree to 1% of the gateway's, or to the floor."""
    return abs(ledger - gateway) <= max(REL * gateway, floor)


def parse_ledger(cm):
    """({run id: USD settled}, {principal: USD spent}) from the day ledger ConfigMap's JSON."""
    data = cm.get("data") or {}
    settled = {k[len("settled."):]: Decimal(v) / MICRO for k, v in data.items() if k.startswith("settled.")}
    spent = {p: Decimal(v) / MICRO for p, v in json.loads(data.get("spent") or "{}").items()}
    return settled, spent


def by_run(vm):
    """{run id: Decimal} from a VM instant-query result of series labelled ar_agent; values are USD or counts."""
    if vm.get("status") != "success":
        raise ValueError(f"VictoriaMetrics did not answer success: {vm.get('error') or vm.get('status')}")
    out = {}
    for s in (vm.get("data") or {}).get("result") or []:
        m = RUN_ID.match(s["metric"].get("ar_agent", ""))
        if m:
            try:
                v = Decimal(str(s["value"][1]))
            except InvalidOperation:
                v = Decimal("NaN")
            if not v.is_finite():
                raise ValueError(f"VictoriaMetrics value {s['value'][1]!r} for run {m.group(1)} is not a number")
            out[m.group(1)] = out.get(m.group(1), Decimal(0)) + v
    return out


def compare(ledger, gateway, skipped=(), spent_total=None):
    """(rows, total, ok): rows [(run, ledger, gateway, within run floor)] over the union of both sides, minus
    the skipped runs; total (ledger, gateway, within the day's floor); ok when every row and the total agree.
    A run on one side only is compared against 0. With spent_total (the day's spent column less the skipped
    runs' settled), the total's ledger side is that, not the sum of the rows."""
    runs = sorted((set(ledger) | set(gateway)) - set(skipped))
    rows = [(r, ledger.get(r, Decimal(0)), gateway.get(r, Decimal(0)),
             within(ledger.get(r, Decimal(0)), gateway.get(r, Decimal(0)), RUN_FLOOR)) for r in runs]
    lt, gt = sum((r[1] for r in rows), Decimal(0)), sum((r[2] for r in rows), Decimal(0))
    if spent_total is not None:
        lt = spent_total
    total = (lt, gt, within(lt, gt, DAY_FLOOR))
    return rows, total, total[2] and all(r[3] for r in rows)


def render(day, rows, total, skipped, spent, settled_sum=None):
    usd = lambda d: f"{d:.6f}"
    lines = [f"cost cross-check {day} (USD; ledger = settled.<run> per run and spent for the TOTAL, gateway = priced by agentgateway)",
             f"{'run':<28}{'ledger':>12}{'gateway':>12}{'diff':>12}  ok"]
    for run, l, g, ok in rows:
        lines.append(f"{run:<28}{usd(l):>12}{usd(g):>12}{usd(l - g):>12}  {'yes' if ok else 'NO'}")
    l, g, ok = total
    lines.append(f"{'TOTAL':<28}{usd(l):>12}{usd(g):>12}{usd(l - g):>12}  {'yes' if ok else 'NO'}")
    if settled_sum is not None:
        lines.append(f"settled sum (reference): {usd(settled_sum)}")
        if not within(settled_sum, l, DAY_FLOOR):
            lines.append(f"spent and the settled sum disagree: {usd(l)} against {usd(settled_sum)} "
                         "(the verdict is on spent; look at the ledger writes, AP#166 and AP#167)")
    if skipped:
        lines.append(f"left out, a token series outside agentgateway (XC7): {', '.join(sorted(skipped))}")
    if spent:
        lines.append("ledger spent per principal (reference): " + ", ".join(f"{p} {usd(v)}" for p, v in sorted(spent.items())))
    return "\n".join(lines)


def window(day, now):
    """(end of the day or now, seconds from the day's start to it)."""
    start = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
    end = min(start + timedelta(days=1), now)
    if end <= start:
        raise ValueError(f"{day} has not started")
    return end, max(int((end - start).total_seconds()), 1)


def kubectl_json(*args):
    return json.loads(subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True).stdout)


def query(promql, at, vm_url):
    qs = urllib.parse.urlencode({"query": promql, "time": int(at.timestamp())})
    if vm_url:
        with urllib.request.urlopen(f"{vm_url.rstrip('/')}/api/v1/query?{qs}", timeout=30) as r:
            return json.load(r)
    return kubectl_json("get", "--raw", f"{VM_PROXY}/api/v1/query?{qs}")


def run(day, namespace, vm_url, now, fetch_ledger=None, fetch_query=None):
    fetch_ledger = fetch_ledger or (lambda: kubectl_json("get", "cm", "-n", namespace, f"agent-factory-ledger-usd-{day}", "-o", "json"))
    fetch_query = fetch_query or (lambda q, at: query(q, at, vm_url))
    end, secs = window(day, now)
    ledger, spent = parse_ledger(fetch_ledger())
    gateway = by_run(fetch_query(
        f'sum by (ar_agent) (increase_pure(agentgateway_gen_ai_client_cost_usd_total{{ar_agent=~"{RUN_AGENT}"}}[{secs}s]))', end))
    envoy = by_run(fetch_query(
        f'sum by (ar_agent) (increase_pure(gen_ai_client_token_usage_sum{{ar_agent=~"{RUN_AGENT}", namespace!="agent-gateway"}}[{secs}s])) > 0', end))
    skipped = sorted(envoy)
    spent_total = sum(spent.values(), Decimal(0)) - sum((ledger.get(r, Decimal(0)) for r in skipped), Decimal(0))
    rows, total, ok = compare(ledger, gateway, skipped, spent_total)
    settled_sum = sum((r[1] for r in rows), Decimal(0))
    return render(day, rows, total, skipped, spent, settled_sum), ok


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--day", required=True, help="UTC day, YYYYMMDD")
    p.add_argument("--namespace", default="agent-system")
    p.add_argument("--vm-url", help="VictoriaMetrics base URL; default: through the API server's service proxy")
    a = p.parse_args(argv[1:])
    if not re.fullmatch(r"\d{8}", a.day):
        p.error("--day is YYYYMMDD")
    try:
        text, ok = run(a.day, a.namespace, a.vm_url, datetime.now(timezone.utc))
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError, ArithmeticError) as e:
        print(f"cost-crosscheck: {e}", file=sys.stderr)
        return 2
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
