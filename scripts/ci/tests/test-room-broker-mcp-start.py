#!/usr/bin/env python3
# requires: python3 kustomize
"""`human.mcp.start` and the removals of the six-tools UX rollout: held to the Maku releases that
decode and refuse each key (`ux-review-design`, UX3, UX9).

`human.mcp.start` (`{default, except}`) replaces `human.mcp.sessionStart`:
  - below START_RELEASE, Maku's strict config decoder refuses `human.mcp.start`, so no copy may carry
    it before the pin reaches START_RELEASE;
  - at or above START_RELEASE, `human.mcp.sessionStart` is deprecated (and refused from REMOVAL_RELEASE),
    so every copy drops `sessionStart`; any copy carrying `human.mcp.start` holds only `default` and
    `except`, with every `except` entry `owner/name` and a repository the factory serves;
  - at or above REMOVAL_RELEASE, the Slack draft grammar and its `proposals` switch are removed from the
    Slack App's strict config, so no copy of the Slack App config carries `proposals`.

Both placeholders stay at v9.9.9 until each Maku release is cut; the commit that bumps the pin sets
the corresponding constant in lockstep, as INTAKE_RELEASE is set in test-room-broker-intake-classes.py.
"""
import pathlib
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config as factory_resources  # noqa: E402  the Factory, Repository and MergePolicy objects

# Release N (adds human.mcp.start, deprecates sessionStart) and release N+1 (refuses sessionStart and
# removes the Slack App's proposals switch). Bump each with the Maku pin in the same commit.
START_RELEASE = (0, 53, 0)
REMOVAL_RELEASE = (0, 53, 0)
START_KEYS = {"default", "except"}
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def version(tag):
    return tag if isinstance(tag, tuple) else tuple(int(n) for n in tag.lstrip("v").split("."))


def build(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True)
    if out.returncode != 0:
        print(f"FAIL: kustomize build {path}: {out.stderr.strip()[:400]}")
        sys.exit(1)
    return [d for d in yaml.safe_load_all(out.stdout) if d]


def broker_config(cloud):
    """The broker's config as its ConfigMap carries it, decoded."""
    cm = next(d for d in build(f"infrastructure/{cloud}/room-broker")
              if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("room-broker-config"))
    return yaml.safe_load(cm["data"]["config.yaml"])


def factory_config(cloud):
    """The factory's config as the chart receives it: every valuesFrom ConfigMap, the last winning."""
    docs = build(f"tooling/{cloud}/agent-factory")
    release = next(d for d in docs if d["kind"] == "HelmRelease"
                   and d["metadata"]["name"] == "agent-factory")
    cms = {d["metadata"]["name"]: d for d in docs if d["kind"] == "ConfigMap"}
    merged = {}
    for ref in release["spec"]["valuesFrom"]:
        values = yaml.safe_load(cms[ref["name"]]["data"]["values.yaml"]) or {}
        for key, value in (values.get("config") or {}).items():
            merged[key] = value if not isinstance(value, dict) else {**merged.get(key, {}), **value}
    return factory_resources.assemble(merged, factory_resources.objects(ROOT))


def slack_app_config(cloud):
    """The Slack App's config as its ConfigMap carries it, decoded."""
    cm = next(d for d in build(f"tooling/{cloud}/agent-factory/slack-app")
              if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("factory-slack-app-config"))
    return yaml.safe_load(cm["data"]["config.yaml"]) or {}


pinned = next(d for d in build("infrastructure/base/room-broker")
              if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "room-broker")
image = pinned["spec"]["values"]["broker"]["image"]
pin = image["tag"].split("@")[0]
check(re.fullmatch(r"v\d+\.\d+\.\d+", pin) is not None, f"helmrelease.yaml's image tag is a release tag: {pin}")
check(version(START_RELEASE) <= version(REMOVAL_RELEASE),
      f"START_RELEASE {START_RELEASE} must not exceed REMOVAL_RELEASE {REMOVAL_RELEASE}")

knows_start = version(pin) >= version(START_RELEASE)
knows_removal = version(pin) >= version(REMOVAL_RELEASE)

clouds = sorted(p.parent.parent.name for p in ROOT.glob("infrastructure/*/room-broker/config.yaml"))
check(set(clouds) == {"base", "aws-0", "gcp-0"}, f"the broker copies this gate reads: {clouds}")

for cloud in clouds:
    cfg = broker_config(cloud)
    human = cfg.get("human") or {}
    mcp = human.get("mcp") or {}
    if not knows_start:
        check("start" not in mcp,
              f"{cloud}: human.mcp.start must not precede {START_RELEASE}: the pinned {pin} refuses "
              f"the key and the rollout would wedge")
        continue

    check("sessionStart" not in mcp,
          f"{cloud}: human.mcp.sessionStart must be removed at or above {START_RELEASE} (pinned {pin})")
    if "start" not in mcp:
        continue

    start = mcp["start"]
    check(isinstance(start, dict) and set(start) <= START_KEYS,
          f"{cloud}: human.mcp.start may hold only {sorted(START_KEYS)}, "
          f"found {sorted(start) if isinstance(start, dict) else start!r}")
    if not isinstance(start, dict):
        continue
    check(mcp.get("enabled") is True, f"{cloud}: human.mcp.start needs human.mcp.enabled")
    check(isinstance(human.get("access"), dict), f"{cloud}: human.mcp.start needs human.access")
    if "default" in start:
        check(isinstance(start["default"], bool),
              f"{cloud}: human.mcp.start.default must be a boolean, found {start['default']!r}")
    if "except" in start:
        exc = start["except"]
        check(isinstance(exc, list) and all(isinstance(r, str) for r in exc),
              f"{cloud}: human.mcp.start.except must be a list of strings, found {exc!r}")
        if isinstance(exc, list) and all(isinstance(r, str) for r in exc):
            served = [r["name"] for r in factory_config(cloud).get("repositories") or []]
            served_lower = {r.lower() for r in served}
            seen = set()
            for r in exc:
                check(REPO_RE.fullmatch(r) is not None,
                      f"{cloud}: human.mcp.start.except: {r!r} is not owner/name")
                check(r.lower() not in seen,
                      f"{cloud}: human.mcp.start.except: {r!r} is listed twice")
                seen.add(r.lower())
                check(r.lower() in served_lower,
                      f"{cloud}: human.mcp.start.except: {r} is not a repository the factory serves "
                      f"({', '.join(served)})")

if knows_removal:
    slack_clouds = sorted(
        p.parent.parent.parent.name for p in ROOT.glob("tooling/*/agent-factory/slack-app/kustomization.yaml")
    )
    check(set(slack_clouds) == {"base", "aws-0", "gcp-0"}, f"the Slack App copies this gate reads: {slack_clouds}")
    for sc in slack_clouds:
        app_cfg = slack_app_config(sc)
        check("proposals" not in app_cfg,
              f"{sc}: Slack App config carries proposals at or above {REMOVAL_RELEASE} (pinned {pin})")

for problem in problems:
    print(f"FAIL: {problem}")
print(f"room-broker mcp.start: pin {pin} (start>={START_RELEASE}, removal>={REMOVAL_RELEASE}), {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
