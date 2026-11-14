#!/usr/bin/env python3
# requires: python3 helm kustomize
"""R1, R3: the room broker and the run-controller run from Maku's `maku` chart, and what Flux
applies keeps the App claim's shape for the broker. For each cloud, the chart rendered with its
HelmRelease's values and postRenderers (scripts/ci/room_broker_chart.py) must hold:

- no Namespace, CiliumNetworkPolicy, Certificate or RuntimeClass of the chart's (network-policy.yaml
  and tls.yaml stay this repository's, the RuntimeClass the cluster's), and one chart ConfigMap, the
  run-controller's; in `agents` only the three Roles and RoleBindings (broker, run-controller, egress
  proxy), the default-deny NetworkPolicy and the runs quota (R3);
- one config volume, naming the generated room-broker-config-<hash>, and no chart ConfigMap;
- the composition's three roles: the migrate init container as rooms_owner, the broker as
  rooms_broker, the retention CronJob as rooms_retention, each with CNPG's CA mounted;
- the Service the policies and callers name: room-broker, its four ports (8090 for the runs' room
  tools), selecting the pods network-policy.yaml, pdb.yaml and vmservicescrape.yaml select;
- two replicas of the pinned image, and no MCP key: :8090 verifies each run's token (R3).
"""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import room_broker_chart  # noqa: E402

BROKER_LABEL = {"app.kubernetes.io/name": "room-broker"}
ROLES = {"owner": "xplane-rooms-cnpg-rooms", "broker": "xplane-rooms-cnpg-role-rooms-broker",  # pragma: allowlist secret
         "retention": "xplane-rooms-cnpg-role-rooms-retention", "ca": "xplane-rooms-cnpg-cluster-ca"}  # pragma: allowlist secret


def env(container, name):
    return next((e for e in container.get("env", []) if e["name"] == name), None)


def secret_ref(e):
    return (((e or {}).get("valueFrom") or {}).get("secretKeyRef") or {}).get("name")


def selector(path, kind, name):
    doc = next(d for d in yaml.safe_load_all((ROOT / path).read_text()) if d and d["kind"] == kind
               and d["metadata"]["name"] == name)
    return doc["spec"].get("endpointSelector", doc["spec"].get("selector"))["matchLabels"]


fails = 0
for cloud in ("aws-0", "gcp-0"):
    try:
        objs = room_broker_chart.render(ROOT, cloud)
    except room_broker_chart.Unavailable as e:
        print(f"SKIP: {e}")
        sys.exit(77)
    built = room_broker_chart.build(ROOT, f"infrastructure/{cloud}/room-broker")
    release = next(d for d in built if d["kind"] == "HelmRelease")
    generated = [d["metadata"]["name"] for d in built if d["kind"] == "ConfigMap"
                 and d["metadata"]["name"].startswith("room-broker-config-")]
    kinds = {(d["kind"], d["metadata"]["name"]) for d in objs}
    by = {(d["kind"], d["metadata"]["name"], d["metadata"].get("namespace", "agent-system")): d for d in objs}
    deploy = by[("Deployment", "room-broker", "agent-system")]
    pod = deploy["spec"]["template"]["spec"]
    broker = pod["containers"][0]
    init = pod.get("initContainers") or []
    cron = by[("CronJob", "room-broker-retention", "agent-system")]
    job = cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    svc = by[("Service", "room-broker", "agent-system")]
    config_vols = [v for v in pod["volumes"] if v.get("configMap")]
    image = release["spec"]["values"]["broker"]["image"]
    checks = {
        # The preflight's config (Maku v0.49.0, preflight on by default) is the other ConfigMap.
        "no Namespace, CNP, Certificate or RuntimeClass, and the run-controller's and the preflight's ConfigMaps alone": not {
            k for k in kinds if k[0] in ("Namespace", "CiliumNetworkPolicy", "Certificate", "RuntimeClass")}
            and sorted(k[1] for k in kinds if k[0] == "ConfigMap") == ["room-broker-preflight", "run-controller-config"],
        "the run-controller and the egress proxy run": {("Deployment", "run-controller"),
                                                        ("Deployment", "egress-proxy")} <= kinds,
        "in agents, the three Roles and RoleBindings, the default-deny and the quota": sorted(
            (k[0], k[1]) for k in by if k[2] == "agents") == sorted(
            [(kind, name) for kind in ("Role", "RoleBinding") for name in ("egress-proxy", "room-broker", "run-controller")]
            + [("NetworkPolicy", "default-deny"), ("ResourceQuota", "runs")]),
        "one config volume, the generated ConfigMap, mounted where ROOMS_CONFIG reads": (
            len(generated) == 1 and [v["configMap"]["name"] for v in config_vols] == generated
            and {"name": config_vols[0]["name"], "mountPath": "/etc/room-broker/config", "readOnly": True}
            in broker["volumeMounts"]
            and env(broker, "ROOMS_CONFIG")["value"] == "/etc/room-broker/config/config.yaml"),
        "migrate runs first, as rooms_owner": [c["name"] for c in init] == ["migrate"]
            and init[0]["args"] == ["migrate"]
            and secret_ref(env(init[0], "ROOMS_MIGRATION_DATABASE_URL")) == ROLES["owner"],
        "the broker connects as rooms_broker": secret_ref(env(broker, "ROOMS_DATABASE_URL")) == ROLES["broker"],
        "the retention job connects as rooms_retention, daily at 03:17": (
            secret_ref(env(job["containers"][0], "ROOMS_DATABASE_URL")) == ROLES["retention"]
            and cron["spec"]["schedule"] == "17 3 * * *"),
        "CNPG's CA is mounted in all three": all(
            any(v.get("secret", {}).get("secretName") == ROLES["ca"] for v in vols)
            for vols in (pod["volumes"], pod["volumes"], job["volumes"])),
        "two replicas of the pinned image, in the job too": deploy["spec"]["replicas"] == 2 and {
            broker["image"], init[0]["image"], job["containers"][0]["image"]} == {
            f"{image['repository']}:{image['tag']}"},
        "no MCP key: :8090 verifies the runs' own tokens": env(broker, "ROOMS_MCP_KEY") is None,
        "the Service serves 8443, 9090, 8080 and 8090": sorted(p["port"] for p in svc["spec"]["ports"])
            == [8080, 8090, 8443, 9090],
        "the Service and Deployment select what the overlays select": (
            svc["spec"]["selector"] == BROKER_LABEL == deploy["spec"]["selector"]["matchLabels"]
            == selector("infrastructure/base/room-broker/network-policy.yaml", "CiliumNetworkPolicy", "room-broker")
            == selector("infrastructure/base/room-broker/pdb.yaml", "PodDisruptionBudget", "room-broker-pdb")
            == selector("infrastructure/base/room-broker/vmservicescrape.yaml", "VMServiceScrape", "room-broker")),
        "the retention pods carry the label their policy selects": (
            job_labels := cron["spec"]["jobTemplate"]["spec"]["template"]["metadata"]["labels"]).get(
            "app.kubernetes.io/name") == selector("infrastructure/base/room-broker/network-policy.yaml",
                                                  "CiliumNetworkPolicy", "room-broker-retention")[
            "app.kubernetes.io/name"],
        "no take-ownership, no CRDs from the chart": all(
            release["spec"][k].get("disableTakeOwnership") is True and release["spec"][k].get("crds") == "Skip"
            for k in ("install", "upgrade")),
    }
    for desc, ok in checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {cloud}: {desc}")
        fails += not ok
if fails:
    print(f"{fails} failure(s)")
    sys.exit(1)
print("PASS")
