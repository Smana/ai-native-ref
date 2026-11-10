#!/usr/bin/env python3
# requires: python3
"""gen-slack-bindings: one declaration, a consumer set per cloud, and drift is a gate failure (CD24, proof 16)."""
import contextlib
import importlib.util
import io
import pathlib
import shutil
import sys
import tempfile

try:
    import yaml
except ImportError:
    print("SKIP: PyYAML missing")
    sys.exit(77)  # 77: run-tests.sh shows SKIP

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/ci/gen-slack-bindings.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

MINI = pathlib.Path(__file__).resolve().parent / "slack-bindings-fixtures/mini"
# Each fixture file and the paths it stands for in a tree the generator reads: the per-cloud ones once
# per cloud.
FIXTURES = {"slack-bindings.yaml": (gen.DECLARATION,), "slack-app-config.yaml": (gen.APP,),
            "helm-values-sponsored.yaml": gen.SPONSORED, "room-broker-config.yaml": gen.BROKER,
            "resources-kustomization.yaml": (f"{gen.FACTORY}/kustomization.yaml",),
            "resources-repositories.yaml": (f"{gen.FACTORY}/repositories.yaml",)}
# Both clouds can serve the App (one at a time): each renders its own sponsored values and broker config.
CONSUMERS = ["tooling/base/agent-factory/slack-app/config.yaml",
             "tooling/aws-0/agent-factory/helm-values-sponsored.yaml",
             "tooling/gcp-0/agent-factory/helm-values-sponsored.yaml",
             "infrastructure/aws-0/room-broker/config.yaml",
             "infrastructure/gcp-0/room-broker/config.yaml"]
AWS_SPONSORED, AWS_BROKER = gen.SPONSORED[0], gen.BROKER[0]

failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


def mini():
    """A copy of the six fixture files, each at every path it stands for."""
    root = pathlib.Path(tempfile.mkdtemp())
    for name, rels in FIXTURES.items():
        for rel in rels:
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
    check("the real tree renders exactly the five consumers", sorted(rendered) == sorted(CONSUMERS))
    for p in CONSUMERS:
        check(f"{p} is the declaration's rendering", rendered.get(p) == (ROOT / p).read_text())
    check("main() on the real tree exits 0", run(ROOT)[0] == 0)

    root = mini()
    rc, _ = run(root, "--write")
    first = tree(root)
    check("--write on the unspliced fixture tree exits 0", rc == 0)
    check("--write moves the fixture tree's consumers", first != tree_of_fixtures())
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
    check("the failure names the factory's Repository objects", f"Repository in {gen.FACTORY}" in err)
    check("a refused declaration writes nothing",
          {p: b for p, b in tree(root).items() if p != gen.DECLARATION} ==
          {p: b for p, b in before.items() if p != gen.DECLARATION})
    shutil.rmtree(root)


TWO = """teamID: T0ACME
channels:
  G0WEB:
    repositories: [acme/web, acme/shop]
    maxCostUSD: 2
    approvals: true
    notify: [room.merged, room.pr_opened]
  C0SHOP:
    repositories: [acme/shop, acme/api]
    maxCostUSD: 0.5
    approvals: false
    notify: [room.ended, room.pr_opened, room.approval_closed]
"""


# The rendering itself, pinned: channels by id, each channel's fields, the sorted repository union
# and the notify union in declaration order (which neither sorting nor idempotence would show).
def check_two_channels_render_in_their_orders():
    root = mini()
    (root / gen.DECLARATION).write_text(TWO)
    rc, err = run(root, "--write")
    check(f"two channels render ({err.strip()})", rc == 0)
    app = (root / gen.APP).read_text()
    check("the App's channels block, sorted by id, approvals only when true", app.endswith(
        "channels:\n"
        "  C0SHOP: {repositories: [acme/shop, acme/api], maxCostUSD: 0.5, "
        "notify: [room.ended, room.pr_opened, room.approval_closed]}\n"
        "  G0WEB: {repositories: [acme/web, acme/shop], maxCostUSD: 2, approvals: true, "
        "notify: [room.merged, room.pr_opened]}\n"))
    channels = yaml.safe_load(app)["channels"]
    check("the App's channels decode to the declaration's",
          list(channels) == ["C0SHOP", "G0WEB"]
          and channels["C0SHOP"] == {"repositories": ["acme/shop", "acme/api"], "maxCostUSD": 0.5,
                                     "notify": ["room.ended", "room.pr_opened", "room.approval_closed"]}
          and channels["G0WEB"] == {"repositories": ["acme/web", "acme/shop"], "maxCostUSD": 2, "approvals": True,
                                    "notify": ["room.merged", "room.pr_opened"]})
    union = ["acme/api", "acme/shop", "acme/web"]
    for sponsored, broker in zip(gen.SPONSORED, gen.BROKER):
        values = yaml.safe_load(yaml.safe_load((root / sponsored).read_text())["data"]["values.yaml"])
        check(f"{sponsored}: the sponsored repositories are the sorted union",
              values["config"]["api"]["sponsored"][0]["repositories"] == union)
        hooks = {w["name"]: w for w in yaml.safe_load((root / broker).read_text())["webhooks"]}
        check(f"{broker}: the repositories are the sorted union", hooks["slack-app"]["repositories"] == union)
        check(f"{broker}: the events are the notify union in declaration order", hooks["slack-app"]["events"]
              == ["room.merged", "room.pr_opened", "room.ended", "room.approval_closed"])
        check(f"{broker}: another subscriber is untouched", hooks["ci"]["repositories"] == ["acme/shop"]
              and hooks["ci"]["events"] == ["room.merged"])
    shutil.rmtree(root)


