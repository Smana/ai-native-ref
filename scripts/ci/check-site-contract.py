#!/usr/bin/env python3
"""Holds the documentation site's contract with the manifests (docs/docs-style.md).

Rules checked here:
- pin: params.makuVersion in website/hugo.yaml equals the Maku image tag in
  tooling/base/agent-factory/helm-values-configmap.yaml.
- active cluster: activeCluster (and any Active: <cluster> line) on
  website/content/docs/status.md equals factory in .github/agent-factory.yaml.
- product name: "Agent Factory" outside release names (Agent Factory v0..v3) is
  refused outside decisions/.
- maku version: a Maku version literal or versioned Maku GitHub URL is refused
  outside status.md and decisions/.
- raw maku link: a raw github.com/Smana/maku/(blob|tree)/ link in a page source
  is refused outside decisions/ (use the maku shortcode instead).
- ceiling: every page that declares diataxis: in front matter obeys its body
  word ceiling (chapter 600, values 500, tutorial/how-to 1200, explanation 1500,
  reference none; front matter and fenced code excluded).

  python3 scripts/ci/check-site-contract.py [--report] [ROOT]

Exit 0: no finding (or --report). Exit 1: each finding is printed on stdout.
"""
import importlib.util
import pathlib
import re
import sys


def _load_reader_first():
    path = pathlib.Path(__file__).with_name("check-reader-first.py")
    spec = importlib.util.spec_from_file_location("check_reader_first", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reader_first = _load_reader_first()

HUGO_CONFIG = pathlib.PurePosixPath("website/hugo.yaml")
HELM_VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
FENCE_FILE = pathlib.PurePosixPath(".github/agent-factory.yaml")
STATUS_PAGE = pathlib.PurePosixPath("website/content/docs/status.md")

CEILINGS: dict[str, int | None] = {
    "chapter": 600,
    "values": 500,
    "tutorial": 1200,
    "how-to": 1200,
    "explanation": 1500,
    "reference": None,
}

TAG_RE = re.compile(r'^\s*tag:\s*["\']?(v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?)(?:@[^"\'\s]*)?["\']?\s*(?:#.*)?$', re.M)
MAKU_VERSION_RE = re.compile(r'^\s*makuVersion:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$')
FENCE_RE = re.compile(r'^\s*factory:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$', re.M)
ACTIVE_CLUSTER_FM_RE = re.compile(r'^\s*activeCluster:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$')
ACTIVE_CLUSTER_BODY_RE = re.compile(r'^\s*(?:\*\*)?Active:(?:\*\*)?\s*`?((?:aws|gcp)-[0-9]+)`?\b')
DIATAXIS_FM_RE = re.compile(r'^\s*diataxis:\s*["\']?(\S+?)["\']?\s*(?:#.*)?$')

PRODUCT_NAME_RE = re.compile(r"Agent Factory(?! \[?v[0-3]\b)")
MAKU_VERSION_TEXT_RE = re.compile(r"Maku v0\.\d+\.\d+")
MAKU_VERSION_URL_RE = re.compile(r"Smana/maku/(?:blob|tree|releases/tag)/v0\.\d+\.\d+")
RAW_MAKU_LINK_RE = re.compile(r"github\.com/Smana/maku/(?:blob|tree)/\S+")


def split_page(text: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Return (front_matter_lines, body_lines_outside_fences) with 1-based line numbers."""
    lines = text.splitlines()
    front: list[tuple[int, str]] = []
    start = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        if end:
            front = [(i + 1, lines[i]) for i in range(1, end)]
            start = end + 1

    body: list[tuple[int, str]] = []
    fence_marker = None
    for idx in range(start, len(lines)):
        line = lines[idx]
        fm = reader_first.FENCE.match(line)
        if fence_marker:
            if fm and fm.group(1) == fence_marker:
                fence_marker = None
            continue
        if fm:
            fence_marker = fm.group(1)
            continue
        body.append((idx + 1, line))
    return front, body


def _page_type_and_words(text: str) -> tuple[str | None, int]:
    front, body = split_page(text)
    dtype = None
    for _, line in front:
        dm = DIATAXIS_FM_RE.match(line)
        if dm:
            dtype = dm.group(1)
            break
    words = sum(len(line.split()) for _, line in body)
    return dtype, words


def check_pin(root: pathlib.Path) -> list[str]:
    values_path = root / HELM_VALUES
    if not values_path.is_file():
        return []
    m = TAG_RE.search(values_path.read_text(encoding="utf-8"))
    if not m:
        return [f"{HELM_VALUES}:1: pin: no tag found"]
    want = m.group(1)
    # Validation branches run signed prereleases without making an unreleased
    # version the public documentation's release pin. Release pins stay exact.
    if "-pr" in want:
        return []

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
    body: list[tuple[int, str]] = []
    if status_path.is_file():
        front, body = split_page(status_path.read_text(encoding="utf-8"))
        for fm_line, text in front:
            am = ACTIVE_CLUSTER_FM_RE.match(text)
            if am:
                got = am.group(1)
                lineno = fm_line
                break

    findings: list[str] = []
    if got != want:
        findings.append(f"{STATUS_PAGE}:{lineno}: active cluster: {got} != {want}")

    for b_line, line in body:
        bm = ACTIVE_CLUSTER_BODY_RE.match(line)
        if bm and bm.group(1) != want:
            findings.append(f"{STATUS_PAGE}:{b_line}: active cluster: {bm.group(1)} != {want}")
    return findings


def _scan_page_vocabulary(rel_display: str, text: str, *, skip_version: bool, check_raw_maku: bool) -> list[str]:
    _, body = split_page(text)
    findings: list[str] = []
    for lineno, line in body:
        clean = reader_first.unexempt(line)
        for hit in PRODUCT_NAME_RE.finditer(clean):
            findings.append(f"{rel_display}:{lineno}: product name: {hit.group(0)}")
        if not skip_version:
            for hit in MAKU_VERSION_TEXT_RE.finditer(clean):
                findings.append(f"{rel_display}:{lineno}: maku version: {hit.group(0)}")
            for hit in MAKU_VERSION_URL_RE.finditer(line):
                findings.append(f"{rel_display}:{lineno}: maku version: {hit.group(0)}")
        if check_raw_maku:
            for hit in RAW_MAKU_LINK_RE.finditer(line):
                findings.append(f"{rel_display}:{lineno}: raw maku link: {hit.group(0).rstrip(').,;')}")
    return findings


def check_vocabulary(root: pathlib.Path) -> list[str]:
    findings: list[str] = []
    readme = root / "README.md"
    if readme.is_file():
        findings.extend(
            _scan_page_vocabulary(
                "README.md",
                readme.read_text(encoding="utf-8"),
                skip_version=False,
                check_raw_maku=False,
            )
        )

    docs = root / reader_first.DOCS
    if docs.is_dir():
        for page in sorted(docs.rglob("*.md")):
            rel = page.relative_to(docs).as_posix()
            if rel == "decisions" or rel.startswith("decisions/"):
                continue
            findings.extend(
                _scan_page_vocabulary(
                    f"{reader_first.DOCS}/{rel}",
                    page.read_text(encoding="utf-8"),
                    skip_version=(rel == "status.md"),
                    check_raw_maku=True,
                )
            )
    return findings


def check_ceilings(root: pathlib.Path) -> list[str]:
    findings: list[str] = []
    docs = root / reader_first.DOCS
    if not docs.is_dir():
        return findings
    for page in sorted(docs.rglob("*.md")):
        rel = page.relative_to(docs).as_posix()
        dtype, words = _page_type_and_words(page.read_text(encoding="utf-8"))
        if dtype is None:
            continue
        if dtype not in CEILINGS:
            findings.append(f"{reader_first.DOCS}/{rel}: ceiling: unknown diataxis: {dtype}")
            continue
        limit = CEILINGS[dtype]
        if limit is not None and words > limit:
            findings.append(f"{reader_first.DOCS}/{rel}: ceiling: {words} words, {dtype} allows {limit}")
    return findings


def report_words(root: pathlib.Path) -> int:
    docs = root / reader_first.DOCS
    if not docs.is_dir():
        return 0
    for page in sorted(docs.rglob("*.md")):
        rel = page.relative_to(docs).as_posix()
        dtype, words = _page_type_and_words(page.read_text(encoding="utf-8"))
        print(f"{words:6d}  {dtype or '-':12s}  {rel}")
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    report = False
    if "--report" in args:
        report = True
        args = [a for a in args if a != "--report"]
    root = pathlib.Path(args[0] if args else pathlib.Path(__file__).resolve().parents[2])
    if report:
        return report_words(root)

    findings = check_pin(root) + check_active_cluster(root) + check_vocabulary(root) + check_ceilings(root)
    if findings:
        for finding in findings:
            print(finding)
        print(f"\n==> {len(findings)} finding(s): site contract broken (docs/docs-style.md).")
        return 1
    print("==> Site contract holds.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
