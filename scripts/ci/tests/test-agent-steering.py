#!/usr/bin/env python3
# requires: python3
"""Steering notes (scoper design SC3, SC4): every .github/agent-factory/steering/<class>.md of this
repository passes the factory's rule, and the rule refuses what the factory refuses.

The rule is agent-platform's internal/factory/steering.Validate, mirrored: UTF-8, at most 2048
bytes, an optional "# " title on line 1, only blank lines before the first "## " module, at most
three "## " lines wherever they stand, one "## Verify" with a "- " or "* " item. A note is named
after a class the factory config declares, or review.

run-tests.sh runs this from .composite/ with cwd = this repository."""
import pathlib
import sys

import yaml

OWN = pathlib.Path.cwd()
NOTES = OWN / ".github/agent-factory/steering"
VALUES = OWN / "tooling/base/agent-factory/helm-values-configmap.yaml"
MAX_BYTES, MAX_MODULES, VERIFY = 2048, 3, "## Verify"


def validate(raw: bytes) -> str:
    """'' when raw is a valid note, else why not, in the factory's words."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8"
    if len(raw) > MAX_BYTES:
        return f"{len(raw)} bytes, at most {MAX_BYTES}"
    modules = items = 0
    current, has_verify = "", False
    for i, line in enumerate(text.replace("\r\n", "\n").split("\n")):
        if line.startswith("## "):
            modules += 1
            current = line.rstrip(" \t")
            has_verify = has_verify or current == VERIFY
        elif line.startswith("# ") and i == 0:
            pass
        elif current == "" and line.strip():
            return f"line {i + 1} stands before the first module"
        elif current == VERIFY and (line.startswith("- ") or line.startswith("* ")):
            items += 1
    if modules > MAX_MODULES:
        return f"{modules} modules, at most {MAX_MODULES}"
    if not has_verify:
        return "no ## Verify module"
    if items == 0:
        return "## Verify lists no check"
    return ""


def classes() -> set:
    """The classes the factory config declares, and review."""
    for doc in yaml.safe_load_all(VALUES.read_text()):
        values = (doc or {}).get("data", {}).get("values.yaml")
        if values:
            cfg = yaml.safe_load(values).get("config", {})
            found = {"review"}
            for repo in cfg.get("repositories") or [cfg]:
                found |= set((repo.get("classes") or {}).keys())
            return found
    return {"review"}


DOCS = ("# Steering: docs\n\n## Verify\n- `task links` (CI: validate): every relative Markdown link resolves.\n"
        "- `task docs` (CI: validate): the site builds; every repository path it names exists.\n\n## Leave alone\n"
        "- `docs/superpowers/`: dated designs and plans; edit only the one the issue names.\n"
        "- `website/content/docs/decisions/`: an ADR is superseded by a new one, never edited.\n\n## Write\n"
        "- English, short declarative sentences, tables over prose; a host page by absolute URL.\n")

# The factory's own cases (steering_test.go): the mirror refuses each, with the same words.
CASES = {
    "2049 bytes": (DOCS[:-1] + "x" * (MAX_BYTES - len(DOCS) + 1) + "\n", "at most 2048"),
    "four modules": (DOCS + "## More\n- x\n", "4 modules"),
    "no Verify": ("# Steering: docs\n\n## Leave alone\n- `docs/`\n", "no ## Verify"),
    "an empty Verify": ("## Verify\nRun the tests.\n## Leave alone\n- x\n", "lists no check"),
    "a Verify look-alike": ("## Verify the site\n- x\n", "no ## Verify"),
    "text before a module": ("Read this first.\n## Verify\n- x\n", "before the first module"),
    "a title on line 2": ("\n# Steering\n## Verify\n- x\n", "before the first module"),
    "a module in a fence": ("## Verify\n- x\n```\n## A\n## B\n## C\n```\n", "4 modules"),
}

fails = []
if validate(DOCS.encode()):
    fails.append(f"the design's docs note is refused: {validate(DOCS.encode())}")
if "not UTF-8" not in validate(b"## Verify\n- \xff\n"):
    fails.append("a note that is not UTF-8 is accepted")
for name, (text, want) in CASES.items():
    if want not in validate(text.encode()):
        fails.append(f"{name}: {validate(text.encode())!r}, want {want!r}")

known = classes()
for note in sorted(NOTES.glob("*.md")) if NOTES.is_dir() else []:
    if why := validate(note.read_bytes()):
        fails.append(f"{note.relative_to(OWN)}: {why}")
    if note.stem not in known:
        fails.append(f"{note.relative_to(OWN)}: {note.stem!r} is not review or a declared class {sorted(known)}")

if fails:
    print("\n".join(fails))
    sys.exit(1)
print(f"ok: {len(list(NOTES.glob('*.md'))) if NOTES.is_dir() else 0} note(s), {len(CASES) + 2} rule cases")
