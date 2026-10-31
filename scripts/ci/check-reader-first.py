#!/usr/bin/env python3
"""Keeps the site's pages free of session history (docs/docs-style.md, rule 18).

A page on airef.ogenki.io is written for someone who was not there: no cluster names, no session
dates, no "proven live", no people's handles and no proof IDs. This fails on any of them in
website/content/docs/**/*.md, except where such text belongs. The exceptions are structural,
by where the text sits, never a list of lines:

- the status page (status.md) and the decision records (decisions/);
- front matter (`lastVerified`, `date`);
- fenced code blocks;
- a labelled example: the rest of a paragraph, table row or list item after "Example (the
  reference host)", the block after one that ends with ":", and the block after an
  `<!-- example -->` line;
- link targets: `](url)`, `[ref]: url`, bare URLs and Hugo shortcodes such as relref;
- repository paths in backticks, the ones scripts/ci/verify-doc-paths.sh checks
  (`clusters/aws-0/…`).

  python3 scripts/ci/check-reader-first.py [ROOT]

Exit 0: no finding. Exit 1: each finding is printed as file:line, the rule and the match.
"""
import pathlib
import re
import sys

DOCS = pathlib.PurePosixPath("website/content/docs")
RECORDS = ("status.md", "decisions/")

# (name, pattern, read inside inline code). A handle in inline code is the literal text a reader
# types or sees, such as the Slack app's `@factory link`; a cluster name or a date there is not.
RULES = (
    ("cluster name", re.compile(r"\b(?:aws|gcp)-0\b"), True),
    ("date", re.compile(r"\b20[0-9]{2}-[01][0-9]-[0-3][0-9]\b"), True),
    ("proven live", re.compile(r"\bproven live\b", re.I), True),
    # Not an e-mail address or a scoped npm package (`@scope/pkg`).
    ("handle", re.compile(r"(?<![\w.@/-])@[A-Za-z][\w-]*(?![\w/@-])"), False),
    # Plan, gate and proof IDs: N6, AM4, F11, SP4 R13, AG8, D4, C7, OD-6, the live checks L1-L8.
    # L4 (the GPU) and L7 (the network layer) are names a reader knows, not IDs; nor are S3, K3
    # or the B1/B2/B6 budgets, which the gateway page defines.
    ("proof ID", re.compile(r"\b(?:SP[0-9]+(?: [A-Z][0-9]+)?|AM[0-9]+|AG[0-9]+|OD-[0-9]+|[CDFN][0-9]+|L[0-35689])\b"), True),
)

# Paths start with the top-level directories verify-doc-paths.sh knows.
TOP = ("apps/", "clusters/", "container-images/", "crds/", "docs/", "flux/", "infrastructure/",
       "namespaces/", "observability/", "opentofu/", "scripts/", "security/", "tooling/",
       "website/", ".github/", ".claude/")
LABEL = re.compile(r"example \(the reference host\)", re.I)
MARKER = re.compile(r"^\s*<!--\s*example\s*-->\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
ITEM = re.compile(r"^\s*(?:[-*+]|[0-9]+\.)\s")
STRIP = (
    re.compile(r"\{\{[<%].*?[%>]\}\}"),                  # shortcodes: relref, figure src, card link
    re.compile(r"(?<=\])\([^)\s]*(?:\s+\"[^\"]*\")?\)"),  # inline link targets
    re.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$"),               # reference link definitions
    re.compile(r"<?https?://[^\s)>\]]+>?"),                # bare URLs and autolinks
)
SPAN = re.compile(r"`([^`\n]+)`")


def unexempt(line):
    """The part of a line the rules read: its link targets and repository paths removed."""
    for pattern in STRIP:
        line = pattern.sub(" ", line)
    return SPAN.sub(lambda m: " " if m.group(1).strip().startswith(TOP) else m.group(0), line)


def scan(text):
    """Every finding in one page, as (line number, rule, match)."""
    lines = text.split("\n")
    findings = []
    start = 0
    if lines and lines[0].strip() == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    fence = None          # the open fence's marker
    in_block = False      # inside a block: lines up to the next blank line
    exempt_block = False  # the current block is a labelled example
    exempt_next = False   # the next block is
    labelled = False      # the label was seen earlier in the current paragraph or list item
    last = ""             # the current block's last line
    for n in range(start, len(lines)):
        line = lines[n]
        m = FENCE.match(line)
        if fence:
            if m and m.group(1) == fence:
                fence = None
            continue
        if m:
            fence = m.group(1)
            in_block = exempt_block = exempt_next = labelled = False
            continue
        if not line.strip():
            if in_block:
                exempt_next = exempt_next or (labelled and last.rstrip().endswith(":"))
            in_block = exempt_block = labelled = False
            continue
        if MARKER.match(line):
            exempt_next = True
            continue
        if not in_block:
            in_block, exempt_block, exempt_next = True, exempt_next, False
        last = line
        if exempt_block:
            continue
        row = line.lstrip().startswith("|")
        if row or ITEM.match(line):
            labelled = False  # a table row or a new list item is its own unit
        label = LABEL.search(line)
        part = "" if labelled else line[:label.start()] if label else line
        labelled = labelled or bool(label)
        part = unexempt(part)
        prose = SPAN.sub(" ", part)
        for rule, pattern, in_code in RULES:
            for hit in pattern.finditer(part if in_code else prose):
                findings.append((n + 1, rule, hit.group(0)))
        if row:
            labelled = False  # a label in a row covers the rest of that row only
    return findings


def main(argv):
    root = pathlib.Path(argv[1] if len(argv) > 1 else pathlib.Path(__file__).resolve().parents[2])
    docs = root / DOCS
    count = 0
    for page in sorted(docs.rglob("*.md")):
        rel = page.relative_to(docs).as_posix()
        if rel in RECORDS or rel.startswith(RECORDS):
            continue
        for n, rule, hit in scan(page.read_text(encoding="utf-8")):
            print(f"{DOCS / rel}:{n}\t{rule}\t{hit}")
            count += 1
    if count:
        print(f"\n==> {count} finding(s): the site carries session history. Rewrite the sentence for a reader")
        print("    who was not there, move it to the status page, or label it as an example")
        print("    (docs/docs-style.md). Do not add an allowlist.")
        return 1
    print("==> No session history on the site's pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
