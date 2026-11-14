#!/usr/bin/env python3
# requires: python3 kustomize helm
"""The room broker's config copies stay base's but for the session and Slack switches: gcp-0's copy
differs in webhooks, human.mcp, human.slackLink, human.intake and human.slackDecide alone, and aws-0's
in the same keys plus coordination (plan mode only). No copy declares suspend, which this platform
does not run (owner ruling Q10, R3). The broker's own RBAC (the maku chart's, as its postRenderer
leaves it) reads and deletes runs, never patches or updates one."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import room_broker_chart  # noqa: E402

checks = {}
for cloud in ("aws-0", "gcp-0"):
    try:
        chart_rules = [r for d in room_broker_chart.render(ROOT, cloud) if d["kind"] == "Role" for r in d["rules"]
                       if "agentruns" in r.get("resources", [])]
    except room_broker_chart.Unavailable as e:
        print(f"SKIP: {e}")
        sys.exit(77)
    checks[f"{cloud}: the broker's own RBAC reads and deletes runs, never patches or updates one"] = bool(chart_rules) and all(
        not {"patch", "update"} & set(r["verbs"]) for r in chart_rules)

config = yaml.safe_load((ROOT / "infrastructure/base/room-broker/config.yaml").read_text())
gcp = yaml.safe_load((ROOT / "infrastructure/gcp-0/room-broker/config.yaml").read_text())
checks["no copy declares suspend"] = all("suspend" not in c for c in (config, gcp))


def minus_switches(cfg):
    """The config without the keys a session may declare: webhooks, human.mcp, human.slackLink,
    human.intake and human.slackDecide."""
    out = {k: v for k, v in cfg.items() if k != "webhooks"}
    out["human"] = {k: v for k, v in out["human"].items()
                    if k not in ("mcp", "slackLink", "intake", "slackDecide")}
    return out


checks["gcp-0's broker config is base's but for webhooks, human.mcp, human.slackLink, human.intake and human.slackDecide"] = (
    minus_switches(gcp) == minus_switches(config))
checks["gcp-0's human.mcp stays enabled"] = (gcp["human"]["mcp"].get("enabled") is True)

aws_copy = ROOT / "infrastructure/aws-0/room-broker/config.yaml"
if aws_copy.is_file():  # the Slack App (runbook 22), the planner and the session switches (runbooks 19, 25)
    aws = yaml.safe_load(aws_copy.read_text())
    # Coordination (Maku #369-#371) is aws-0's alone and plan mode only: execute stays gated on repository
    # class authority, and the broker refuses any mode but off without the planner, which base keeps off.
    aws_coordination = aws.pop("coordination", None)
    checks["aws-0's coordination is plan mode, nothing more"] = aws_coordination == {"mode": "plan"}
    checks["base and gcp-0 declare no coordination"] = "coordination" not in config and "coordination" not in gcp
    checks["aws-0's broker config is base's but for webhooks, human.mcp, human.slackLink, human.intake, human.slackDecide and coordination"] = (
        "suspend" not in aws and minus_switches(aws) == minus_switches(config))
    checks["aws-0's human.mcp stays enabled"] = (aws["human"]["mcp"].get("enabled") is True)

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
