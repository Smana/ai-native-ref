#!/usr/bin/env python3
# requires: python3
"""An http:// factoryURL in a broker config states factoryInsecure: true (Maku v0.33.0, audit S-1): the broker
refuses to start otherwise, and the rollout never completes. The static half of test-maku-config-load.sh, which
runs the pinned broker's own loader where a Maku clone is available; this one runs everywhere.

The https:// half: a factoryURL that is https:// names a factoryCAFile the broker's pod mounts (app.yaml), and the factory
chart serves TLS (api.tls.secretName, with an issuer) on the port it calls, so the two hops flip together."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
problems = []
app = next(d for d in yaml.safe_load_all((ROOT / "infrastructure/base/room-broker/app.yaml").read_text()) if d)
mounts = [(m, v) for m in app["spec"].get("extraVolumeMounts", []) for v in app["spec"].get("extraVolumes", [])]
factory_values = next(d for d in yaml.safe_load_all((ROOT / "tooling/base/agent-factory/helm-values-configmap.yaml").read_text())
                      if d and d.get("kind") == "ConfigMap")
tls = yaml.safe_load(factory_values["data"]["values.yaml"]).get("api", {}).get("tls", {})
https = 0
configs = sorted(ROOT.glob("infrastructure/*/room-broker/config.yaml"))
if not configs:
    problems.append("no broker config found")
for path in configs:
    cfg = yaml.safe_load(path.read_text())
    url = cfg.get("factoryURL", "")
    if url.startswith("http://") and cfg.get("factoryInsecure") is not True:
        problems.append(f"{path.relative_to(ROOT)}: factoryURL {url} is http:// with no factoryInsecure: true")
    if url.startswith("https://") and cfg.get("factoryInsecure"):
        problems.append(f"{path.relative_to(ROOT)}: factoryInsecure is set on an https:// factoryURL")
    if url.startswith("https://"):
        https += 1
        ca = cfg.get("factoryCAFile", "")
        if not ca:
            problems.append(f"{path.relative_to(ROOT)}: https:// factoryURL with no factoryCAFile (the platform CA is private)")
        elif not any(ca == f"{m['mountPath']}/{i['path']}"
                     for m, v in mounts for i in v.get("secret", {}).get("items", [])
                     if m["name"] == v["name"]):
            problems.append(f"{path.relative_to(ROOT)}: factoryCAFile {ca} is not a file app.yaml mounts from a Secret")
        if not (tls.get("secretName") and tls.get("issuerRef", {}).get("name")):
            problems.append(f"{path.relative_to(ROOT)}: https:// factoryURL, but the factory chart sets no api.tls secretName and issuer")
        if not url.startswith("https://agent-factory.agent-system.svc"):
            problems.append(f"{path.relative_to(ROOT)}: factoryURL {url} is not a name the factory certificate carries")
if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"PASS: {len(configs)} broker configs: an http:// factoryURL states factoryInsecure, {https} https:// ones name a mounted CA and a TLS factory")