ONE = (MINI / "slack-bindings.yaml").read_text()
# (case, the declaration, (path, old, new) or None, what stderr must name). A per-cloud edit lands on
# aws-0's copy alone: each cloud's consumer is checked on its own.
REFUSALS = [
    ("a channel id outside the pattern", ONE.replace("C0SHOP", "X0SHOP"), None, "X0SHOP"),
    ("a teamID outside the pattern", ONE.replace("T0ACME", "t0acme"), None, "t0acme"),
    ("no channel", "teamID: T0ACME\nchannels: {}\n", None, "no channel"),
    ("an empty repositories", ONE.replace("[acme/shop]", "[]"), None, "repositories is empty"),
    ("a malformed repository", ONE.replace("[acme/shop]", "[acme/shop, 'a b/c']"), None, "a b/c"),
    ("an unserved repository", ONE.replace("[acme/shop]", "[acme/shop, acme/x]"), None, "acme/x"),
    ("maxCostUSD below 0.01", ONE.replace("1.5", "0.001"), None, "0.001"),
    ("maxCostUSD above the principal's", ONE.replace("1.5", "2.5"), None, "2.5"),
    ("maxCostUSD a string", ONE.replace("1.5", "'1'"), None, "'1'"),
    ("maxCostUSD a boolean", ONE.replace("1.5", "true"), None, "True"),
    ("an unknown notify name", ONE.replace("room.merged", "room.nope"), None, "room.nope"),
    ("a notify name the App draws no line for", ONE.replace("room.merged", "room.run_ended"), None, "room.run_ended"),
    ("an empty notify union", ONE.replace("[room.pr_opened, room.merged, room.ended]", "[]"), None, "notify"),
    ("a duplicate notify entry", ONE.replace("room.merged,", "room.merged, room.merged,"), None, "room.merged"),
    ("a duplicate repository", ONE.replace("[acme/shop]", "[acme/shop, acme/shop]"), None, "acme/shop"),
    ("a duplicate YAML key", ONE + "  C0SHOP:\n    repositories: [acme/shop]\n    maxCostUSD: 1\n    notify: []\n",
     None, "C0SHOP"),
    ("an unknown channel key", ONE + "    color: red\n", None, "color"),
    ("an unknown top-level key", ONE + "extra: 1\n", None, "extra"),
    ("approvals not a boolean", ONE + "    approvals: 'yes'\n", None, "approvals"),
    ("no slack-app webhook", ONE, (AWS_BROKER, "name: slack-app", "name: slackapp"), AWS_BROKER),
    ("no slack-app sponsored entry", ONE, (AWS_SPONSORED, "name: slack-app", "name: slackapp"), AWS_SPONSORED),
    ("a comment inside a generated region", ONE, (AWS_BROKER, "run_started,\n", "run_started,\n    # c\n"),
     AWS_BROKER),
    ("a consumer that does not parse", ONE, (gen.APP, "namespace: agent-system", "namespace: [x"), gen.APP),
    # The ceiling is the lower cloud's: 1.5 fits gcp-0's principal (2) but not aws-0's lowered one.
    ("maxCostUSD above one cloud's principal", ONE, (AWS_SPONSORED, "maxCostUSD: 2", "maxCostUSD: 1"), "1.5"),
]


# Every refusal rule exits 1 and names what it refused; a refusal writes nothing.
def check_each_refusal_names_its_value():
    for name, declaration, edit, names in REFUSALS:
        root = mini()
        (root / gen.DECLARATION).write_text(declaration)
        if edit:
            p = root / edit[0]
            check(f"{name}: the fixture edit applies", edit[1] in p.read_text())
            p.write_text(p.read_text().replace(edit[1], edit[2]))
        before = tree(root)
        try:
            rc, err = run(root, "--write")
        except Exception as e:  # an uncaught error is a failure of its own, not the suite's end
            rc, err = f"raised {type(e).__name__}", ""
        check(f"{name}: exits 1 (got {rc})", rc == 1)
        check(f"{name}: stderr names {names!r} ({err.strip()[:160]})", names in err)
        check(f"{name}: writes nothing", tree(root) == before)
        shutil.rmtree(root)


check_one_declaration_renders_three_consumers()
check_two_channels_render_in_their_orders()
check_each_refusal_names_its_value()
check_hand_editing_a_generated_region_fails()
check_an_unserved_repository_fails_at_the_declaration()

print("\n".join(failures) or "PASS")
sys.exit(1 if failures else 0)
