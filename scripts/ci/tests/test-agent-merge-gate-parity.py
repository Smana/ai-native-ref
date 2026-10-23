#!/usr/bin/env python3
# requires: python3
"""Each class's fence, declared twice, is one fence (merge gate classes MC2).

A class that declares allowedFiles, protectedFiles, modifyOnly or maxModifiedLines in the
factory's config is held to its `low-risk: <class>` rule in the repository's .policy.yml, the
independent second check policy-bot evaluates:

- allowedFiles is the rule's only_changed_files, as a set;
- the rule's no_changed_files is the gate list plus protectedFiles, as a set;
- modifyOnly is file_not_added and file_not_deleted, both ['.*'];
- maxModifiedLines n is modified_lines total "< n+1".

A class with no rule may not be live. docs-links and revert declare none of the four: their fence
is the policy's alone, as before the vocabulary. The host's .policy.yml is the composite's; this
repository's is the working directory's (run-tests.sh runs this from .composite/).
"""
import copy
import pathlib
import sys

import yaml

HOST = pathlib.Path(__file__).resolve().parents[3]
OWN = pathlib.Path.cwd()
POLICY = {"Smana/cloud-native-ref": HOST / ".policy.yml", "Smana/ai-native-ref": OWN / ".policy.yml"}
CANON = "agent change approved by a maintainer"
FENCE = ("allowedFiles", "protectedFiles", "modifyOnly", "maxModifiedLines")


def rules_of(policy):
    return {r["name"]: r for r in policy.get("approval_rules", [])}


def mismatches(name, cl, rule, gates):
    """Every way the class's declared fence and its policy rule disagree."""
    cond = rule.get("if", {})
    out = []
    allowed = set((cond.get("only_changed_files") or {}).get("paths", []))
    if set(cl.get("allowedFiles", [])) != allowed:
        out.append(f"{name}: allowedFiles {sorted(cl.get('allowedFiles', []))} != only_changed_files {sorted(allowed)}")
    protected = set((cond.get("no_changed_files") or {}).get("paths", []))
    if protected != set(gates) | set(cl.get("protectedFiles", [])):
        out.append(f"{name}: no_changed_files is not the gate list plus protectedFiles: "
                   f"{sorted(protected ^ (set(gates) | set(cl.get('protectedFiles', []))))}")
    added = (cond.get("file_not_added") or {}).get("paths") == [".*"]
    deleted = (cond.get("file_not_deleted") or {}).get("paths") == [".*"]
    if bool(cl.get("modifyOnly")) != (added and deleted):
        out.append(f"{name}: modifyOnly {bool(cl.get('modifyOnly'))} but file_not_added/file_not_deleted {added}/{deleted}")
    total = (cond.get("modified_lines") or {}).get("total")
    want = f"< {cl['maxModifiedLines'] + 1}" if cl.get("maxModifiedLines") else None
    if total != want:
        out.append(f"{name}: maxModifiedLines {cl.get('maxModifiedLines')} but modified_lines total {total!r}")
    return out


def check(repo, classes, policy):
    rules = rules_of(policy)
    gates = rules[CANON]["if"]["no_changed_files"]["paths"]
    out = []
    for name, cl in sorted(classes.items()):
        if not any(k in cl for k in FENCE):
            continue
        rule = rules.get(f"low-risk: {name}")
        if rule is None:
            if cl.get("live"):
                out.append(f"{repo}: class {name} is live with no 'low-risk: {name}' rule in .policy.yml (MC2)")
            continue
        out += [f"{repo}: {m}" for m in mismatches(name, cl, rule, gates)]
    return out


cm = yaml.safe_load((HOST / "tooling/base/agent-factory/helm-values-configmap.yaml").read_text())
config = yaml.safe_load(cm["data"]["values.yaml"])["config"]
fails = []
for r in config["repositories"]:
    fails += check(r["name"], r.get("classes") or {}, yaml.safe_load(POLICY[r["name"]].read_text()))

# Offline proof 11, on the host's real rule: dead-links' fence as the factory declares it on the
# host agrees with docs-links' rule renamed, and a deliberate mismatch is caught.
host = yaml.safe_load(POLICY["Smana/cloud-native-ref"].read_text())
dead = next(r for r in config["repositories"] if r["name"] == "Smana/cloud-native-ref")["classes"].get("dead-links")
if dead is None:
    fails.append("self-test: the host declares no dead-links class")
else:
    probe = copy.deepcopy(host)
    twin = copy.deepcopy(rules_of(probe)["low-risk: docs-links"])
    twin["name"] = "low-risk: dead-links"
    probe["approval_rules"].append(twin)
    live = dict(dead, live=True)
    if check("self-test", {"dead-links": live}, probe):
        fails.append(f"self-test: dead-links disagrees with docs-links' rule: {check('self-test', {'dead-links': live}, probe)}")
    for key, value in [("maxModifiedLines", 30), ("modifyOnly", False), ("allowedFiles", [r"^docs/.+\.md$"]),
                       ("protectedFiles", [r"^website/"])]:
        if not check("self-test", {"dead-links": dict(live, **{key: value})}, probe):
            fails.append(f"self-test: a {key} mismatch went unnoticed")
    if not check("self-test", {"dead-links": live}, host):
        fails.append("self-test: a live class without its rule went unnoticed")

for f in fails:
    print(f"FAIL: {f}")
print(f"==> merge gate parity: {len(config['repositories'])} repositories, {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
