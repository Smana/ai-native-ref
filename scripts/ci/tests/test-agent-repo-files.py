#!/usr/bin/env python3
# requires: python3
"""This repository as the agent factory's second repository (second-repository design D7, D9).

- Each trust policy is the host's, byte for byte, but for its audience: the issuer, subject and
  permissions never drift wider than the host's, and the audience names this repository.
- The fence names gcp-0, the only live factory.
- .policy.yml: every agent rule excludes the whole gate list, and every sentinel is a gate path.

run-tests.sh runs this from .composite/ (the host's .github/ stays there) with cwd = this repo."""
import pathlib
import re
import sys

import yaml

HOST = pathlib.Path(__file__).resolve().parents[3]
OWN = pathlib.Path.cwd()
REPO = "Smana/ai-native-ref"
ROLES = ["implementer", "reviewer", "tester", "triager"]
SENTINELS = [
    ".policy.yml", ".github/agent-factory.yaml", ".github/chainguard/agent-implementer.sts.yaml",
    ".github/workflows/ci.yaml", "AGENTS.md", ".claude/settings.json", ".agents/skills/x",
    "clusters/aws-0-agent-platform/kustomization.yaml", "flux/sources/ocirepo-agent-factory.yaml",
    "security/base/octo-sts/x", "tooling/base/agent-factory/helm-values-configmap.yaml",
    "tooling/aws-0/agent-factory/x", "infrastructure/base/agent-gateway/x",
    "infrastructure/aws-0/agent-gateway/x", "observability/base/agent-platform/x",
    "scripts/ci/flux-schema/assert-agent-gateway.py", "HOST_REF", "taskfile.yaml",
    ".pre-commit-config.yaml", ".secrets.baseline",
]
fails = []

for role in ROLES:
    rel = f".github/chainguard/agent-{role}.sts.yaml"
    own, host = OWN / rel, HOST / rel
    if not own.is_file() or not host.is_file():
        fails.append(f"{rel}: missing here or on the host")
        continue
    want = host.read_text().replace(
        f"audience: octo-sts/Smana/cloud-native-ref/{role}\n", f"audience: octo-sts/{REPO}/{role}\n")
    if own.read_text() != want:
        fails.append(f"{rel}: differs from the host's beyond the audience octo-sts/{REPO}/{role}")
extra = {p.name for p in (OWN / ".github/chainguard").glob("*.sts.yaml")} - {f"agent-{r}.sts.yaml" for r in ROLES}
if extra:
    fails.append(f"unexpected trust policies: {sorted(extra)}")

fence = OWN / ".github/agent-factory.yaml"
if not fence.is_file() or (yaml.safe_load(fence.read_text()) or {}) != {"factory": "gcp-0"}:
    fails.append(".github/agent-factory.yaml: must be exactly `factory: gcp-0`")

rules = yaml.safe_load((OWN / ".policy.yml").read_text()).get("approval_rules", [])
canon = next((r for r in rules if r.get("name") == "agent change approved by a maintainer"), None)
if canon is None:
    fails.append(".policy.yml: no rule 'agent change approved by a maintainer'")
else:
    gates = canon["if"]["no_changed_files"]["paths"]
    if canon.get("requires", {}).get("users") != ["Smana"] or canon["requires"].get("count", 0) < 1:
        fails.append(".policy.yml: the agent rule must require Smana's review")
    for r in rules:
        users = (r.get("if", {}).get("has_author_in") or {}).get("users", [])
        if any(u.endswith("[bot]") for u in users):
            have = set((r["if"].get("no_changed_files") or {}).get("paths", []))
            if missing := [g for g in gates if g not in have]:
                fails.append(f".policy.yml: rule '{r['name']}' lacks gate paths {missing}")
            if "requires" not in r:
                fails.append(f".policy.yml: agent rule '{r['name']}' approves without a review (no live class here)")
    for s in SENTINELS:
        if not any(re.search(g, s) for g in gates):
            fails.append(f".policy.yml: sentinel {s} is not a gate path")

for x in fails:
    print("FAIL", x)
if fails:
    sys.exit(1)
print("PASS")
