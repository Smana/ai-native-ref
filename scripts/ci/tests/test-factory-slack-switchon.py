#!/usr/bin/env python3
# requires: python3 kustomize
"""Factory interfaces part 2, each cloud's switch-on holds together (runbooks 18 and 22).

The Slack App, the broker's sponsored client and webhook, and the factory's sponsored principal are
declared in each cloud's copies (CLOUDS; one Slack App serves one of them at a time, the one its
Request URL names), and each side must name what the other reads: the principal's name and
client id file, the webhook's URL on the App's Service, the App's channel binding (the declaration,
tooling/base/agent-factory/slack-bindings.yaml, rendered into base's config), the channels' cost ceilings against the principal's, the Flux Kustomization that applies
the App, the egress patch the overlay lists, and one owner of the factory's sponsored Secret.

The two Slack decision switches (the broker's `human.slackDecide` and a channel's `approvals`) are
checked as consistency, never as presence: each is optional, and a channel that draws approval cards
must be paired with the broker entry that can answer them, so every check here passes before the
switch-on and fails on a half-on tree.

The Slack ids are not known until the owner has created the App: they are marked OWNER-FILL-* in
the files below. They pass while FACTORY_SLACK_LIVE is unset, so the tree builds before the owner's
step; with FACTORY_SLACK_LIVE=1 any marker left fails (set it in the switch-on PR's CI, or run it
by hand before merging)."""
import os
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MARKER = "OWNER-FILL"
CLOUDS = ("aws-0", "gcp-0")
FILES = ["tooling/base/agent-factory/slack-bindings.yaml"] + [
    f"tooling/{c}/agent-factory/helm-values-sponsored.yaml" for c in CLOUDS]
checks = {}


def load(rel):
    return [d for d in yaml.safe_load_all((ROOT / rel).read_text()) if d]


def build(rel):
    out = subprocess.run(["kustomize", "build", str(ROOT / rel)], capture_output=True, text=True, check=True)
    return [d for d in yaml.safe_load_all(out.stdout) if d]


app = load("tooling/base/agent-factory/slack-bindings.yaml")[0]
service = next(d for d in load("tooling/base/agent-factory/slack-app/service.yaml") if d["kind"] == "Service")


