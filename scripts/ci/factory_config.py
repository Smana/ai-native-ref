#!/usr/bin/env python3
"""The agent factory's config as the factory reads it: the values file's `config:` with the
Factory, Repository and MergePolicy objects laid over it (Maku factory resources).

The file (tooling/base/agent-factory/helm-values-configmap.yaml, then a cloud's valuesFrom
ConfigMaps) keeps the plumbing and the startup switches; tooling/base/agent-factory/resources/
holds the catalogue and the repositories. `config()` lays one over the other in the old shape
(`repositories: [{name, classes, merge, ...}]`, `meter.prices`, ...), as Maku's resources.Assemble
merges them, so a suite reads one config whichever side a key lives on. It does not validate:
scripts/ci/validate-factory-config.sh runs the pinned Maku's own `maku config validate` on both.

    render <cloud> <manifests.yaml> <out dir>   writes config.yaml and manifests.yaml, the Flux
                                                variables substituted with placeholders
    config <cloud>                              prints the config the factory reads, in the file's shape,
                                                the same placeholders in (for `maku policy diff --config`)
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "tooling/base/agent-factory"
RESOURCES = f"{BASE}/resources"
VALUES_NAME = "agent-factory-helm-values"
# Maku's resources.CatalogueKeys: the file's top-level keys a Factory replaces.
CATALOGUE = ("control", "defaults", "tiers", "templates", "caps", "budgets", "facts", "brief", "resume",
             "scoper", "loops", "harnessProfiles", "mergeGuardrails", "evaluation", "mergeDefaults")
REPOSITORY_KEYS = ("maintainers", "triggerLabel", "checks", "schedules", "classAuthority")
# The Flux variables these files read, as placeholders the factory's parser accepts.
PLACEHOLDERS = {"private_domain_name": "priv.example.test", "identity_provider_url": "https://auth.example.test"}


def _docs(path):
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def _merge(a, b):
    """Helm's valuesFrom merge: maps deep-merge, anything else is replaced."""
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **{k: _merge(a[k], v) if k in a else v for k, v in b.items()}}
    return b


def values(root=ROOT, cloud=None):
    """The factory's Helm values: base's ConfigMap, then each ConfigMap the cloud's overlay adds to
    the HelmRelease's valuesFrom, in order."""
    root = pathlib.Path(root)
    cms = {}
    dirs = [root / BASE] + ([root / f"tooling/{cloud}/agent-factory"] if cloud else [])
    for d in dirs:
        for f in yaml.safe_load((d / "kustomization.yaml").read_text()).get("resources", []):
            if (d / f).is_file():
                for doc in _docs(d / f):
                    if doc.get("kind") == "ConfigMap" and "values.yaml" in (doc.get("data") or {}):
                        cms[doc["metadata"]["name"]] = yaml.safe_load(doc["data"]["values.yaml"])
    order = [VALUES_NAME]
    if cloud:
        k = yaml.safe_load((root / f"tooling/{cloud}/agent-factory/kustomization.yaml").read_text())
        for p in k.get("patches", []):
            for op in yaml.safe_load(p.get("patch") or "[]") or []:
                if isinstance(op, dict) and op.get("path") == "/spec/valuesFrom/-":
                    order.append(op["value"]["name"])
    out = {}
    for name in order:
        out = _merge(out, cms[name])
    return out


def objects(root=ROOT):
    """The Factory, Repository and MergePolicy objects of the resources directory, unrendered."""
    d = pathlib.Path(root) / RESOURCES
    return [doc for f in yaml.safe_load((d / "kustomization.yaml").read_text())["resources"] for doc in _docs(d / f)]


# Reusable merge policies, the B4 table: how a class-shape MergePolicy and one Repository's binding
# of it resolve into the class the gate decides on, as Maku's config.Resolve does (the refusals are
# Maku's to make: scripts/ci/tests/test-agent-resolved-classes.sh compares the two).
FILL_ONCE = ("allowedFiles", "companionFiles", "requiredLabel")
ADDITIVE = ("holdoutChecks", "protectedFiles")
CAPS = ("maxPatchFiles", "maxModifiedLines", "maxPerDay")


