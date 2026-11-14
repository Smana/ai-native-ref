#!/usr/bin/env python3
# requires: python3 kustomize
"""The merge policy surface Maku v0.50.0 reads (merge policies review, release N).

- One policy-management stage: the factory's values and every broker config set
  `policyManagement.stage: manage` and none of the six switches it replaces.
- `merge.maxPerDay`, never `autoMergesPerDay` (both set and different refuse the repository).
- No binding is `mode: "off"`: it reads as `disabled`, and the next release refuses the old word.
- The guardrail defaults (MR7): no policy or binding above 10 files, 300 lines or 5 a day unless the
  Factory raises that guardrail; above one, its class is GuardrailMismatch and is not served.
- The bound rule (MR6): every live or shadow binding, resolved with its policy, has allowedFiles or a
  diffShape (docs-links and revert carry theirs built in); otherwise it is Unbounded.
- Both clouds apply the same Factory, Repository and MergePolicy objects.

`maku config validate` (validate-factory-config.sh) refuses the same, by its own rules; this suite names
the ANR-side cause first and holds the shape between pin bumps.
"""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config  # noqa: E402

SWITCHES = ("read", "simulation", "dualEvaluation", "repositoryAuthority", "approvalMemory", "promotion")
BUILT_IN_SHAPE = ("docs-links", "revert")
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


def render(cloud):
    out = subprocess.run(["kustomize", "build", str(ROOT / f"tooling/{cloud}/agent-factory/resources")],
                         capture_output=True, text=True, check=True).stdout
    return sorted((d for d in yaml.safe_load_all(out) if d), key=lambda d: (d["kind"], d["metadata"]["name"]))


def stage_only(pm):
    return isinstance(pm, dict) and pm.get("stage") == "manage" and not any(k in pm for k in SWITCHES)


objs = {cloud: render(cloud) for cloud in ("aws-0", "gcp-0")}
check("aws-0 and gcp-0 apply the same Factory, Repository and MergePolicy objects", objs["aws-0"] == objs["gcp-0"])

check("the factory: policyManagement is {stage: manage}, no switch",
      stage_only(factory_config.values(ROOT)["config"].get("policyManagement")))
for cfg in sorted(ROOT.glob("infrastructure/*/room-broker/config.yaml")):
    pm = (yaml.safe_load(cfg.read_text()) or {}).get("policyManagement")
    check(f"{cfg.relative_to(ROOT)}: policyManagement.stage manage, no switch", stage_only(pm))

docs = objs["aws-0"]
factory = next(d for d in docs if d["kind"] == "Factory")["spec"]
policies = {d["metadata"]["name"]: d["spec"] for d in docs if d["kind"] == "MergePolicy"}
repos = [d for d in docs if d["kind"] == "Repository"]
guard = factory_config.guardrails_with_defaults(factory.get("mergeGuardrails"))
check("the Factory sets no minPromotionEvidence (ignored since Maku v0.50.0: evidence is per policy)",
      "minPromotionEvidence" not in (factory.get("mergeGuardrails") or {}))
check("mergeDefaults: maxPerDay, not autoMergesPerDay", "autoMergesPerDay" not in (factory.get("mergeDefaults") or {}))


def over(spec):
    return [f"{k} {spec[k]} > {guard[k]}" for k in factory_config.CAPS if spec.get(k) and spec[k] > guard[k]]


for name, spec in policies.items():
    check(f"MergePolicy/{name}: within the guardrails {over(spec) or ''}", not over(spec))
for r in repos:
    name, spec = r["metadata"]["name"], r["spec"]
    merge = spec.get("merge") or {}
    check(f"Repository/{name}: merge.maxPerDay, not autoMergesPerDay", "autoMergesPerDay" not in merge)
    for b in spec.get("mergePolicies") or []:
        where = f"Repository/{name} binding {b['name']}"
        check(f"{where}: mode is live, shadow or disabled", b.get("mode") in ("live", "shadow", "disabled"))
        check(f"{where}: within the guardrails {over(b) or ''}", not over(b))
        if b.get("mode") in ("live", "shadow"):
            p = policies.get(b["name"], {})
            bounded = b["name"] in BUILT_IN_SHAPE or p.get("diffShape") or p.get("allowedFiles") or b.get("allowedFiles")
            check(f"{where}: bounded (allowedFiles or a diffShape), not Unbounded", bool(bounded))

print(f"==> merge policy surface: {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
