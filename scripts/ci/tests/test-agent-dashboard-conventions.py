#!/usr/bin/env python3
# requires: python3
"""The agent dashboards' reading conventions, on the real tree. A panel must say what it shows and
must not paint a count red: Grafana's default thresholds are green with red at 80, so a bar of
tokens or runs turns red for being large. A stat or bar gauge therefore sets its colour (fixed, or
thresholds that mean something: a cap, a ratio), and a counter that has no series until its first
event reads 0, not No data."""
import json
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
DASHBOARDS = ROOT / "observability/base/agent-platform"
errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


def board(name):
    docs = [d for d in yaml.safe_load_all((DASHBOARDS / name).read_text()) if d and d.get("kind") == "GrafanaDashboard"]
    return json.loads(docs[0]["spec"]["json"].replace("$$", "$"))


def flat(b):
    for p in b.get("panels", []):
        yield p
        yield from p.get("panels", [])


def panels(file):
    return {p["title"]: p for p in flat(board(file))}


def check_colours():
    for path in sorted(DASHBOARDS.glob("grafana-dashboard*.yaml")):
        for p in flat(board(path.name)):
            if p.get("type") not in ("stat", "bargauge"):
                continue
            d = p.get("fieldConfig", {}).get("defaults", {})
            check("color" in d or "thresholds" in d,
                  f"{path.name}: {p['title']} is a {p['type']} on Grafana's default thresholds (red above 80)")
    ident = panels("grafana-dashboard-agent-identity.yaml")
    # A counter with no series until its first event reads 0.
    for title in ("Refusals", "Revocations", "Stopped at the ceiling", "Time waited"):
        check(ident[title]["fieldConfig"]["defaults"].get("noValue") == "0", f"{title} reads 0 when it has no series")


for run in (check_colours,):
    run()
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("PASS")