def resolve(policy, binding, merge, guardrails=None):
    """The class a binding resolves to (B4, B14): the policy's meaning, the binding's mode, each
    fill-once parameter from where it is set, the additive lists unioned, the lower cap, the
    repository's Flux source, then the guardrails."""
    cl = {k: v for k, v in (policy or {}).items() if k != "requires"}
    cl = yaml.safe_load(yaml.safe_dump(cl))  # a deep copy: consumers never share a list
    mode = binding.get("mode")
    if mode == "live":
        cl["live"] = True
    elif mode == "shadow":
        cl["shadow"] = True
    for k in FILL_ONCE:
        if binding.get(k):
            cl[k] = binding[k]
    if binding.get("oracleWorkflow") and cl.get("oracle") is not None:
        cl["oracle"] = {**cl["oracle"], "workflow": binding["oracleWorkflow"]}
    for k in ADDITIVE:
        items = list(cl.get(k) or [])
        items += [x for x in binding.get(k) or [] if x not in items]
        if items:
            cl[k] = items
    approvals = list(cl.get("requiresApproval") or [])
    approvals += [a for a in binding.get("requiresApproval") or [] if a not in approvals]
    if approvals:
        cl["requiresApproval"] = approvals
    for k in CAPS:
        if binding.get(k):
            cl[k] = binding[k] if not cl.get(k) else min(cl[k], binding[k])
    flux = (cl.get("monitor") or {}).get("flux")
    if flux is not None and merge.get("fluxSource"):
        flux["source"] = merge["fluxSource"]
    g = guardrails or {}
    for k, into in (("protectedFiles", "protectedFiles"), ("mandatoryChecks", "holdoutChecks")):
        items = list(cl.get(into) or [])
        items += [x for x in g.get(k) or [] if x not in items]
        if items:
            cl[into] = items
    for k in CAPS:
        if g.get(k) and not cl.get(k):
            cl[k] = g[k]
    return cl


def merge_settings(defaults, merge):
    """A repository's merge with the Factory's mergeDefaults filled in, key by key (Q8)."""
    return {**(defaults or {}), **(merge or {})}


def assemble(cfg, objs):
    """cfg with objs laid over it, as resources.Assemble merges them (nothing refused, nothing validated)."""
    m = {k: v for k, v in cfg.items()}
    for f in (o for o in objs if o["kind"] == "Factory"):
        for k in CATALOGUE:
            m.pop(k, None)
        for k, v in f["spec"].items():
            if k == "prices":
                m["meter"] = {**(m.get("meter") or {}), "prices": v}
            elif k == "triage" and isinstance(v, dict):
                m["triage"] = {**(m.get("triage") or {}), **v}
            else:
                m[k] = v
    mps = [o for o in objs if o["kind"] == "MergePolicy"]
    classes = {o["metadata"]["name"]: o["spec"] for o in mps}
    repos = sorted((o for o in objs if o["kind"] == "Repository"), key=lambda o: o["metadata"]["name"])
    listed = list(m.get("repositories") or [])
    for r in repos:
        entry = {"name": r["spec"]["repository"]}
        entry.update({k: r["spec"][k] for k in REPOSITORY_KEYS if k in r["spec"]})
        if "merge" in r["spec"] or "mergePolicies" in r["spec"]:
            # Bound (B2, B3): the Repository's own merge over the defaults, and each binding resolved.
            # Maku v0.48.0 removed the per-repository MergePolicy: a binding is the only shape.
            entry["merge"] = merge_settings(m.get("mergeDefaults"), r["spec"].get("merge"))
            entry["classes"] = {b["name"]: resolve(classes.get(b["name"]), b, entry["merge"], m.get("mergeGuardrails"))
                                for b in r["spec"].get("mergePolicies") or [] if b["name"] in classes}
        listed.append(entry)
    m["repositories"] = listed
    return m


def config(root=ROOT, cloud=None):
    """The factory's config as it reads it: the file's `config:` with the objects laid over it."""
    return assemble(values(root, cloud)["config"], objects(root))


def substitute(text, cloud):
    """Flux's ${var}, as placeholders; a variable with none fails, so nothing is left to the parser."""
    subs = dict(PLACEHOLDERS, cluster_name=cloud)

    def one(m):
        if m.group(1) not in subs:
            raise SystemExit(f"no placeholder for ${{{m.group(1)}}}")
        return subs[m.group(1)]
    return re.sub(r"\$\{(\w+)\}", one, text)


def render(cloud, manifests, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(substitute(yaml.safe_dump(values(ROOT, cloud)["config"], allow_unicode=True), cloud))
    (out / "manifests.yaml").write_text(substitute(pathlib.Path(manifests).read_text(), cloud))


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "render":
        render(*sys.argv[2:])
    elif len(sys.argv) == 3 and sys.argv[1] == "config":
        sys.stdout.write(substitute(yaml.safe_dump(config(ROOT, sys.argv[2]), allow_unicode=True, sort_keys=False), sys.argv[2]))
    else:
        sys.exit(__doc__)
