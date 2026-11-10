#!/usr/bin/env python3
# requires: python3
"""Every central class has a harness profile to export to, or stage 1's export fails at migration."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config  # noqa: E402  the values file with the Factory, Repository and MergePolicy objects over it
config = factory_config.config(ROOT)
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
