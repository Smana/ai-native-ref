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
import json
import pathlib
import re
import subprocess
import sys
import tempfile

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

# OD-F3-1 (R50): this repository's dead-links lane needs its own rule, or a shadow decision here
# could never reach would-arm; the lane's schedule and monitor are declared with it.
own = next(r for r in config["repositories"] if r["name"] == "Smana/ai-native-ref")
own_dead = (own.get("classes") or {}).get("dead-links")
if own_dead is None:
    fails.append("Smana/ai-native-ref declares no dead-links class")
else:
    if "low-risk: dead-links" not in rules_of(yaml.safe_load(POLICY["Smana/ai-native-ref"].read_text())):
        fails.append("Smana/ai-native-ref: dead-links declared with no 'low-risk: dead-links' rule in .policy.yml (R50)")
    if not any(s.get("class") == "dead-links" for s in own.get("schedules") or []):
        fails.append("Smana/ai-native-ref: dead-links has no schedule (MC6)")
    if "monitor" not in own_dead:
        fails.append("Smana/ai-native-ref: dead-links has no monitor (L16)")

# Offline proof 16 (MC11): every file a never-automerge rule of the host's renovate.json reaches
# is the lane's to refuse: in the gate list or in deps-patch's protectedFiles, or outside its
# allowedFiles. A rule by file names its files; a rule by package reaches every host file that
# references the package as a dependency, never a bare mention (M14). A new never-automerge rule
# is covered or this fails.
HOST_TREE = OWN / ".host"  # the host's own checkout: the composite also holds this repository's files (L5)
KEYED = r"^[^#]*(chart|image|repository|url|name):[[:space:]]*['\"]?[^'\"]*"


def ere(s):
    return re.sub(r"([.\[\]()*+?{}|^$\\])", r"\\\1", s)


def reach_pattern(name):
    """The ERE of a dependency reference to one matchPackageNames entry. A regex entry loses its
    anchors (grep's ^ is the line's start, not the package name's); a path is a whole token
    wherever it sits, open-ended when the regex was a prefix; a bare name is a word in the value
    of a dependency key."""
    regex = name.startswith("/") and name.endswith("/")
    body = name[1:-1] if regex else ere(name)
    exact = not regex or body.endswith("$")
    body = body.removeprefix("^").removesuffix("$")
    if "/" in body:
        return rf"(^|[[:space:]'\"=/@])({body})" + (r"([[:space:]'\"@:]|$)" if exact else "")
    return rf"{KEYED}\b({body})\b"


def never_automerge(renovate):
    return [r for r in renovate.get("packageRules", []) if r.get("automerge") is False or r.get("enabled") is False]


def reached(rule, tree=HOST_TREE):
    files = set(rule.get("matchFileNames", []))
    for name in rule.get("matchPackageNames", []):
        out = subprocess.run(["git", "-C", str(tree), "grep", "-lE", reach_pattern(name), "--", "*.yaml", "*.yml"],
                             capture_output=True, text=True).stdout
        files |= set(out.split())
    return files


def refused(path, cl, gates):
    allowed = cl.get("allowedFiles")
    if allowed and not any(re.match(f"^(?:{p})$", path) for p in allowed):
        return True
    return any(re.search(p, path) for p in list(gates) + cl.get("protectedFiles", []))


# Self-test of the reach (M14), on a fixture tree: a bare name reaches the file that deploys it,
# not one that mentions it; an anchored registry regex reaches its reference; a repository that
# only shares the package's prefix is not the package.
with tempfile.TemporaryDirectory() as d:
    fx = pathlib.Path(d)
    for path, text in {
        "deploy.yaml": "spec:\n  chart:\n    spec:\n      chart: zitadel\n",
        "mention.yaml": "# zitadel never started\nspec:\n  description: waits for zitadel\n",
        "pkg.yaml": "spec:\n  package: ghcr.io/smana/crossplane-configuration-aws:v0.9.20\n",
        "inference.yaml": "spec:\n  url: https://github.com/kubernetes-sigs/gateway-api-inference-extension\n",
        "gateway.yaml": "spec:\n  url: https://github.com/kubernetes-sigs/gateway-api\n",
    }.items():
        (fx / path).write_text(text)
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "add", "."], check=True)
    for names, want in [(["zitadel"], {"deploy.yaml"}),
                        (["/^ghcr\\.io/smana/crossplane-configuration-/"], {"pkg.yaml"}),
                        (["kubernetes-sigs/gateway-api"], {"gateway.yaml"})]:
        if (got := reached({"matchPackageNames": names}, fx)) != want:
            fails.append(f"self-test: {names} reaches {sorted(got)}, want {sorted(want)}")

renovate = json.loads((HOST_TREE / ".github/renovate.json").read_text())
host_classes = next(r for r in config["repositories"] if r["name"] == "Smana/cloud-native-ref")["classes"]
gates = rules_of(host)[CANON]["if"]["no_changed_files"]["paths"]
for lane in ("deps-patch", "deps-minor"):  # both adopted lanes hold the same refusals
    lane_cl = host_classes.get(lane)
    if lane_cl is None:
        fails.append(f"{lane}: not declared on the host")
        continue
    for rule in never_automerge(renovate):
        for path in sorted(reached(rule)):
            if not refused(path, lane_cl, gates):
                fails.append(f"{lane}: never-automerge {rule.get('matchPackageNames') or rule.get('matchFileNames')} reaches {path}, which the lane would take")
deps = host_classes.get("deps-patch")
if deps is not None:
    # self-test: drop zitadel's protection and the suite must notice
    probe = dict(deps, protectedFiles=[p for p in deps.get("protectedFiles", []) if "zitadel" not in p])
    if all(refused(p, probe, gates) for r in never_automerge(renovate) for p in reached(r)):
        fails.append("self-test: a dropped protectedFiles entry went unnoticed")

for f in fails:
    print(f"FAIL: {f}")
print(f"==> merge gate parity: {len(config['repositories'])} repositories, {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
