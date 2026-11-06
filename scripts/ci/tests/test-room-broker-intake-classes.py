#!/usr/bin/env python3
# requires: python3 kustomize
"""`human.intake.plan`: the allowlist and the class table behind the planner's two tools, and the
maku release that has to decode the block before any cloud carries it.

`intake_plan` turns what a person asked into a `plan/v1`: one repository, one to three issues, each
with its class, the roles the broker derives from that class and the ceiling the plan is charged
against, and the one question it must ask first. None of those is the model's to choose (CD17): the
class table names every class a plan may carry, its roles and its money, and the allowlist is the
whole world the candidate set is drawn from (CD5). Both are config, so a value naming a class the
factory does not have, a role it does not run, a repository it does not serve or money above the
tier's is a plan nothing can run — refused here, offline, instead of by the first plan of a session.

The release comes first, and both ends of that order are held here. `human.intake` is unknown to
maku's strict decoder before the release that adds it, so a block written early fails the broker's
rollout (`test-maku-config-load.sh` loads every copy through the tag `app.yaml` pins and says so).
Below INTAKE_RELEASE the block must therefore be absent everywhere and the pin must be below it; at
or above it the block must be present in every copy. Whoever cuts that release bumps the pin and
INTAKE_RELEASE in the same commit, and writes the block in that commit too.

The factory's side is read the way the factory reads it: the ConfigMaps its HelmRelease lists, in
order, the last one winning.
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
# The first maku release whose internal/config knows human.intake. Bump it with the pin: the block
# may not exist on a broker older than this tag, and must exist on one at or above it.
INTAKE_RELEASE = "v0.35.0"
# The one public repository the proof plans for (CD5): a class table may be written for it even on a
# cloud whose factory does not serve it yet.
PUBLIC_REPO = "Smana/ai-native-ref"
# The tier every task takes when triage names none (the factory's own comment on `triage`): a ceiling
# above its taskUSD is money the factory does not have.
DEFAULT_TIER = "standard"
# The roles a loop adds beside the templates': a scoper runs where a class's row sets `scope: scoper`,
# a tester where it sets testFirst. Both are runs the factory makes, so a plan may name them.
EXTRA_ROLES = {"scoper", "tester"}
PLAN_KEYS = {"enabled", "url", "model", "apiKeyFile", "deadline", "dailyPlans", "fallback",
             "repositories", "classes"}
CLASS_KEYS = {"roles", "ceilingUSD", "source"}
PLANNER_MOUNT = "/etc/room-broker/planner"
# The copies whose switch is on (ADR-0060): one cloud, for the one public repository. Every other copy,
# base's included, keeps it off.
ENABLED_IN = {"gcp-0"}
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def version(tag):
    return tuple(int(n) for n in tag.lstrip("v").split("."))


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
    return merged


def plan_block(cfg):
    return ((cfg.get("human") or {}).get("intake") or {}).get("plan") or {}


def served(repo):
    """A repository the factory serves: its name, and its classes with their rows."""
    return {name: cols for name, cols in (((repo or {}).get("classes")) or {}).items()}


pinned = next(d for d in build("infrastructure/base/room-broker")
              if d["kind"] == "App" and d["metadata"]["name"] == "room-broker")
pin = pinned["spec"]["image"]["tag"].split("@")[0]
check(re.fullmatch(r"v\d+\.\d+\.\d+", pin) is not None, f"app.yaml's tag is a release tag: {pin}")

# --- the pin is one release, in the four places that name it ------------------------------
# A half-bump is the failure this guards: the Deployment on one release, the retention CronJob, the
# CRDs and the schema on another, and nothing offline noticing.
digest = pinned["spec"]["image"]["tag"].split("@")[-1]
cronjob = next(d for d in build("infrastructure/base/room-broker")
               if d["kind"] == "CronJob")
cron_image = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"]
check(cron_image == f"ghcr.io/smana/maku-broker:{pin}@{digest}",
      "the retention CronJob runs the same release and digest as app.yaml")
crd = (ROOT / "infrastructure/base/room-broker/crd-rooms.yaml").read_text().splitlines()[1]
check(f"maku {pin}" in crd, f"crd-rooms.yaml's source comment names {pin}")
schema = yaml.safe_load((ROOT / "infrastructure/base/room-broker/sqlinstance.yaml").read_text())
check(schema["spec"]["atlasSchema"]["ref"] == pin, f"atlasSchema.ref is {pin}")

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
    # --- one block, every copy ----------------------------------------------------------------
    # A cloud that grew its own reading of the planner's block has a second planner, not a copy. The
    # switch is the one key a copy may set apart.
    def but_switch(block):
        return {k: v for k, v in block.items() if k != "enabled"}
    for cloud in clouds:
        check(but_switch(blocks[cloud]) == but_switch(blocks.get("base") or {}),
              f"{cloud}: human.intake is base's copy, verbatim but for enabled")
    # The key A1 mounted, not a path a block invents: a planner reading elsewhere 401s every plan.
    mounts = [m for m in pinned["spec"].get("extraVolumeMounts") or [] if m.get("mountPath") == PLANNER_MOUNT]

    # --- the allowlist and the class table, against the factory that has to run them ----------
    for cloud in clouds:
        cfg = broker_config(cloud)
        plan = plan_block(cfg)
        human = cfg.get("human") or {}
        factory = factory_config(cloud)
        repos = factory.get("repositories") or []
        names = [r["name"] for r in repos]
        classes = {}
        for repo in repos:
            for name, row in served(repo).items():
                classes[name] = row
        roles = set(EXTRA_ROLES)
        for template in (factory.get("templates") or {}).values():
            roles.update(template.get("roles") or [])
        task_usd = ((factory.get("tiers") or {}).get(DEFAULT_TIER) or {}).get("taskUSD")
        check(isinstance(task_usd, (int, float)) and task_usd > 0,
              f"{cloud}: the factory config has tiers.{DEFAULT_TIER}.taskUSD")

        # The block's own shape, as maku's decoder reads it: a typo here is a rollout that fails (or,
        # worse, a value the decoder defaults away and nobody notices).
        check(set(plan) == PLAN_KEYS,
              f"{cloud}: human.intake.plan's keys are {sorted(PLAN_KEYS)}, found {sorted(plan)}")
        # On in one cloud, for one public repository (ADR-0060); off everywhere else. A second cloud or
        # a second repository is its own decision, not a copy of this one.
        on = cloud in ENABLED_IN
        check(plan.get("enabled") is on,
              f"{cloud}: human.intake.plan.enabled is {str(on).lower()}: on only in {sorted(ENABLED_IN)}")
        if on:
            check(plan.get("repositories") == [PUBLIC_REPO],
                  f"{cloud}: the planner is on for {PUBLIC_REPO} alone, found {plan.get('repositories')}")
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
        check(mounts and plan.get("apiKeyFile") == f"{PLANNER_MOUNT}/api-key",
              f"{cloud}: human.intake.plan.apiKeyFile is the mounted planner key ({PLANNER_MOUNT}/api-key)")

        for repo in plan.get("repositories") or []:
            check(re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", repo) is not None,
                  f"{cloud}: human.intake.plan.repositories: {repo!r} is not owner/name")
            check(repo in names or repo.lower() == PUBLIC_REPO.lower(),
                  f"{cloud}: {repo} is neither a repository the factory serves ({', '.join(names)}) "
                  f"nor the public repository the proof uses")
        for name, row in (plan.get("classes") or {}).items():
            at = f"{cloud}: human.intake.plan.classes[{name!r}]"
            check(name in classes, f"{at} is not a class of a repository the factory serves "
                                   f"({', '.join(sorted(classes))})")
            check(isinstance(row, dict) and set(row) == CLASS_KEYS,
                  f"{at}'s keys are {sorted(CLASS_KEYS)}, found {sorted(row) if isinstance(row, dict) else row}")
            if not isinstance(row, dict):
                continue
            check(bool(row.get("roles")), f"{at}.roles is empty: a plan's roles are its class's")
            check(len(set(row.get("roles") or [])) == len(row.get("roles") or []),
                  f"{at}.roles declares no role twice")
            for role in row.get("roles") or []:
                check(role in roles, f"{at}.roles: {role!r} is not a role this factory runs "
                                     f"({', '.join(sorted(roles))})")
            ceiling = row.get("ceilingUSD")
            check(isinstance(ceiling, (int, float)) and ceiling > 0,
                  f"{at}.ceilingUSD is money, above zero")
            if isinstance(ceiling, (int, float)) and isinstance(task_usd, (int, float)):
                check(ceiling <= task_usd,
                      f"{at}.ceilingUSD {ceiling} is above tiers.{DEFAULT_TIER}.taskUSD {task_usd}: "
                      f"a ceiling the factory cannot pay")
            # The plan shows where the number came from, and it is one of its two sources: the class's
            # own taskUSD, or the channel's lower maxCostUSD.
            check(row.get("source") in (f"class:{name}.taskUSD", "channel:maxCostUSD"),
                  f"{at}.source is class:{name}.taskUSD or channel:maxCostUSD, found {row.get('source')!r}")

        # --- the pairing the broker refuses without --------------------------------------------
        # Both tools live on /mcp, and the candidate set is the GitHub write check human.access
        # carries: enabled without either is a switch that reads as on and refuses every call.
        access = human.get("access")
        check(isinstance(access, dict) and bool(access.get("readerFile")),
              f"{cloud}: human.access is declared: the planner's candidate set is its write check")
        if plan.get("enabled") is True:
            check((human.get("mcp") or {}).get("enabled") is True,
                  f"{cloud}: human.intake.plan.enabled needs human.mcp.enabled: both tools are on /mcp")

for problem in problems:
    print(f"  FAIL {problem}")
print(f"intake classes: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
