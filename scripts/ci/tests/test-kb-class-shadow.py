#!/usr/bin/env python3
# requires: python3
"""Smana/runlore-kb's kb-entries class is shadow, with the fence a RunLore entry PR needs (RK3, K8, K12).

The factory's own validation (Maku internal/factory/config) refuses an entry with no triggerLabel, no
docs-links and revert classes, or a shadow class and no full merge block with leakScanCheck in both check
lists; test-maku-config-load.sh replays the values through it. This suite holds the values themselves.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config  # noqa: E402  the values file with the Factory, Repository and MergePolicy objects over it
repos = factory_config.config(ROOT)["repositories"]
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


kb = next((r for r in repos if r["name"] == "Smana/runlore-kb"), None)
if kb is None:
    print("FAIL  the config has no Smana/runlore-kb")
    sys.exit(1)
c = kb["classes"]["kb-entries"]
check("kb-entries is shadow", c.get("shadow") is True and "live" not in c)
check("a RunLore entry PR's shape", (c["diffShape"], c["allowedFiles"], c["companionFiles"]) ==
      ("added-entry", [r"^incidents/[^/]+\.md$"], [r"^index\.md$", r"^log\.md$"]))
check("runlore[bot]'s labelled PRs only", c["author"]["adopt"] == {"logins": ["runlore[bot]"], "branches": ["^runlore/kb-"]}
      and c["requiredLabel"] == "ready-to-merge")
check("the validator holds", c["holdoutChecks"] == ["validate"])
check("five a day at most", c["maxPerDay"] == 5)
check("the classes the factory requires, all shadow", set(kb["classes"]) == {"kb-entries", "docs-links", "revert"}
      and all(cl.get("shadow") is True and "live" not in cl for cl in kb["classes"].values()))
m = kb["merge"]
check("the merge block the factory's validation needs",
      kb["triggerLabel"] == "factory/ready" and m["requiredChecks"] == ["validate", "leak-scan"]
      and m["verifyChecks"] == ["validate", "leak-scan"]
      and m["leakScanCheck"] == "leak-scan" and m["approveToMerge"] is True and m["maxPerDay"] == 5
      and m["breaker"] == {"window": 10, "maxReverts": 1, "maxFollowUps": 1, "recoverAfter": 3})
print(f"==> kb-entries shadow: {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
