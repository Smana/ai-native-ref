#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ops/cost-crosscheck.py (cost cross-check design, offline proof 3): agreement, a 2% gap,
the $0.10 day floor and the $0.01 run floor, a run on one side only, an Envoy run left out, and main()
end to end with the ledger and VictoriaMetrics answered from fixtures.

Run: python3 scripts/ci/tests/test-cost-crosscheck.py
"""
import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal as D

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIX = ROOT / "scripts/ci/tests/cost-crosscheck-fixtures"
spec = importlib.util.spec_from_file_location("cost_crosscheck", ROOT / "scripts/ops/cost-crosscheck.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

fails = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok or not detail else ' -- ' + str(detail)}")
    if not ok:
        fails.append(name)


ledger_cm = json.loads((FIX / "ledger.json").read_text())
vm_gateway = json.loads((FIX / "vm-gateway.json").read_text())
vm_envoy = json.loads((FIX / "vm-envoy.json").read_text())
NOW = datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)

print("parsing")
settled, spent = cc.parse_ledger(ledger_cm)
check("settled.<run> micro-USD become USD per run", settled == {"aaa": D("0.5"), "bbb": D("0.2"), "ccc": D("1")}, settled)
check("spent per principal in USD", spent == {"system:factory": D("1.4"), "github:smana": D("0.3")}, spent)
gw = cc.by_run(vm_gateway)
check("the gateway's series are keyed by the run id in ar_agent", gw == {"aaa": D("0.5"), "bbb": D("0.195")}, gw)

print("agreement (XC4)")
rows, total, ok = cc.compare({"a": D("10.00"), "b": D("5.00")}, {"a": D("10.00"), "b": D("5.00")})
check("equal ledger and gateway agree", ok and total[:2] == (D("15"), D("15")), (rows, total))
rows, total, ok = cc.compare({"a": D("10.00")}, {"a": D("10.10")})
check("a 1% gap or less agrees (0.99% of the gateway)", ok, (rows, total))
rows, total, ok = cc.compare({"a": D("10.00")}, {"a": D("10.20")})
check("a 2% gap on a $10 run fails the run and the day", not ok and not rows[0][3] and not total[2], (rows, total))
rows, total, ok = cc.compare({"a": D("0.20")}, {"a": D("0.205")})
check("a $0.005 gap on a $0.20 run is inside the $0.01 run floor", ok and rows[0][3], (rows, total))
rows, total, ok = cc.compare({"a": D("0.20")}, {"a": D("0.22")})
check("a $0.02 gap on a $0.20 run is outside the run floor, and the day's $0.10 floor absorbs it",
      not rows[0][3] and total[2] and not ok, (rows, total))
rows, total, ok = cc.compare({"a": D("1.00")}, {"a": D("1.15")})
check("a $0.15 gap on a $1.00 day is outside the $0.10 day floor", not total[2], total)
rows, total, ok = cc.compare({"a": D("0.50")}, {"a": D("0.50"), "b": D("0.30")})
check("a run the gateway priced and the ledger never saw fails, against 0",
      not ok and [r[0] for r in rows] == ["a", "b"] and rows[1][1] == 0 and not rows[1][3], rows)
rows, total, ok = cc.compare({"a": D("0.50"), "z": D("0.30")}, {"a": D("0.50")})
check("a run only the ledger holds fails too", not ok and not rows[1][3], rows)
rows, total, ok = cc.compare({"a": D("0.50"), "z": D("0.30")}, {"a": D("0.50")}, skipped=["z"])
check("a skipped (Envoy) run is left out of the rows and the total", ok and [r[0] for r in rows] == ["a"] and total[0] == D("0.5"), rows)

print("main, from fixtures")


def answer(query, at):
    return vm_envoy if "namespace!=" in query else vm_gateway


def go(cm=ledger_cm, fetch=answer):
    return cc.run("20261027", "agent-system", None, NOW, fetch_ledger=lambda: cm, fetch_query=fetch)


text, ok = go()
check("the fixture day agrees: aaa exact, bbb $0.005 off, ccc (Envoy) left out", ok and "ccc" in text.split("left out")[1], text)
check("the table lists the run ids, the total and the principals' spent",
      all(s in text for s in ("aaa", "bbb", "TOTAL", "github:smana 0.300000")), text)
cm = copy.deepcopy(ledger_cm)
cm["data"]["settled.aaa"] = "510000"
text, ok = go(cm)
check("a ledger run $0.01 over a $0.50 run is inside the run floor", ok, text)
cm["data"]["settled.aaa"] = "600000"
text, ok = go(cm)
check("a ledger $0.10 over on a $0.50 run fails, the row marked NO", not ok and "NO" in text, text)
queries = []
go(fetch=lambda q, at: (queries.append((q, at)), answer(q, at))[1])
check("the cost query is the increase over the whole UTC day at the day's end",
      "increase_pure(agentgateway_gen_ai_client_cost_usd_total" in queries[0][0] and "[86400s]" in queries[0][0]
      and queries[0][1] == datetime(2026, 10, 28, tzinfo=timezone.utc), queries[0])
check("the Envoy query reads token series outside namespace agent-gateway", 'namespace!="agent-gateway"' in queries[1][0], queries[1])
partial = cc.window("20261028", NOW)
check("today's window ends now", partial == (NOW, 6 * 3600), partial)

print("the day total is the ledger's spent column (XC3)")
text, ok = go()
check("the fixture day agrees on spent minus the Envoy run's settled (1.7 - 1.0) against the gateway's 0.695",
      ok and any(l.startswith("TOTAL") and "0.700000" in l for l in text.splitlines()), text)
check("the settled sum is printed as a cross-reference, with no disagreement note when it agrees",
      "settled sum" in text and "disagree" not in text, text)
cm = copy.deepcopy(ledger_cm)
cm["data"]["spent"] = json.dumps({"system:factory": "2400000", "github:smana": "300000"})
text, ok = go(cm)
check("a spent column $1.00 over the settled entries fails the day against the gateway", not ok, text)
cm = copy.deepcopy(ledger_cm)
cm["data"]["settled.bbb"] = "50000"
cm["data"]["spent"] = json.dumps({"system:factory": "1400000", "github:smana": "300000"})
text, ok = go(cm)
check("spent and settled apart: both printed and said so, the verdict stays on spent and the gateway",
      "disagree" in text and "spent" in text, text)

print("cannot tell (exit 2), no traceback")


def vm_body(value=None, status="success"):
    body = {"status": status, "data": {"resultType": "vector", "result": []}}
    if value is not None:
        body["data"]["result"] = [{"metric": {"ar_agent": "system:serviceaccount:agents:xplane-run-aaa"}, "value": [1, value]}]
    if status != "success":
        body = {"status": status, "errorType": "bad_data", "error": "boom"}
    return body


def main_with(ledger=lambda *a: ledger_cm, vm=lambda q, at, u: vm_gateway):
    saved = cc.kubectl_json, cc.query
    cc.kubectl_json, cc.query = ledger, vm
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cc.main(["cost-crosscheck.py", "--day", "20261027"])
    except Exception as e:  # a traceback is the failure
        return f"raised {type(e).__name__}: {e}", err.getvalue()
    finally:
        cc.kubectl_json, cc.query = saved
    return code, err.getvalue()


for bad in ("NaN", "+Inf", "-Inf"):
    code, err = main_with(vm=lambda q, at, u, bad=bad: vm_body(bad))
    check(f"a VM value {bad} exits 2 with a message", code == 2 and "cost-crosscheck" in err, (code, err))
code, err = main_with(vm=lambda q, at, u: vm_body(status="error"))
check("a non-success VM body exits 2 with a message", code == 2 and "cost-crosscheck" in err, (code, err))

print("empty sides")


def gone(*a):
    raise subprocess.CalledProcessError(1, "kubectl", stderr="not found")


code, err = main_with(ledger=gone)
check("an empty day (no ledger ConfigMap) exits 2 with a message", code == 2 and "cost-crosscheck" in err, (code, err))
empty = {"kind": "ConfigMap", "metadata": {"name": "x"}, "data": {}}
text, ok = go(empty, lambda q, at: vm_body())
check("an existing ledger with nothing settled and no gateway series is agreement at zero", ok and "TOTAL" in text, text)
text, ok = go(ledger_cm, lambda q, at: vm_body())
check("ledger spend with an empty VM result fails, every run priced at 0 by the gateway",
      not ok and text.count("NO") >= 2, text)

print("the command line")
try:
    with contextlib.redirect_stderr(io.StringIO()):
        cc.main(["cost-crosscheck.py", "--day", "yesterday"])
    check("a bad --day is refused", False)
except SystemExit as e:
    check("a bad --day is refused with usage (exit 2)", e.code == 2)

if fails:
    print(f"\n{len(fails)} failure(s)")
    sys.exit(1)
print("\nall passed")
