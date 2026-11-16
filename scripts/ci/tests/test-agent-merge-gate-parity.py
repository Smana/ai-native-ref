#!/usr/bin/env python3
# requires: python3
"""Every bound class is bounded in the factory's own MergePolicy and binding objects (merge policies
review MR6, Task 2).

`maku/merge-gate` is the sole merge gate (`mergeDefaults.gateStatus: true`, `policyBot: false`), so
this suite no longer reads `.policy.yml`:

- Every `live` or `shadow` class, resolved from its MergePolicy and binding, has `allowedFiles` or a
  `diffShape` (`docs-links` and `revert` carry `links-only` built in).
- No `live` class has `evidence: low` without a `diffShape`, built-in shape or `oracle` (MR4).
- `Smana/ai-native-ref`'s `dead-links` class carries its schedule and monitor (MC6, L16).
- Offline proof 16 (MC11): every file a never-automerge rule of the host's `renovate.json` reaches
  is refused by `deps-patch` and `deps-minor` (outside `allowedFiles` or matched by `protectedFiles`,
  with Maku's default protected paths included).
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HOST = pathlib.Path(__file__).resolve().parents[3]
OWN = pathlib.Path.cwd()
BUILT_IN_SHAPE = ("docs-links", "revert")

sys.path.insert(0, str(HOST / "scripts/ci"))
import factory_config  # noqa: E402  the values file with the Factory, Repository and MergePolicy objects over it


def class_problems(repo, classes):
    out = []
    for name, cl in sorted(classes.items()):
        if not (cl.get("live") or cl.get("shadow")):
            continue
        has_shape = name in BUILT_IN_SHAPE or bool(cl.get("diffShape"))
        if not (has_shape or cl.get("allowedFiles")):
            out.append(f"{repo}: class {name} is live or shadow without allowedFiles or diffShape (MR6)")
        if cl.get("live") and cl.get("evidence") == "low" and not (has_shape or cl.get("oracle")):
            out.append(f"{repo}: live class {name} has evidence: low without a diffShape or an oracle (MR4)")
    return out


config = factory_config.config(HOST)
fails = []
for r in config["repositories"]:
    fails += class_problems(r["name"], r.get("classes") or {})

# Self-test: an unbounded class and a live evidence: low class without a shape or an oracle are caught.
if not class_problems("self-test", {"unbounded": {"shadow": True}}):
    fails.append("self-test: an unbounded shadow class went unnoticed")
if not class_problems("self-test", {"unbacked-low": {"live": True, "evidence": "low", "allowedFiles": [r"^docs/"]}}):
    fails.append("self-test: a live evidence: low class without a shape or an oracle went unnoticed")
if class_problems("self-test", {"docs-links": {"live": True, "evidence": "low"}}):
    fails.append("self-test: built-in shape docs-links was rejected")

# OD-F3-1 (MC6, L16): this repository's dead-links lane declares its schedule and monitor with it.
own = next(r for r in config["repositories"] if r["name"] == "Smana/ai-native-ref")
own_dead = (own.get("classes") or {}).get("dead-links")
if own_dead is None:
    fails.append("Smana/ai-native-ref declares no dead-links class")
else:
    if not any(s.get("class") == "dead-links" for s in own.get("schedules") or []):
        fails.append("Smana/ai-native-ref: dead-links has no schedule (MC6)")
    if "monitor" not in own_dead:
        fails.append("Smana/ai-native-ref: dead-links has no monitor (L16)")

# Offline proof 16 (MC11): every file a never-automerge rule of the host's renovate.json reaches
# is the lane's to refuse: in protectedFiles (Maku's defaults included) or outside allowedFiles.
HOST_TREE = OWN / ".host"  # the host's own checkout when run from .composite/ (L5)
KEYED = r"^[^#]*(chart|image|repository|url|name):[[:space:]]*['\"]?[^'\"]*"


def ere(s):
    return re.sub(r"([.\[\]()*+?{}|^$\\])", r"\\\1", s)


def reach_pattern(name):
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


def refused(path, cl):
    allowed = cl.get("allowedFiles")
    if allowed and not any(re.match(f"^(?:{p})$", path) for p in allowed):
        return True
    narrowed = cl.get("narrowedFiles")
    if narrowed and not any(re.match(f"^(?:{p})$", path) for p in narrowed):
        return True
    return any(re.search(p, path) for p in cl.get("protectedFiles", []))


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

renovate_path = HOST_TREE / ".github/renovate.json"
if renovate_path.is_file():
    renovate = json.loads(renovate_path.read_text())
    host_classes = next(r for r in config["repositories"] if r["name"] == "Smana/cloud-native-ref")["classes"]
    for lane in ("deps-patch", "deps-minor"):
        lane_cl = host_classes.get(lane)
        if lane_cl is None:
            fails.append(f"{lane}: not declared on the host")
            continue
        for rule in never_automerge(renovate):
            for path in sorted(reached(rule)):
                if not refused(path, lane_cl):
                    fails.append(f"{lane}: never-automerge {rule.get('matchPackageNames') or rule.get('matchFileNames')} reaches {path}, which the lane would take")
    deps = host_classes.get("deps-patch")
    if deps is not None:
        probe = dict(deps, protectedFiles=[p for p in deps.get("protectedFiles", []) if "zitadel" not in p])
        if all(refused(p, probe) for r in never_automerge(renovate) for p in reached(r)):
            fails.append("self-test: a dropped protectedFiles entry went unnoticed")

for f in fails:
    print(f"FAIL: {f}")
print(f"==> merge gate parity: {len(config['repositories'])} repositories, {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
