#!/usr/bin/env python3
# requires: python3
"""scripts/ops/kb-measures.py (K6): human touches per incident and the knowledge queue, from GitHub's records.

Fixtures: two RunLore stubs (the first published and merged by the owner, the second merged by the
factory's merger App), a follow-up the monitor filed and a stub from another source (neither is an
incident), and three knowledge-base PRs of which one is merged and two are open."""
import contextlib
import importlib.util
import io
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
# The queue is read at the end of the window whenever its PRs were opened: a backlog PR from before the window
# is open at the end, and one merged after the end still is.
from datetime import datetime, timezone
utc = lambda d: datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
backlog = [{"number": 9, "created_at": "2026-08-01T00:00:00Z", "closed_at": None, "merged_at": None, "merged_by": None},
           {"number": 8, "created_at": "2026-08-01T00:00:00Z", "closed_at": "2026-11-20T00:00:00Z", "merged_at": "2026-11-20T00:00:00Z"}]
w = kb.measures(load("stubs"), load("events"), load("kb-prs") + backlog, since=utc("2026-10-20"), until=utc("2026-11-01"))
check("the window counts only its own opened PRs", w["kb_opened"] == 3 and w["kb_merged"] == 1)
check("the queue counts the backlog open at the end, whenever it was opened", w["kb_open_end"] == 4)
check("the oldest open is the backlog's", w["oldest_open_days"] > 90)
table = kb.render(m)
check("one Markdown table", table.count("\n| ") >= 7 and table.startswith("| "))
check("--fixtures reads a directory", kb.main(["--since", "2026-11-01", "--fixtures", str(FIX)]) == 0)


def usage_error(name, args, *needles):
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            kb.main(args)
    except SystemExit as e:
        check(name, e.code == 2 and all(n in err.getvalue() for n in needles)
              and "Traceback" not in err.getvalue())
        return
    check(name, False)


usage_error("a --since that is not a real date is a usage error",
            ["--since", "2026-13-01", "--fixtures", str(FIX)], "--since", "YYYY-MM-DD")
usage_error("an --until that is not a real date is a usage error",
            ["--since", "2026-11-01", "--until", "2026-02-30", "--fixtures", str(FIX)], "--until", "YYYY-MM-DD")
usage_error("an --until before --since is a usage error",
            ["--since", "2026-11-10", "--until", "2026-11-01", "--fixtures", str(FIX)],
            "--until must be after --since")
usage_error("an --until equal to --since is a usage error",
            ["--since", "2026-11-10", "--until", "2026-11-10", "--fixtures", str(FIX)],
            "--until must be after --since")
valid = io.StringIO()
with contextlib.redirect_stdout(valid):
    code = kb.main(["--since", "2026-11-10", "--until", "2026-11-20", "--fixtures", str(FIX)])
check("a valid call still prints its table", code == 0 and valid.getvalue().startswith("| Measure | Value |"))

tbl_out, json_out = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(tbl_out):
    tbl_code = kb.main(["--since", "2026-10-20", "--until", "2026-11-01", "--fixtures", str(FIX)])
with contextlib.redirect_stdout(json_out):
    json_code = kb.main(["--since", "2026-10-20", "--until", "2026-11-01", "--fixtures", str(FIX), "--json"])
doc = json.loads(json_out.getvalue())
tbl_rows = dict(line.strip("| ").split(" | ") for line in tbl_out.getvalue().splitlines()[2:])
expected_keys = ("incidents", "touches", "kb_opened", "kb_merged", "kb_closed", "kb_open_end", "oldest_open_days")
check("--json prints one indented JSON document with the table's keys",
      tbl_code == 0 and json_code == 0
      and tuple(doc.keys()) == expected_keys
      and tuple(doc["touches"].keys()) == ("median", "max")
      and json_out.getvalue() == json.dumps(doc, indent=2) + "\n")
check("--json values equal the table's for the same fixtures",
      [str(v) for v in (doc["incidents"], doc["touches"]["median"], doc["touches"]["max"],
                        doc["kb_opened"], doc["kb_merged"], doc["kb_closed"],
                        doc["kb_open_end"], doc["oldest_open_days"])]
      == [tbl_rows[k] for k in ("Incidents", "Human touches per incident, median",
                                "Human touches per incident, max", "KB PRs opened",
                                "KB PRs merged", "KB PRs closed unmerged",
                                "KB PRs open at the end (any age)", "Oldest open KB PR (days)")])
empty = kb.measures([], {}, [])
empty_doc = json.loads(kb.render_json(empty))
check("--json emits null where the table prints -",
      empty_doc["touches"] == {"median": None, "max": None}
      and empty_doc["oldest_open_days"] is None
      and "| - |" in kb.render(empty))
check("the module docstring usage line names [--json]", "[--json]" in kb.__doc__.splitlines()[2])
if failures:
    sys.exit(1)
print("PASS: kb-measures")
