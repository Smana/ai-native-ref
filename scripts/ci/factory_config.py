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
             "scoper", "loops", "harnessProfiles", "mergeGuardrails", "evaluation")
REPOSITORY_KEYS = ("maintainers", "triggerLabel", "checks", "schedules", "classAuthority")
POLICY_KEYS = ("classes", "merge")
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
    policies = {o["spec"]["repositoryRef"]: o for o in objs if o["kind"] == "MergePolicy"}
    repos = sorted((o for o in objs if o["kind"] == "Repository"), key=lambda o: o["metadata"]["name"])
    listed = list(m.get("repositories") or [])
    for r in repos:
        entry = {"name": r["spec"]["repository"]}
        entry.update({k: r["spec"][k] for k in REPOSITORY_KEYS if k in r["spec"]})
        p = policies.get(r["metadata"]["name"], {}).get("spec", {})
        entry.update({k: p[k] for k in POLICY_KEYS if k in p})
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
