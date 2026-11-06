#!/usr/bin/env python3
# requires: python3
"""gen-slack-bindings: one declaration, three consumers, and drift is a gate failure (CD24, proof 16)."""
import contextlib
import importlib.util
import io
import pathlib
import shutil
import sys
import tempfile

try:
    import yaml  # noqa: F401
except ImportError:
    print("SKIP: PyYAML missing")
    sys.exit(77)  # 77: run-tests.sh shows SKIP

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/ci/gen-slack-bindings.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

MINI = pathlib.Path(__file__).resolve().parent / "slack-bindings-fixtures/mini"
# Each fixture file and the path it stands for in a tree the generator reads.
FIXTURES = {"slack-bindings.yaml": gen.DECLARATION, "slack-app-config.yaml": gen.APP,
            "helm-values-sponsored.yaml": gen.SPONSORED, "room-broker-config.yaml": gen.BROKER,
            "helm-values-configmap.yaml": gen.FACTORY}
CONSUMERS = ["tooling/base/agent-factory/slack-app/config.yaml",
             "tooling/gcp-0/agent-factory/helm-values-sponsored.yaml",
             "infrastructure/gcp-0/room-broker/config.yaml"]
# Until ai-native-ref PR A's Task A4 renders the three regions, the committed tree is not the
# declaration's rendering; A4 also deletes this overlay copy, so its presence marks that tree.
UNRENDERED = ROOT / "tooling/gcp-0/agent-factory/slack-app/config.yaml"

failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


def mini():
    """A copy of the five fixture files, each at the path it stands for."""
    root = pathlib.Path(tempfile.mkdtemp())
    for name, rel in FIXTURES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MINI / name, root / rel)
    return root


def run(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = gen.main(["gen-slack-bindings.py", *args, str(root)])
    return rc, err.getvalue()


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# Proof 16, first half: one declaration renders the App's channels, the factory's sponsored
# repositories and the broker's webhook repositories byte for byte.
def check_one_declaration_renders_three_consumers():
    served, ceiling = gen.registries(ROOT)
    declaration = gen.load_declaration((ROOT / gen.DECLARATION).read_text())
    rendered = gen.render(declaration, served, ceiling, ROOT)
    check("the real tree renders exactly the three consumers", sorted(rendered) == sorted(CONSUMERS))
    if UNRENDERED.exists():
        # Removed by Task A4, which renders the regions and deletes the overlay copy this guard reads.
        print(f"note: {UNRENDERED.relative_to(ROOT)} exists, so the committed tree predates A4's "
              "rendering: the real tree's byte-for-byte and main() == 0 checks are skipped", file=sys.stderr)
    else:
        for p in CONSUMERS:
            check(f"{p} is the declaration's rendering", rendered.get(p) == (ROOT / p).read_text())
        check("main() on the real tree exits 0", gen.main(["gen-slack-bindings.py", str(ROOT)]) == 0)

    root = mini()
    rc, _ = run(root, "--write")
    first = tree(root)
    check("--write on the unspliced fixture tree exits 0", rc == 0)
    check("--write moves the fixture tree's three consumers", first != tree_of_fixtures())
    rc, _ = run(root, "--write")
    check("a second --write exits 0", rc == 0)
    check("a second --write leaves every file byte-identical", tree(root) == first)
    rc, _ = run(root)
    check("the written fixture tree is its declaration's rendering", rc == 0)
    shutil.rmtree(root)


def tree_of_fixtures():
    root = mini()
    try:
        return tree(root)
    finally:
        shutil.rmtree(root)


# Review Focus 5: a generated file edited by hand in the same commit as its declaration fails on the
# rendering, not on "the file moved".
def check_hand_editing_a_generated_region_fails():
    root = mini()
    run(root, "--write")
    app = root / gen.APP
    lines = app.read_text().splitlines(True)
    i = next(n for n, line in enumerate(lines) if line.startswith("channels:")) + 1
    check("the rendered channel line carries maxCostUSD: 1.5", "maxCostUSD: 1.5," in lines[i])
    lines[i] = lines[i].replace("maxCostUSD: 1.5,", "maxCostUSD: 1.6,")  # one byte
    app.write_text("".join(lines))
    rc, err = run(root)
    check("a hand-edited channels: line exits 1", rc == 1)
    check("the failure names the App config", gen.APP in err)
    shutil.rmtree(root)


# Proof 16, last clause: a channel naming a repository the factory does not serve fails at the
# declaration, before any cluster sees it.
def check_an_unserved_repository_fails_at_the_declaration():
    root = mini()
    declaration = root / gen.DECLARATION
    before = tree(root)
    declaration.write_text(declaration.read_text().replace("[acme/shop]", "[acme/shop, acme/unserved]"))
    check("the fixture declaration lists acme/shop as a flow list", "acme/unserved" in declaration.read_text())
    rc, err = run(root, "--write")
    check("an unserved repository exits 1", rc == 1)
    check("the failure names acme/unserved", "acme/unserved" in err)
    check("the failure names config.repositories", "config.repositories" in err)
    check("a refused declaration writes nothing",
          {p: b for p, b in tree(root).items() if p != gen.DECLARATION} ==
          {p: b for p, b in before.items() if p != gen.DECLARATION})
    shutil.rmtree(root)


check_one_declaration_renders_three_consumers()
check_hand_editing_a_generated_region_fails()
check_an_unserved_repository_fails_at_the_declaration()

print("\n".join(failures) or "PASS")
sys.exit(1 if failures else 0)
