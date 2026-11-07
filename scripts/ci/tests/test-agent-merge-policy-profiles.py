#!/usr/bin/env python3
# requires: python3
"""Every central class has a harness profile to export to, or stage 1's export fails at migration."""
import pathlib
import sys

import yaml

values = yaml.safe_load(yaml.safe_load(
    pathlib.Path("tooling/base/agent-factory/helm-values-configmap.yaml").read_text())["data"]["values.yaml"])
config = values["config"]
profiles = config.get("harnessProfiles", {})
missing = []
for repo in config["repositories"]:
    for name, cl in repo["classes"].items():
        if name == "review":
            continue
        adopted = "adopt" in (cl.get("author") or {})
        match = [p for p in profiles.values()
                 if (p.get("template") == "none") == adopted
                 and p.get("checks", False) == cl.get("checks", False)
                 and p.get("testFirst", False) == cl.get("testFirst", False)]
        if not match:
            missing.append(f"{repo['name']}: {name}")
if missing:
    sys.exit("no harness profile for: " + ", ".join(missing))
print("every class has a harness profile")
