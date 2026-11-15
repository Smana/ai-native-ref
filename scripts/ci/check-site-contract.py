#!/usr/bin/env python3
"""Holds the documentation site's contract with the manifests (docs/docs-style.md).

Rules checked here:
- pin: params.makuVersion in website/hugo.yaml equals the Maku image tag in
  tooling/base/agent-factory/helm-values-configmap.yaml.
- active cluster: activeCluster (and any Active: <cluster> line) on
  website/content/docs/status.md equals factory in .github/agent-factory.yaml.

  python3 scripts/ci/check-site-contract.py [ROOT]

Exit 0: no finding. Exit 1: each finding is printed as file:line: <rule>: <match>.
"""
import pathlib
import re
import sys

HUGO_CONFIG = pathlib.PurePosixPath("website/hugo.yaml")
HELM_VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
FENCE_FILE = pathlib.PurePosixPath(".github/agent-factory.yaml")
STATUS_PAGE = pathlib.PurePosixPath("website/content/docs/status.md")

TAG_RE = re.compile(r'^\s*tag:\s*["\']?(v[0-9]+\.[0-9]+\.[0-9]+)(?:@[^"\'\s]*)?["\']?\s*(?:#.*)?$', re.M)
MAKU_VERSION_RE = re.compile(r'^\s*makuVersion:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$')
FENCE_RE = re.compile(r'^\s*factory:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$', re.M)
ACTIVE_CLUSTER_FM_RE = re.compile(r'^\s*activeCluster:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$')
ACTIVE_CLUSTER_BODY_RE = re.compile(r'^\s*(?:\*\*)?Active:(?:\*\*)?\s*`?((?:aws|gcp)-[0-9]+)`?\b')
FENCE_BLOCK_RE = re.compile(r"^\s*(```|~~~)")


def check_pin(root: pathlib.Path) -> list[str]:
    values_path = root / HELM_VALUES
    if not values_path.is_file():
        return []
    m = TAG_RE.search(values_path.read_text(encoding="utf-8"))
    if not m:
        return [f"{HELM_VALUES}:1: pin: no tag found"]
    want = m.group(1)

    hugo_path = root / HUGO_CONFIG
    got = "<unset>"
    lineno = 1
    if hugo_path.is_file():
        for idx, line in enumerate(hugo_path.read_text(encoding="utf-8").splitlines(), 1):
            hm = MAKU_VERSION_RE.match(line)
            if hm:
                got = hm.group(1)
                lineno = idx
                break
    if got != want:
        return [f"{HUGO_CONFIG}:{lineno}: pin: {got} != {want}"]
    return []


def check_active_cluster(root: pathlib.Path) -> list[str]:
    fence_path = root / FENCE_FILE
    if not fence_path.is_file():
        return []
    m = FENCE_RE.search(fence_path.read_text(encoding="utf-8"))
    if not m:
        return [f"{FENCE_FILE}:1: active cluster: no factory found"]
    want = m.group(1)

    status_path = root / STATUS_PAGE
    got = "<unset>"
    lineno = 1
    body_start = 0
    lines: list[str] = []
    if status_path.is_file():
        lines = status_path.read_text(encoding="utf-8").splitlines()
        if lines and lines[0].strip() == "---":
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
            if end:
                body_start = end + 1
                for idx in range(1, end):
                    am = ACTIVE_CLUSTER_FM_RE.match(lines[idx])
                    if am:
                        got = am.group(1)
                        lineno = idx + 1
                        break

    findings: list[str] = []
    if got != want:
        findings.append(f"{STATUS_PAGE}:{lineno}: active cluster: {got} != {want}")

    fence_marker = None
    for idx in range(body_start, len(lines)):
        line = lines[idx]
        fm = FENCE_BLOCK_RE.match(line)
        if fence_marker:
            if fm and fm.group(1) == fence_marker:
                fence_marker = None
            continue
        if fm:
            fence_marker = fm.group(1)
            continue
        bm = ACTIVE_CLUSTER_BODY_RE.match(line)
        if bm and bm.group(1) != want:
            findings.append(f"{STATUS_PAGE}:{idx + 1}: active cluster: {bm.group(1)} != {want}")
    return findings


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else pathlib.Path(__file__).resolve().parents[2])
    findings = check_pin(root) + check_active_cluster(root)
    if findings:
        for finding in findings:
            print(finding)
        print(f"\n==> {len(findings)} finding(s): site contract broken (docs/docs-style.md).")
        return 1
    print("==> Site contract holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
