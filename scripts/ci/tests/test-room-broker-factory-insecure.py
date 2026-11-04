#!/usr/bin/env python3
# requires: python3
"""An http:// factoryURL in a broker config states factoryInsecure: true (Maku v0.33.0, audit S-1): the broker
refuses to start otherwise, and the rollout never completes. The static half of test-maku-config-load.sh, which
runs the pinned broker's own loader where a Maku clone is available; this one runs everywhere."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
problems = []
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
if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"PASS: {len(configs)} broker configs state factoryInsecure with their http:// factoryURL")
