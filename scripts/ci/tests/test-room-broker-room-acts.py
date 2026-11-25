#!/usr/bin/env python3
# requires: python3 kustomize
"""The room's acts (Maku v0.54.0, phase G) and whole plans (phase H), in every copy of the broker's
config: each act is one the pinned release knows, `plan` only where the Factory offers plan-first,
`file` and `intake.wholePlans` only where the planner runs, and no Slack channel offers an act its
room refuses."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
KNOWN = {"answer", "retry", "split", "plan", "file", "stop"}  # Maku internal/config KnownRoomActs
DEFAULT = ["answer", "retry"]  # Maku internal/config DefaultRoomActs, when the key is unset
COPIES = {"base": "infrastructure/base/room-broker/config.yaml",
          "gcp-0": "infrastructure/gcp-0/room-broker/config.yaml",
          "aws-0": "infrastructure/aws-0/room-broker/config.yaml"}
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


out = subprocess.run(["kustomize", "build", str(ROOT / "tooling/base/agent-factory/resources")],
                     capture_output=True, text=True, check=True).stdout
factory = next(d for d in yaml.safe_load_all(out) if d and d["kind"] == "Factory")["spec"]
outcomes = factory.get("outcomes") or ["change"]
slack = yaml.safe_load((ROOT / "tooling/base/agent-factory/slack-app/config.yaml").read_text())
slack_acts = {a for c in (slack.get("channels") or {}).values() for a in c.get("intentActions") or []}

for cloud, rel in COPIES.items():
    human = (yaml.safe_load((ROOT / rel).read_text()) or {}).get("human") or {}
    acts = human.get("roomActs")
    effective = DEFAULT if acts is None else acts
    planner = ((human.get("intake") or {}).get("plan") or {}).get("enabled") is True
    check(f"{cloud}: every room act is one Maku knows", set(effective) <= KNOWN)
    check(f"{cloud}: no room act is listed twice", len(effective) == len(set(effective)))
    check(f"{cloud}: plan only where the Factory offers plan-first",
          "plan" not in effective or "plan-first" in outcomes)
    check(f"{cloud}: file only where the planner runs", "file" not in effective or planner)
    check(f"{cloud}: intake.wholePlans only where the planner runs",
          not (human.get("intake") or {}).get("wholePlans") or planner)
    if cloud == "gcp-0":
        check("gcp-0: every act is on for the live session",
              set(effective) == KNOWN)
        check("gcp-0: whole plans are on", (human.get("intake") or {}).get("wholePlans") is True)
        check("gcp-0: Slack offers no act the room refuses",
              not (slack_acts & KNOWN) - set(effective))

sys.exit(1 if fails else 0)
