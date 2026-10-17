#!/usr/bin/env python3
# requires: python3 kustomize
"""On gcp-0 ZITADEL is served by the cluster's own Gateway VIP, where a CiliumNetworkPolicy
rule with any toPorts never matches (ruling AU; the measurement is in the host's
tooling/gcp-0/headlamp/network-policy.yaml). So every policy that reaches the IdP on aws-0
must, on gcp-0, name no IdP FQDN and carry a portless `toEntities: [all]` rule instead.
The consumers are found from aws-0's renders, so a new one cannot be forgotten."""
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
IDP = "auth.${public_domain_name}"


def render_roots(cluster):
    roots = set()
    for child in sorted(ROOT.glob(f"clusters/{cluster}-*/*.yaml")):
        for d in yaml.safe_load_all(child.read_text()):
            path = ((d or {}).get("spec") or {}).get("path", "")
            if d and d.get("kind") == "Kustomization" and path and not path.startswith("./clusters/"):
                roots.add(path.removeprefix("./"))
    return sorted(roots)


def policies(cluster):
    found = {}
    for root in render_roots(cluster):
        out = subprocess.run(["kustomize", "build", str(ROOT / root)], capture_output=True, text=True)
        if out.returncode:
            print(f"  FAIL {cluster}: kustomize build {root}: {out.stderr.strip()}")
            sys.exit(1)
        for d in yaml.safe_load_all(out.stdout):
            if d and d["kind"] == "CiliumNetworkPolicy":
                found[(d["metadata"].get("namespace"), d["metadata"]["name"])] = (root, d["spec"].get("egress") or [])
    return found


def names_idp(rule):
    return any(IDP in (f.get("matchName", "") + f.get("matchPattern", "")) for f in rule.get("toFQDNs") or [])


aws, gcp = policies("aws-0"), policies("gcp-0")
consumers = sorted(k for k, (_, egress) in aws.items() if any(names_idp(r) for r in egress))

checks = {"aws-0 has IdP consumers to check": bool(consumers)}
for key in consumers:
    label = "/".join(key)
    if key not in gcp:
        checks[f"{label}: not rendered on gcp-0 (no IdP rule to fix)"] = True
        continue
    root, egress = gcp[key]
    checks[f"{label} ({root}): no IdP FQDN rule on gcp-0"] = not any(names_idp(r) for r in egress)
    checks[f"{label} ({root}): a portless toEntities all rule"] = any(
        r.get("toEntities") == ["all"] and "toPorts" not in r for r in egress)
for key, (root, egress) in sorted(gcp.items()):
    if key not in consumers and any(names_idp(r) for r in egress):
        checks[f"{'/'.join(key)} ({root}): names the IdP on gcp-0 with no aws-0 twin"] = False

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