def check_cloud(cloud):
    broker = load(f"infrastructure/{cloud}/room-broker/config.yaml")[0]
    values = yaml.safe_load(load(f"tooling/{cloud}/agent-factory/helm-values-sponsored.yaml")[0]["data"]["values.yaml"])
    api = values["config"]["api"]
    principal = api["sponsored"][0]
    sponsored = broker["human"]["mcp"]["sponsored"]

    # the principal: one name and one client id file filename on each side
    checks[f"{cloud}: the broker and the factory declare one sponsored principal, the same name"] = (
        len(sponsored) == 1 and len(api["sponsored"]) == 1 and sponsored[0]["name"] == principal["name"] == "slack-app")
    checks[f"{cloud}: both read the client id by the <name>-client-id key of the same Secret"] = (
        pathlib.PurePosixPath(sponsored[0]["clientIDFile"]).name == f"{principal['name']}-client-id"
        == pathlib.PurePosixPath(principal["clientIDFile"]).name)
    checks[f"{cloud}: the factory's project id file is the Secret's project-id key"] = (
        api["projectIDFile"] == "/etc/agent-factory-sponsored/project-id")

    # the principal's ceilings against the App's channels
    ceiling = principal["maxCostUSD"]
    checks[f"{cloud}: the principal's maxCostUSD is in (0, dailyUSD]"] = 0 < ceiling <= principal["dailyUSD"]
    checks[f"{cloud}: every channel's maxCostUSD is at least 0.01 and at most the principal's"] = bool(app["channels"]) and all(
        0.01 <= c["maxCostUSD"] <= ceiling for c in app["channels"].values())
    allowed = set(principal["repositories"])
    checks[f"{cloud}: every channel's repositories are the principal's"] = all(
        set(c["repositories"]) <= allowed for c in app["channels"].values())

    # the owner's Slack identity: team id then user id, on the App's own team
    (team_user,) = principal["onBehalfOf"]["slack"]
    checks[f"{cloud}: onBehalfOf names the App's team"] = team_user.split("/")[0] == app["teamID"]

    # the webhook targets the App's Service, listener port and path
    hook = next((w for w in broker.get("webhooks", []) if w["name"] == "slack-app"), None)
    ports = {p["port"] for p in service["spec"]["ports"]}
    checks[f"{cloud}: the broker declares the slack-app webhook on the App's Service, in its namespace"] = bool(hook) and (
        hook["network"] == "cluster"
        and hook["url"].startswith(f"http://{service['metadata']['name']}.{service['metadata']['namespace']}.svc.cluster.local:")
        and int(hook["url"].split(":")[-1].split("/")[0]) in ports and hook["url"].endswith("/webhooks")
        and all(e.startswith("room.") for e in hook["events"]))
    checks[f"{cloud}: the webhook key file is the one the broker's whole-Secret mount holds"] = bool(hook) and hook[
        "secretFile"].startswith("/etc/room-broker/webhooks/slack-app/")

    # D14's two switches: each is optional, and when one side is on the other must be able to answer.
    decide = broker["human"].get("slackDecide")
    checks[f"{cloud}: human.slackDecide, when set, names the sponsored principal and the App's team"] = decide is None or (
        decide["principal"] == principal["name"] and decide["teamID"] == app["teamID"])
    checks[f"{cloud}: every channel's approvals, when set, is a bool"] = all(
        isinstance(c.get("approvals", False), bool) for c in app["channels"].values())
    draws_cards = any(c.get("approvals") for c in app["channels"].values())
    checks[f"{cloud}: a channel drawing cards has room.approval_closed in the broker's webhook list"] = not draws_cards or (
        hook is not None and "room.approval_closed" in hook["events"])
    # The broker's switch is the authority and must be on before any card offers a button (Maku
    # docs/slack.md): without it the decide route is a 404 and every press says the factory is unreachable.
    checks[f"{cloud}: a channel drawing cards has human.slackDecide on the broker"] = not draws_cards or decide is not None

    # the cluster applies the App, from its own cloud's directory, after the siblings it calls
    cluster = ROOT / f"clusters/{cloud}-agent-platform"
    ks = load(f"clusters/{cloud}-agent-platform/tooling-factory-slack-app.yaml")[0]["spec"]
    checks[f"{cloud}: the cluster lists and names the App's Kustomization, applying its cloud's directory"] = (
        "tooling-factory-slack-app.yaml" in yaml.safe_load((cluster / "kustomization.yaml").read_text())["resources"]
        and ks["path"] == f"./tooling/{cloud}/agent-factory/slack-app"
        and ks["sourceRef"] == {"kind": "OCIRepository", "name": "ai-native-ref"})
    checks[f"{cloud}: it waits for the secrets, the broker and the factory"] = (
        {d["name"] for d in ks["dependsOn"]} == {"agent-secrets", "room-broker", "agent-factory"})

    # the render: the overlay's ConfigMap is the one the Deployment mounts, the factory has both values entries
    docs = build(f"tooling/{cloud}/agent-factory/slack-app")
    cms = [d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("factory-slack-app-config")]
    # CD24: the declaration is the one place the channel binding is written, and the render is its
    # picture — the overlay holds no copy to drift.
    checks[f"{cloud}: the overlay holds no App config of its own"] = not (ROOT / f"tooling/{cloud}/agent-factory/slack-app/config.yaml").exists()
    rendered = yaml.safe_load(cms[0]["data"]["config.yaml"]) if len(cms) == 1 else {}
    checks[f"{cloud}: the render is one App config, base's generated, with the declaration's binding"] = (
        len(cms) == 1
        and rendered["teamID"] == app["teamID"]
        and rendered["channels"] == app["channels"]
        and "factory-slack-app-config" not in {d["metadata"]["name"] for d in docs})
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    mounted = [v.get("configMap", {}).get("name") for v in deploy["spec"]["template"]["spec"]["volumes"]]
    checks[f"{cloud}: the Deployment mounts that ConfigMap"] = len(cms) == 1 and cms[0]["metadata"]["name"] in mounted
    factory = build(f"tooling/{cloud}/agent-factory")
    release = next(d for d in factory if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "agent-factory")
    refs = [r["name"] for r in release["spec"]["valuesFrom"]]
    checks[f"{cloud}: the factory's values merge the sponsored ConfigMap after base's"] = (
        refs[0] == "agent-factory-helm-values" and refs[-1] == "agent-factory-helm-values-sponsored")

    # Two Flux Kustomizations must not own one object: exactly one of the factory's render and the App's
    # carries the factory's sponsored Secret (aws-0's factory, gcp-0's App).
    owners = [d for d in factory + docs
              if d["kind"] == "ExternalSecret" and d["metadata"]["name"] == "agent-factory-sponsored"]
    checks[f"{cloud}: one render owns agent-factory-sponsored, with the keys both sides read"] = len(owners) == 1 and {
        e["secretKey"] for e in owners[0]["spec"]["data"]} >= {
        pathlib.PurePosixPath(principal["clientIDFile"]).name, pathlib.PurePosixPath(api["projectIDFile"]).name}


for c in CLOUDS:
    check_cloud(c)

# the owner's markers
left = [f"{f}: {line.strip()}" for f in FILES for line in (ROOT / f).read_text().splitlines()
        if MARKER in line and not line.lstrip().startswith("#")]
if os.environ.get("FACTORY_SLACK_LIVE") == "1":
    checks[f"no {MARKER} marker is left (FACTORY_SLACK_LIVE=1)"] = not left
else:
    print(f"  note {len(left)} {MARKER} marker line(s) wait for the owner (set FACTORY_SLACK_LIVE=1 to enforce)")

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
for line in left if os.environ.get("FACTORY_SLACK_LIVE") == "1" else []:
    print(f"       left: {line}")
sys.exit(1 if fails else 0)
