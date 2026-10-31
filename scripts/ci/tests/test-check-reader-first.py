#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/check-reader-first.py, the gate that keeps session history off the site.

Each case writes pages into a temporary website/content/docs/ and checks what the gate reports:
a clean page, one finding per rule, and every place the text is allowed to sit.

Run: python3 scripts/ci/tests/test-check-reader-first.py
"""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("check_reader_first", ROOT / "scripts/ci/check-reader-first.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

FAILURES = []


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def rules(text):
    return [rule for _, rule, _ in gate.scan(text)]


def run(pages):
    """main() over a tree holding these pages: (exit code, output)."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel, text in pages.items():
            page = pathlib.Path(tmp, "website/content/docs", rel)
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gate.main(["check-reader-first.py", tmp])
        return code, out.getvalue()


CLEAN = """---
title: Your first task
lastVerified: 2026-10-30
---

You put the label `factory/ready` on an issue. The factory runs on an L4 GPU node and keeps the
weights in S3; the gateway budgets B1 and B2 count every call.
"""

print("a page that passes")
code, out = run({"use/first-task.md": CLEAN})
check("a clean page exits 0", code == 0, out)
check("front matter's lastVerified is not read", rules(CLEAN) == [])

print("a page that fails")
BAD = """---
title: Bad
---

The factory ran on aws-0 on 2026-10-29, proven live after @Smana's review.
Gate AG8 and SP4 R13 hold it; N6 and the live check L3 too.
"""
code, out = run({"use/bad.md": BAD})
check("a page with history exits 1", code == 1, out)
check("the finding names the file and line", "website/content/docs/use/bad.md:5\tcluster name\taws-0" in out, out)
check("every rule fires",
      sorted(set(rules(BAD))) == ["cluster name", "date", "handle", "proof ID", "proven live"], str(rules(BAD)))
check("each proof ID is found", [h for _, r, h in gate.scan(BAD) if r == "proof ID"] == ["AG8", "SP4 R13", "N6", "L3"],
      str(gate.scan(BAD)))
check("a cluster name in inline code is still one", rules("Run it on `gcp-0`.\n") == ["cluster name"])
check("a table row is read", rules("| Cluster | aws-0 |\n") == ["cluster name"])
check("an e-mail address is not a handle", rules("Write to owner@example.com.\n") == [])
check("a scoped npm package is not a handle", rules("OpenCode wants @ai-sdk/openai instead.\n") == [])

print("the allowed places")
code, out = run({"status.md": BAD, "decisions/0001-x.md": BAD, "use/first-task.md": CLEAN})
check("the status page and the decision records are not read", code == 0, out)
check("a fenced block is not read", rules("Run:\n\n```bash\nkubectl --context aws-0 get pods  # 2026-10-29\n```\n") == [])
check("a tilde fence is not read", rules("~~~\n@Smana on gcp-0\n~~~\n") == [])
check("the block after a fence is read again",
      rules("Example (the reference host):\n\n```\nx\n```\n\nThe factory ran on aws-0.\n") == ["cluster name"])
check("the rest of a paragraph after the label is an example",
      rules("Each cloud has one cluster. Example (the reference host): `aws-0`\nand `gcp-0`.\n") == [])
check("text before the label is read",
      rules("On aws-0, for example. Example (the reference host): `gcp-0`.\n") == ["cluster name"])
check("the block after a labelled paragraph ending with a colon is an example",
      rules("Example (the reference host), one cluster per cloud:\n\n| aws-0 | x |\n| gcp-0 | y |\n") == [])
check("only that one block",
      rules("Example (the reference host):\n\n| aws-0 | x |\n\nNow on gcp-0.\n") == ["cluster name"])
check("a label in a table row covers that row only",
      rules("| a | (example (the reference host): aws-0) |\n| b | gcp-0 |\n") == ["cluster name"])
check("a label in a list item covers that item only",
      rules("- one, example (the reference host): aws-0\n- two on gcp-0\n") == ["cluster name"])
check("the block after an <!-- example --> line is an example",
      rules("<!-- example -->\nThe task ran on aws-0 on 2026-10-07 after @Smana's review.\n\nThen aws-0.\n")
      == ["cluster name"])
check("a link target is not read",
      rules("See [runbook 14](https://github.com/o/r/blob/main/docs/runbooks/14-gcp-0-2026-10-18.md).\n") == [])
check("a reference link definition is not read",
      rules("See [the results][r].\n\n[r]: https://example.com/results-aws-0-2026-10-30.md\n") == [])
check("a bare URL is not read", rules("<https://example.com/2026-10-20-research.md>\n") == [])
check("a relref shortcode is not read",
      rules('[spec]({{< relref "/docs/specs/2026-10-18-cost.md" >}})\n') == [])
check("the link text is read", rules("[v1 review, 2026-10-12](https://example.com/x)\n") == ["date"])
check("a repository path in backticks is not read",
      rules("The paths are under `clusters/aws-0/flux/` and `infrastructure/gcp-0/x.yaml`.\n") == [])
check("a handle in inline code is literal text", rules("Mention `@factory link` in the channel.\n") == [])

print()
if FAILURES:
    print(f"{len(FAILURES)} failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("all passed")
