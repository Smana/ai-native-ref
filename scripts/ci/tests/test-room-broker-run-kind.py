#!/usr/bin/env python3
# requires: python3 kustomize
"""The broker's real config agrees with the chart values it replaces (R3). The postRenderer deletes
the chart's room-broker-config, so the broker reads this repository's config.yaml, while the chart
renders its RBAC, Service, policies and run-controller from the HelmRelease's values. For every
cloud's render, the config must restate the values: runs (group, namespace, namePrefix), the run
issuer's mode and subPattern (the chart's pattern for those runs), and roomTools.auth. A drift
would leave the broker watching one run kind while the chart grants and admits another. The
run-controller's model gateway and aliases are agent-gateway/model-gateway's."""
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
        docs = room_broker_chart.build(ROOT, f"infrastructure/{cloud}/room-broker")
    except room_broker_chart.Unavailable as e:
        print(f"SKIP: {e}")
        sys.exit(77)
    release = next(d for d in docs if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "room-broker")
    cm = next(d for d in docs if d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("room-broker-config"))
    values, config = release["spec"]["values"], yaml.safe_load(cm["data"]["config.yaml"])
    runs, broker = values["runs"], values["broker"]
    pattern = f"^system:serviceaccount:{runs['namespace']}:{runs['namePrefix']}([a-z2-7]{{8}})$"
    issuers = config.get("runIssuers") or []
    checks[f"{cloud}: config runs is the values' runs"] = config.get("runs") == runs
    checks[f"{cloud}: one run issuer, in the values' mode"] = (
        len(issuers) == 1 and issuers[0].get("mode", "jwks") == broker["runIssuer"]["mode"])
    checks[f"{cloud}: its subPattern is the chart's for those runs"] = bool(issuers) and issuers[0].get("subPattern") == pattern
    checks[f"{cloud}: roomTools.auth is the values'"] = (
        (config.get("roomTools") or {}).get("auth", "key") == broker["roomTools"].get("auth", "key"))
    checks[f"{cloud}: the run-controller runs maku.ogenki.io runs"] = (
        values["runController"]["enabled"] is True and runs["group"] == "maku.ogenki.io")

# The runs call agent-gateway/model-gateway: the run-controller's gateway and aliases are that release's.
gw = yaml.safe_load((ROOT / "infrastructure/base/agent-gateway/model-gateway/helmrelease.yaml").read_text())
gw_values = gw["spec"]["values"]
model = values["runController"]["model"]
checks["the runs call the model gateway release, by its name and namespace"] = (
    model["mode"] == "gateway" and model["gateway"]["service"] == gw_values["name"]
    and model["gateway"]["namespace"] == gw["metadata"]["namespace"])
checks["they name exactly the aliases each of its listeners serves"] = all(
    sorted(model["gateway"]["aliases"][c]) == sorted(gw_values["aliases"][c]) for c in ("public", "internal"))
checks["it admits exactly these runs"] = (
    gw_values["runs"] == {"namespace": runs["namespace"], "namePrefix": runs["namePrefix"]})

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
