#!/usr/bin/env python3
# requires: python3 kustomize
"""The merge policy surface Maku reads (merge policies review, releases N and N+1).

- One policy-management stage: the factory's values and every broker config set
  `policyManagement.stage: manage` and none of the six switches it replaces.
- `mergeDefaults`: `gateStatus: true`, `policyBot: false`, and `maxPerDay` (never `autoMergesPerDay`).
- The chart's four-policy catalog (`mergePolicies.catalog.enabled: true`, `exclude: [deps-patch]`)
  supplies `docs-links`, `revert` and `docs`; `deps-patch` stays in `resources/` with its six
  `protectedFiles`, `monitor.flux` and `evidence: low`. No file in `resources/` duplicates a
  non-excluded catalog policy, and the seven empty policies (`docs-links`, `revert`, `docs`,
  `dashboards`, `scripts`, `tests`, `review`) are deleted from `resources/`.
- No `MergePolicy` sets `requires` or a workflow field (`harness`, `harnessAllowed`, `escalation`,
  `testFirst`, `checks`).
- No binding uses `mode: "off"` or `mode: "disabled"` or names a deleted empty policy; every binding
  names a policy from the chart catalog or `resources/`.
- The guardrail defaults (MR7): no policy or binding above 10 files, 300 lines or 5 a day unless the
  Factory raises that guardrail; above one, its class is GuardrailMismatch and is not served.
- The bound rule (MR6): every live or shadow binding, resolved with its policy, has allowedFiles or a
  diffShape (docs-links and revert carry theirs built in); otherwise it is Unbounded.
- Both clouds apply the same Factory (outside `spec.evaluation`), Repository and MergePolicy objects.
"""
import copy
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config  # noqa: E402

SWITCHES = ("read", "simulation", "dualEvaluation", "repositoryAuthority", "approvalMemory", "promotion")
BUILT_IN_SHAPE = ("docs-links", "revert")
DELETED_POLICIES = ("docs-links", "revert", "docs", "dashboards", "scripts", "tests", "review")
WORKFLOW_FIELDS = ("harness", "harnessAllowed", "escalation", "testFirst", "checks")
fails = []


