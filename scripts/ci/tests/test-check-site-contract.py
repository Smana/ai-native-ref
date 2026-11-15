#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/check-site-contract.py, the gate that holds the site's contract.

Each case writes a minimal repository tree into a temporary directory and checks what
check-site-contract.py reports.

Run: python3 scripts/ci/tests/test-check-site-contract.py
"""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
TARGET = ROOT / "scripts/ci/check-site-contract.py"
spec = importlib.util.spec_from_file_location("check_site_contract", TARGET)
if spec is None or spec.loader is None or not TARGET.is_file():
    sys.exit(f"missing {TARGET}")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

FAILURES = []
STATE = {}


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def tree(*, hugo=None, values=None, fence=None, status=None, pages=None):
    STATE.clear()
    files = {}
    if hugo is not None:
        files["website/hugo.yaml"] = hugo
    if values is not None:
        files["tooling/base/agent-factory/helm-values-configmap.yaml"] = values
    if fence is not None:
        files[".github/agent-factory.yaml"] = fence
    if status is not None:
        files["website/content/docs/status.md"] = status
    if pages:
        for rel, text in pages.items():
            files[f"website/content/docs/{rel}"] = text
    STATE["files"] = files


def page(rel, body, *, front=None):
    files = STATE.setdefault("files", {})
    text = f"---\n{front}\n---\n\n{body}" if front is not None else body
    if rel == "README.md":
        files["README.md"] = text
    else:
        files[f"website/content/docs/{rel}"] = text


def run():
    files = STATE.pop("files", {})
    with tempfile.TemporaryDirectory() as tmp:
        for rel, text in files.items():
            path = pathlib.Path(tmp, rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = contract.main(["check-site-contract.py", tmp])
        STATE["code"] = code
        return out.getvalue()


print("pin matches chart image tag")
tree(hugo="params:\n  makuVersion: v0.46.0\n", values='tag: "v0.47.0@sha256:abc"\n')
out = run()
check("mismatched pin fails", "pin: v0.46.0 != v0.47.0" in out and STATE["code"] == 1, out)

tree(hugo="title: AI Native Reference\n", values='tag: "v0.50.0@sha256:abc"\n')
out = run()
check("unset pin fails", "pin: <unset> != v0.50.0" in out and STATE["code"] == 1, out)

tree(hugo="params:\n  makuVersion: v0.50.0\n", values='tag: "v0.50.0@sha256:abc"\n')
out = run()
check("matching pin passes", "pin" not in out and STATE["code"] == 0, out)

print("active cluster matches ownership fence")
tree(fence="factory: aws-0\n", status="---\nactiveCluster: gcp-0\n---\n")
out = run()
check("mismatched activeCluster front matter fails", "active cluster: gcp-0 != aws-0" in out and STATE["code"] == 1, out)

tree(fence="factory: gcp-0\n", status="---\ntitle: Status\n---\n")
out = run()
check("unset activeCluster fails", "active cluster: <unset> != gcp-0" in out and STATE["code"] == 1, out)

tree(fence="factory: gcp-0\n", status="---\nactiveCluster: gcp-0\n---\n\nActive: `aws-0`\n")
out = run()
check("mismatched Active line in body fails", "active cluster: aws-0 != gcp-0" in out and STATE["code"] == 1, out)

tree(fence="factory: gcp-0\n", status="---\nactiveCluster: gcp-0\n---\n\nActive: `gcp-0`\n")
out = run()
check("matching activeCluster and Active line pass", "active cluster" not in out and STATE["code"] == 0, out)

print("product name and Maku version rules")
page("use/x.md", "The Agent Factory opened a pull request.\n")
out = run()
check("Agent Factory as a product is refused", "use/x.md:1: product name: Agent Factory" in out and STATE["code"] == 1, out)

page("status.md", "The Agent Factory is a bundle of open-source tools.\n")
out = run()
check("Agent Factory on status.md is also refused", "status.md:1: product name: Agent Factory" in out and STATE["code"] == 1, out)

page("README.md", "# Title\n\nThe Agent Factory runs Maku v0.47.0.\n")
out = run()
check(
    "README.md is scanned for product name and maku version",
    "README.md:3: product name: Agent Factory" in out and "README.md:3: maku version: Maku v0.47.0" in out and STATE["code"] == 1,
    out,
)

page("use/x.md", "Released as Agent Factory v3.0.0 and Agent Factory [v2](u).\n")
out = run()
check("release names Agent Factory v0-v3 pass", "product name" not in out and STATE["code"] == 0, out)

page("use/x.md", "Runs Maku v0.47.0. Uses agentgateway v1.6.0.\n")
out = run()
check(
    "Maku version refused outside status while other tools pass",
    "use/x.md:1: maku version: Maku v0.47.0" in out and "agentgateway" not in out and STATE["code"] == 1,
    out,
)

page("use/x.md", "See [spec](https://github.com/Smana/maku/blob/v0.47.0/docs/cli.md) and [tag](https://github.com/Smana/maku/releases/tag/v0.50.0).\n")
out = run()
check(
    "Maku version in URL link targets is refused outside status",
    "use/x.md:1: maku version: Smana/maku/blob/v0.47.0" in out
    and "use/x.md:1: maku version: Smana/maku/releases/tag/v0.50.0" in out
    and STATE["code"] == 1,
    out,
)

page("use/x.md", "```\nThe Agent Factory runs Maku v0.47.0\n```\n", front="title: The Agent Factory\n")
out = run()
check("front matter and fenced code are skipped", STATE["code"] == 0, out)

page("status.md", "Maku v0.47.0 and [v0.50.0](https://github.com/Smana/maku/releases/tag/v0.50.0)\n")
page("decisions/0001.md", "The Agent Factory, Maku v0.30.0\n")
out = run()
check("status.md allows maku version and decisions/ allows both", STATE["code"] == 0, out)

print()
if FAILURES:
    print(f"{len(FAILURES)} failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("all passed")
