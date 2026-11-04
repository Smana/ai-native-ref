#!/usr/bin/env python3
# requires: python3
"""scripts/ops/kb-measures.py (K6): human touches per incident and the knowledge queue, from GitHub's records.

Fixtures: two RunLore stubs (the first published and merged by the owner, the second merged by the
factory's merger App), a follow-up the monitor filed and a stub from another source (neither is an
incident), and three knowledge-base PRs of which one is merged and two are open."""
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIX = pathlib.Path(__file__).resolve().parent / "kb-measures-fixtures"
try:
    spec = importlib.util.spec_from_file_location("kb", ROOT / "scripts/ops/kb-measures.py")
    kb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kb)
except FileNotFoundError:
    print("No module named kb-measures")
    sys.exit(1)

failures = []


def check(name, ok):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        failures.append(name)


load = lambda n: json.loads((FIX / f"{n}.json").read_text())
m = kb.measures(load("stubs"), load("events"), load("kb-prs"))
check("touches per incident", m["touches"] == {"median": 1.5, "max": 2})
check("a bot's label is not a touch", m["touches_by_incident"]["#2"] == 1)
check("kb counts", (m["kb_opened"], m["kb_merged"], m["kb_open_end"]) == (3, 1, 2))
check("a follow-up and a foreign stub are not incidents", m["incidents"] == 2)
check("closed unmerged is its own count", m["kb_closed"] == 0)
check("the oldest open PR's age is in days", m["oldest_open_days"] is not None and m["oldest_open_days"] >= 0)
table = kb.render(m)
check("one Markdown table", table.count("\n| ") >= 7 and table.startswith("| "))
check("--fixtures reads a directory", kb.main(["--since", "2026-11-01", "--fixtures", str(FIX)]) == 0)
if failures:
    sys.exit(1)
print("PASS: kb-measures")