def check(name, ok):
    print(("ok    " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


def render(cloud):
    out = subprocess.run(["kustomize", "build", str(ROOT / f"tooling/{cloud}/agent-factory/resources")],
                         capture_output=True, text=True, check=True).stdout
    return sorted((d for d in yaml.safe_load_all(out) if d), key=lambda d: (d["kind"], d["metadata"]["name"]))


def without_evaluation(docs):
    out = copy.deepcopy(docs)
    for d in out:
        if d.get("kind") == "Factory":
            (d.get("spec") or {}).pop("evaluation", None)
    return out


def chart_catalog():
    return factory_config.chart_catalog(factory_config.values(ROOT))


def policies(docs):
    out = dict(chart_catalog())
    for d in docs:
        if d["kind"] == "MergePolicy":
            out[d["metadata"]["name"]] = d["spec"]
    return out


def repositories(docs):
    return {d["metadata"]["name"]: d["spec"] for d in docs if d["kind"] == "Repository"}


def stage_only(pm):
    return isinstance(pm, dict) and pm.get("stage") == "manage" and not any(k in pm for k in SWITCHES)


objs = {cloud: render(cloud) for cloud in ("aws-0", "gcp-0")}
check("aws-0 and gcp-0 apply the same Factory (outside evaluation), Repository and MergePolicy objects",
      without_evaluation(objs["aws-0"]) == without_evaluation(objs["gcp-0"]))

all_vals = factory_config.values(ROOT)
vals = all_vals["maku-factory"]
check("the factory: policyManagement is {stage: manage}, no switch",
      stage_only(all_vals["config"].get("policyManagement")))
for cfg in sorted(ROOT.glob("infrastructure/*/room-broker/config.yaml")):
    pm = (yaml.safe_load(cfg.read_text()) or {}).get("policyManagement")
    check(f"{cfg.relative_to(ROOT)}: policyManagement.stage manage, no switch", stage_only(pm))

check("maku-factory.enabled renders the controller and its catalog", vals.get("enabled") is True)
cat_cfg = (vals.get("mergePolicies") or {}).get("catalog") or {}
check("mergePolicies.catalog: enabled is true and exclude is [deps-patch]",
      cat_cfg.get("enabled") is True and cat_cfg.get("exclude") == ["deps-patch"])
cat = chart_catalog()
check("chart_catalog(): renders docs-links, revert and docs",
      set(cat) == {"docs-links", "revert", "docs"})

res_dir = ROOT / "tooling/base/agent-factory/resources"
for gone in DELETED_POLICIES:
    check(f"resources/mergepolicy-{gone}.yaml is deleted", not (res_dir / f"mergepolicy-{gone}.yaml").exists())

docs = objs["aws-0"]
kustomize_policies = {d["metadata"]["name"]: d["spec"] for d in docs if d["kind"] == "MergePolicy"}
check("no MergePolicy in resources/ duplicates a non-excluded catalog policy",
      not (set(cat) & set(kustomize_policies)))
check("deps-patch in resources/ keeps monitor.flux, evidence: low, and no requires",
      "deps-patch" in kustomize_policies
      and "flux" in (kustomize_policies["deps-patch"].get("monitor") or {})
      and kustomize_policies["deps-patch"].get("evidence") == "low"
      and "requires" not in kustomize_policies["deps-patch"])

factory = next(d for d in docs if d["kind"] == "Factory")["spec"]
guard = factory_config.guardrails_with_defaults(factory.get("mergeGuardrails"))
merge_defaults = factory.get("mergeDefaults") or {}
check("the Factory sets no minPromotionEvidence (ignored since Maku v0.50.0: evidence is per policy)",
      "minPromotionEvidence" not in (factory.get("mergeGuardrails") or {}))
check("mergeDefaults: maxPerDay, not autoMergesPerDay", "autoMergesPerDay" not in merge_defaults)
check("mergeDefaults: gateStatus is true and policyBot is false (maku/merge-gate is the sole merge gate)",
      merge_defaults.get("gateStatus") is True and merge_defaults.get("policyBot") is False)


def over(spec):
    return [f"{k} {spec[k]} > {guard[k]}" for k in factory_config.CAPS if spec.get(k) and spec[k] > guard[k]]


all_policies = policies(docs)
for name, spec in all_policies.items():
    check(f"MergePolicy/{name}: within the guardrails {over(spec) or ''}", not over(spec))
    check(f"MergePolicy/{name}: no requires or workflow fields",
          "requires" not in spec and not any(k in spec for k in WORKFLOW_FIELDS))

repos = repositories(docs)
for name, spec in repos.items():
    merge = spec.get("merge") or {}
    check(f"Repository/{name}: merge.maxPerDay, not autoMergesPerDay", "autoMergesPerDay" not in merge)
    for b in spec.get("mergePolicies") or []:
        where = f"Repository/{name} binding {b['name']}"
        check(f"{where}: names a known MergePolicy (catalog or resources/)", b["name"] in all_policies)
        check(f"{where}: mode is live or shadow (no off or disabled bindings remain)",
              b.get("mode") in ("live", "shadow"))
        check(f"{where}: within the guardrails {over(b) or ''}", not over(b))
        p = all_policies.get(b["name"], {})
        bounded = b["name"] in BUILT_IN_SHAPE or p.get("diffShape") or p.get("allowedFiles") or b.get("allowedFiles")
        check(f"{where}: bounded (allowedFiles or a diffShape), not Unbounded", bool(bounded))

anr_bindings = {b["name"]: b for b in repos["ai-native-ref"].get("mergePolicies") or []}
check("Repository/ai-native-ref: binds docs in shadow narrowed to ^website/content/.+\\.md$ and 60 lines",
      anr_bindings.get("docs") == {
          "name": "docs",
          "mode": "shadow",
          "allowedFiles": [r"^website/content/.+\.md$"],
          "maxModifiedLines": 60,
      })

cnr_modes = {b["name"]: b["mode"] for b in repos["cloud-native-ref"].get("mergePolicies") or []}
check("Repository/cloud-native-ref: binds docs-links and revert live, and dead-links, deps-patch, deps-minor, alert-rules shadow",
      cnr_modes == {
          "docs-links": "live",
          "revert": "live",
          "alert-rules": "shadow",
          "dead-links": "shadow",
          "deps-patch": "shadow",
          "deps-minor": "shadow",
      })

print(f"==> merge policy surface: {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
