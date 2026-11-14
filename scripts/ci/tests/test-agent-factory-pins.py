#!/usr/bin/env python3
# requires: python3
"""The agent factory's chart and image pins move together, and both by digest.

The chart's appVersion names the image it was built with, so the values' image
tag must be that version (chart `<ver>-pr<N>.g<sha>` ships image
`v<ver>-pr<N>.<sha>`; a release `<ver>` ships `v<ver>`). A tag alone is not a
pin: any same-repo agent-platform PR's CI can re-push it with a valid signature,
so the OCIRepository carries `ref.digest`, which Flux resolves before the tag.
Renovate groups the two (.github/renovate.json); this is what fails when one is
bumped without the other.

The CRDs chart (agent-factory-crds) is the same Maku release, pinned the same way, and the only
owner of the CRDs: it renders them with helm.sh/resource-policy: keep, and the factory's
HelmRelease skips its own crds/. A CRD deleted deletes every object of its kind.
"""
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
problems = []

source = yaml.safe_load((ROOT / "flux/sources/ocirepo-agent-factory.yaml").read_text())
ref = source["spec"]["ref"]
chart_tag = ref.get("tag", "")
if not DIGEST.match(ref.get("digest", "")):
    problems.append(f"OCIRepository agent-factory ref.digest {ref.get('digest')!r} is not sha256:<64 hex>")

cm = yaml.safe_load((ROOT / "tooling/base/agent-factory/helm-values-configmap.yaml").read_text())
image = yaml.safe_load(cm["data"]["values.yaml"])["image"]
version, _, digest = image["tag"].partition("@")
if not DIGEST.match(digest):
    problems.append(f"image tag {image['tag']!r} is not <version>@sha256:<64 hex>")

expected = "v" + re.sub(r"\.g([0-9a-f]+)$", r".\1", chart_tag)
if version != expected:
    problems.append(f"image {version!r} is not chart {chart_tag!r}'s appVersion {expected!r}: bump both")

# The maku names since v0.30.0 (agent-platform renamed); the old ones stop at v0.29.x.
if source["spec"]["url"] != "oci://ghcr.io/smana/charts/maku-factory":
    problems.append(f"OCIRepository agent-factory url {source['spec']['url']!r} is not oci://ghcr.io/smana/charts/maku-factory")
if image.get("repository") != "ghcr.io/smana/maku-factory":
    problems.append(f"image repository {image.get('repository')!r} is not ghcr.io/smana/maku-factory")

crds_dir = ROOT / "tooling/base/agent-factory/crds"
crds_source = yaml.safe_load((crds_dir / "ocirepository.yaml").read_text())
crds_ref = crds_source["spec"]["ref"]
if crds_source["spec"]["url"] != "oci://ghcr.io/smana/charts/agent-factory-crds":
    problems.append(f"OCIRepository agent-factory-crds url {crds_source['spec']['url']!r} is not oci://ghcr.io/smana/charts/agent-factory-crds")
if crds_ref.get("tag") != chart_tag:
    problems.append(f"CRDs chart {crds_ref.get('tag')!r} is not the factory chart {chart_tag!r}: bump both")
if not DIGEST.match(crds_ref.get("digest", "")):
    problems.append(f"OCIRepository agent-factory-crds ref.digest {crds_ref.get('digest')!r} is not sha256:<64 hex>")
if not crds_source["spec"].get("verify"):
    problems.append("OCIRepository agent-factory-crds has no cosign verify")
crds_hr = yaml.safe_load((crds_dir / "helmrelease.yaml").read_text())["spec"]
if (crds_hr.get("values") or {}).get("keep") is not True:
    problems.append("HelmRelease agent-factory-crds: values.keep is not true (helm.sh/resource-policy: keep)")
for phase in ("install", "upgrade"):
    if (crds_hr.get(phase) or {}).get("remediation"):
        problems.append(f"HelmRelease agent-factory-crds: {phase}.remediation set; a remediation must never uninstall or roll back the CRDs")
factory_hr = yaml.safe_load((ROOT / "tooling/base/agent-factory/helmrelease.yaml").read_text())["spec"]
for phase in ("install", "upgrade"):
    if factory_hr.get(phase, {}).get("crds") != "Skip":
        problems.append(f"HelmRelease agent-factory: {phase}.crds is not Skip; agent-factory-crds owns the CRDs")
# room-broker's maku chart ships the Room and AgentRun CRDs in its crds/: two releases must never
# claim one CRD, so it skips them too.
broker_hr = yaml.safe_load((ROOT / "infrastructure/base/room-broker/helmrelease.yaml").read_text())["spec"]
for phase in ("install", "upgrade"):
    if broker_hr.get(phase, {}).get("crds") != "Skip":
        problems.append(f"HelmRelease room-broker: {phase}.crds is not Skip; agent-factory-crds owns the CRDs")
# crd-rooms.yaml hands the Rooms CRD to agent-factory-crds and is never pruned (runbook 26).
rooms = yaml.safe_load((ROOT / "infrastructure/base/room-broker/crd-rooms.yaml").read_text())["metadata"]
want = {"helm.sh/resource-policy": "keep", "kustomize.toolkit.fluxcd.io/prune": "disabled",
        "meta.helm.sh/release-name": "agent-factory-crds", "meta.helm.sh/release-namespace": "agent-system"}
for key, value in want.items():
    if (rooms.get("annotations") or {}).get(key) != value:
        problems.append(f"crd-rooms.yaml: annotation {key} is not {value!r}")
if (rooms.get("labels") or {}).get("app.kubernetes.io/managed-by") != "Helm":
    problems.append("crd-rooms.yaml: label app.kubernetes.io/managed-by is not Helm")

rules = json.loads((ROOT / ".github/renovate.json").read_text())["packageRules"]
names = {"ghcr.io/smana/charts/maku-factory", "ghcr.io/smana/maku-factory"}
if not any(names <= set(r.get("matchPackageNames") or []) and r.get("groupName") for r in rules):
    problems.append("no Renovate packageRule groups the factory's chart and image")

# Human path AM1 and AM7: approve-to-merge and the breaker's recovery are on for every repository.
# The strict decoder refuses both keys on a Maku older than v0.32.0, so they move with the pin.
sys.path.insert(0, str(ROOT / "scripts/ci"))
import factory_config  # noqa: E402  the values file with the Factory, Repository and MergePolicy objects over it
for repo in factory_config.config(ROOT)["repositories"]:
    merge = repo["merge"]
    if merge.get("approveToMerge") is not True:
        problems.append(f"repository {repo['name']}: merge.approveToMerge is not true")
    if merge.get("breaker", {}).get("recoverAfter") != 3:
        problems.append(f"repository {repo['name']}: merge.breaker.recoverAfter is not 3")
    # Maku's validation refuses a leakScanCheck that is not in both lists (K12): `validate` standing in
    # for it would escalate an invalid entry as a live credential.
    leak = merge.get("leakScanCheck")
    if leak and not (leak in merge.get("requiredChecks", []) and leak in merge.get("verifyChecks", [])):
        problems.append(f"repository {repo['name']}: leakScanCheck {leak!r} is not in both requiredChecks and verifyChecks")

for p in problems:
    print(f"FAIL: {p}")
print(f"==> agent-factory pins: chart {chart_tag}, CRDs chart {crds_ref.get('tag')}, image {version}, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
