#!/usr/bin/env python3
# requires: python3 kustomize
"""Factory interfaces part 2, gcp-0's switch-on holds together (runbook 18).

The Slack App, the broker's sponsored client and webhook, and the factory's sponsored principal are
declared in gcp-0's copies, and each side must name what the other reads: the principal's name and
client id file, the webhook's URL on the App's Service, the App's config (base's but teamID and
channels), the channels' cost ceilings against the principal's, the Flux Kustomization that applies
the App, the egress patch the overlay lists.

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
FILES = ["tooling/gcp-0/agent-factory/slack-app/config.yaml",
         "tooling/gcp-0/agent-factory/helm-values-sponsored.yaml"]
checks = {}


def load(rel):
    return [d for d in yaml.safe_load_all((ROOT / rel).read_text()) if d]


def build(rel):
    out = subprocess.run(["kustomize", "build", str(ROOT / rel)], capture_output=True, text=True, check=True)
    return [d for d in yaml.safe_load_all(out.stdout) if d]


broker = load("infrastructure/gcp-0/room-broker/config.yaml")[0]
base_app = load("tooling/base/agent-factory/slack-app/config.yaml")[0]
app = load("tooling/gcp-0/agent-factory/slack-app/config.yaml")[0]
values = yaml.safe_load(load("tooling/gcp-0/agent-factory/helm-values-sponsored.yaml")[0]["data"]["values.yaml"])
api = values["config"]["api"]
principal = api["sponsored"][0]
sponsored = broker["human"]["mcp"]["sponsored"]

# the principal: one name and one client id file filename on each side
checks["the broker and the factory declare one sponsored principal, the same name"] = (
    len(sponsored) == 1 and len(api["sponsored"]) == 1 and sponsored[0]["name"] == principal["name"] == "slack-app")
checks["both read the client id by the <name>-client-id key of the same Secret"] = (
    pathlib.PurePosixPath(sponsored[0]["clientIDFile"]).name == f"{principal['name']}-client-id"
    == pathlib.PurePosixPath(principal["clientIDFile"]).name)
checks["the factory's project id file is the Secret's project-id key"] = (
    api["projectIDFile"] == "/etc/agent-factory-sponsored/project-id")

# the principal's ceilings against the App's channels
ceiling = principal["maxCostUSD"]
checks["the principal's maxCostUSD is in (0, dailyUSD]"] = 0 < ceiling <= principal["dailyUSD"]
checks["every channel's maxCostUSD is at least 0.01 and at most the principal's"] = bool(app["channels"]) and all(
    0.01 <= c["maxCostUSD"] <= ceiling for c in app["channels"].values())
allowed = set(principal["repositories"])
checks["every channel's repositories are the principal's"] = all(
    set(c["repositories"]) <= allowed for c in app["channels"].values())

# the App's config is base's, teamID and channels apart; the broker URL has no path
strip = lambda c: {k: v for k, v in c.items() if k not in ("teamID", "channels")}
checks["the App's gcp-0 config is base's but for teamID and channels"] = strip(app) == strip(base_app)

# the owner's Slack identity: team id then user id, on the App's own team
(team_user,) = principal["onBehalfOf"]["slack"]
checks["onBehalfOf names the App's team"] = team_user.split("/")[0] == app["teamID"]

# the webhook targets the App's Service, listener port and path
hook = next((w for w in broker.get("webhooks", []) if w["name"] == "slack-app"), None)
service = next(d for d in load("tooling/base/agent-factory/slack-app/service.yaml") if d["kind"] == "Service")
ports = {p["port"] for p in service["spec"]["ports"]}
checks["the broker declares the slack-app webhook on the App's Service, in its namespace"] = bool(hook) and (
    hook["network"] == "cluster"
    and hook["url"].startswith(f"http://{service['metadata']['name']}.{service['metadata']['namespace']}.svc.cluster.local:")
    and int(hook["url"].split(":")[-1].split("/")[0]) in ports and hook["url"].endswith("/webhooks")
    and all(e.startswith("room.") for e in hook["events"]))
checks["the webhook key file is the one the broker's whole-Secret mount holds"] = bool(hook) and hook[
    "secretFile"].startswith("/etc/room-broker/webhooks/slack-app/")

# the cluster applies the App, from gcp-0's directory, after the siblings it calls
cluster = ROOT / "clusters/gcp-0-agent-platform"
ks = load("clusters/gcp-0-agent-platform/tooling-factory-slack-app.yaml")[0]["spec"]
checks["gcp-0's cluster lists and names the App's Kustomization, applying gcp-0's directory"] = (
    "tooling-factory-slack-app.yaml" in yaml.safe_load((cluster / "kustomization.yaml").read_text())["resources"]
    and ks["path"] == "./tooling/gcp-0/agent-factory/slack-app"
    and ks["sourceRef"] == {"kind": "OCIRepository", "name": "ai-native-ref"})
checks["it waits for the secrets, the broker and the factory"] = (
    {d["name"] for d in ks["dependsOn"]} == {"agent-secrets", "room-broker", "agent-factory"})

# the render: gcp-0's ConfigMap is the one the Deployment mounts, the factory has both values entries
docs = build("tooling/gcp-0/agent-factory/slack-app")
cms = [d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("factory-slack-app-config")]
checks["the render holds one App config ConfigMap, gcp-0's"] = (
    len(cms) == 1 and yaml.safe_load(cms[0]["data"]["config.yaml"])["teamID"] == app["teamID"]
    and "factory-slack-app-config" not in {d["metadata"]["name"] for d in docs})
deploy = next(d for d in docs if d["kind"] == "Deployment")
mounted = [v.get("configMap", {}).get("name") for v in deploy["spec"]["template"]["spec"]["volumes"]]
checks["the Deployment mounts that ConfigMap"] = cms[0]["metadata"]["name"] in mounted
factory = build("tooling/gcp-0/agent-factory")
release = next(d for d in factory if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "agent-factory")
refs = [r["name"] for r in release["spec"]["valuesFrom"]]
checks["the factory's values merge the sponsored ConfigMap after base's"] = (
    refs[0] == "agent-factory-helm-values" and refs[-1] == "agent-factory-helm-values-sponsored")

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
