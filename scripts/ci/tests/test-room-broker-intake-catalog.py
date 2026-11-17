#!/usr/bin/env python3
# requires: python3 kustomize
"""`human.intake.plan`: the planner's catalog wiring (workflows review WF12), and the Maku release
that has to decode the block before any cloud carries it.

`intake_plan` turns what a person asked into a `plan/v1`. Since WF12, the broker reads the served
public repositories and their workflows from the factory's `GET /v1/catalog` (`factoryURL`), so no
copy of `human.intake.plan` carries `classes` or `repositories`, and every enabled copy sets
`factoryURL`.
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
INTAKE_RELEASE = "v0.35.0"
PLAN_KEYS = {"enabled", "url", "model", "apiKeyFile", "deadline", "dailyPlans", "fallback", "reasoningEffort"}
REASONING_EFFORT = "low"
PLANNER_TOKEN = "/var/run/secrets/maku/model-gateway/planner"
ENABLED_IN = {"aws-0", "gcp-0"}
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def version(tag):
    return tuple(int(n) for n in tag.lstrip("v").split("-", 1)[0].split("."))


def build(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True)
    if out.returncode != 0:
        print(f"FAIL kustomize build {path}: {out.stderr.strip()[:400]}")
        sys.exit(1)
    return [d for d in yaml.safe_load_all(out.stdout) if d]


def broker_config(cloud):
    """The broker's config as its ConfigMap carries it, decoded."""
    cm = next(d for d in build(f"infrastructure/{cloud}/room-broker")
              if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("room-broker-config"))
    return yaml.safe_load(cm["data"]["config.yaml"])


def plan_block(cfg):
    return ((cfg.get("human") or {}).get("intake") or {}).get("plan") or {}


pinned = next(d for d in build("infrastructure/base/room-broker")
              if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "room-broker")
image = pinned["spec"]["values"]["broker"]["image"]
pin = image["tag"].split("@")[0]
check(re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", pin) is not None, f"helmrelease.yaml's image tag is a release or prerelease tag: {pin}")

# --- release charts and CRDs match; a validation image may be a signed prerelease -----------
chart_source = yaml.safe_load((ROOT / "infrastructure/base/room-broker/ocirepository.yaml").read_text())
chart_pin = f"v{chart_source['spec']['ref']['tag']}"
if "-pr" not in pin:
    check(chart_pin == pin,
          f"the maku chart's tag (infrastructure/base/room-broker/ocirepository.yaml) is {pin} without its v")
crd = (ROOT / "infrastructure/base/room-broker/crd-rooms.yaml").read_text().splitlines()[1]
check(f"maku {chart_pin}" in crd, f"crd-rooms.yaml's source comment names {chart_pin}")
schema = yaml.safe_load((ROOT / "infrastructure/base/room-broker/sqlinstance.yaml").read_text())
check("atlasSchema" not in schema["spec"], "the broker's migrate init container owns the schema ledger")

# --- the release gates the block, in both directions --------------------------------------
knows_intake = version(pin) >= version(INTAKE_RELEASE)
clouds = sorted(p.parent.parent.name for p in ROOT.glob("infrastructure/*/room-broker/config.yaml"))
check(len(clouds) >= 2 and "base" in clouds, f"the copies this gate reads: {clouds}")
blocks = {}
for cloud in clouds:
    cfg = broker_config(cloud)
    plan = plan_block(cfg)
    blocks[cloud] = plan
    if not knows_intake:
        check(not plan, f"{cloud}: human.intake must not precede {INTAKE_RELEASE}: the pinned {pin} "
                        f"refuses the key and the rollout would wedge (block found)")
        continue
    check(bool(plan), f"{cloud}: the pinned {pin} decodes human.intake, so every copy declares it")

if not knows_intake:
    for desc, ok in [(f"the pin {pin} is below {INTAKE_RELEASE}, so no copy carries the block",
                      all(not b for b in blocks.values()))]:
        check(ok, desc)
else:
    def but_switch(block):
        return {k: v for k, v in block.items() if k != "enabled"}
    for cloud in clouds:
        check(but_switch(blocks[cloud]) == but_switch(blocks.get("base") or {}),
              f"{cloud}: human.intake is base's copy, verbatim but for enabled")
    mounts = bool((pinned["spec"]["values"]["broker"].get("modelGateway") or {}).get("service"))

    for cloud in clouds:
        cfg = broker_config(cloud)
        plan = plan_block(cfg)
        human = cfg.get("human") or {}
        check("classes" not in plan and "repositories" not in plan,
              f"{cloud}: human.intake.plan carries neither classes nor repositories (WF12: read from /v1/catalog)")
        check(set(plan) == PLAN_KEYS,
              f"{cloud}: human.intake.plan's keys are {sorted(PLAN_KEYS)}, found {sorted(plan)}")
        check(plan.get("reasoningEffort") == REASONING_EFFORT,
              f"{cloud}: human.intake.plan.reasoningEffort is {REASONING_EFFORT!r}, found {plan.get('reasoningEffort')!r}")
        on = cloud in ENABLED_IN
        check(plan.get("enabled") is on,
              f"{cloud}: human.intake.plan.enabled is {str(on).lower()}: on only in {sorted(ENABLED_IN)}")
        if on:
            check(bool(cfg.get("factoryURL")),
                  f"{cloud}: human.intake.plan.enabled needs factoryURL to read GET /v1/catalog")
        check(plan.get("model") == "tier-frontier",
              f"{cloud}: human.intake.plan.model is tier-frontier, the one alias the gateway serves the planner")
        url = str(plan.get("url") or "")
        check(re.fullmatch(r"https?://[^/@\s]+(?:/[^/\s]+)*", url) is not None,
              f"{cloud}: human.intake.plan.url is an absolute http(s)://host URL with no userinfo: {url!r}")
        deadline = str(plan.get("deadline") or "")
        check(re.fullmatch(r"[1-9]\d*s", deadline) is not None and int(deadline.rstrip("s")) <= 20,
              f"{cloud}: human.intake.plan.deadline is above 0 and at most 20s, under /mcp's 25s bound")
        check(isinstance(plan.get("dailyPlans"), int) and plan["dailyPlans"] >= 1,
              f"{cloud}: human.intake.plan.dailyPlans is at least 1 per requester")
        check(plan.get("fallback") in ("off", "composer"),
              f"{cloud}: human.intake.plan.fallback is off or composer")
        check(mounts and plan.get("apiKeyFile") == PLANNER_TOKEN,
              f"{cloud}: human.intake.plan.apiKeyFile is the mounted planner token ({PLANNER_TOKEN})")

        access = human.get("access")
        check(isinstance(access, dict),
              f"{cloud}: human.access is declared: the planner's candidate set is its write check")
        if plan.get("enabled") is True:
            check((human.get("mcp") or {}).get("enabled") is True,
                  f"{cloud}: human.intake.plan.enabled needs human.mcp.enabled: both tools are on /mcp")

for problem in problems:
    print(f"  FAIL {problem}")
print(f"intake catalog: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
