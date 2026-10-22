#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/gen-capabilities.py, which renders mcp.yaml's MCP Allow lists from the profiles.

Each case copies the real infrastructure/base/agent-gateway/ into a temporary root, changes one
thing and runs the generator there: the profiles rebuild every list byte for byte, a profile edit
moves its own expression only, and each malformed profile is refused, by name, without a write.

Run: python3 scripts/ci/tests/test-gen-capabilities.py
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import shutil
import sys
import tempfile

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen_capabilities", ROOT / "scripts/ci/gen-capabilities.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FAILURES = []
GW = ROOT / gen.GATEWAY
LISTS = re.compile(r"^(?P<i> *)matchExpressions:\n(?:(?P=i)  - .*\n)+", re.M)


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def run(root, *flags):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = gen.main(["gen-capabilities.py", *flags, str(root)])
    return code, out.getvalue()


@contextlib.contextmanager
def tree():
    """A temporary root holding a copy of the real agent-gateway directory."""
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(GW, pathlib.Path(d) / gen.GATEWAY)
        yield pathlib.Path(d)


def mcp(root):
    return root / gen.MCP


def edit(root, name, change):
    path = root / gen.PROFILES / name
    doc = yaml.safe_load(path.read_text())
    change(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves mcp.yaml alone."""
    with tree() as t:
        before = mcp(t).read_text()
        change(t)
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and mcp(t).read_text() == before, out)


def on(name, change):
    """A tree change that edits one profile."""
    return lambda t: edit(t, name, change)


def constrained(d):
    d["tools"]["flux-operator-mcp"][3] = {"name": "get_kubernetes_resources",
                                          "when": 'mcp.tool.arguments.kind != "Secret"'}


def renamed_target(d):
    d["tools"]["mcp-victoria-logs"] = d["tools"].pop("mcp-victorialogs")


def restricted(t):
    shutil.copy(t / gen.PROFILES / "reviewer.internal.yaml", t / gen.PROFILES / "reviewer.restricted.yaml")
    edit(t, "reviewer.restricted.yaml", lambda d: d.update(dataClass="restricted"))


def no_public(t):
    for p in (t / gen.PROFILES).glob("*.public.yaml"):
        p.unlink()


print("parity")
with tree() as t:
    code, out = run(t)
    check("today's profiles render today's mcp.yaml", code == 0 and "is its profiles' rendering" in out, out)
with tree() as t:
    blank = LISTS.sub(lambda m: f"{m['i']}matchExpressions:\n{m['i']}  - 'placeholder'\n", mcp(t).read_text())
    mcp(t).write_text(blank)
    code, out = run(t, "--write")
    check("--write rebuilds both lists from the profiles alone, byte for byte",
          code == 0 and mcp(t).read_bytes() == (GW / "mcp.yaml").read_bytes(), out)
check("an expression is one N7 alternative",
      gen.expression("reviewer", "internal", "room-broker", ["room_read", "room_verdict"]) ==
      '"agent-router.reviewer.internal" in jwt.aud && mcp.tool.target == "room-broker"'
      ' && mcp.tool.name in ["room_read", "room_verdict"]')
with tree() as t:
    edit(t, "reviewer.internal.yaml", lambda d: d.update(tools=dict(reversed(list(d["tools"].items())))))
    code, out = run(t)
    check("targets render in the backend's order, not the profile's", code == 0, out)

print("drift (design gate 5)")
with tree() as t:
    text = mcp(t).read_text()
    mcp(t).write_text(text.replace(', "get_kubernetes_logs"]', "]", 1))
    code, out = run(t)
    check("a list edited by hand fails, with the diff and the fix", mcp(t).read_text() != text and code == 1
          and '+            - \'"agent-router.reviewer.internal"' in out and "--write" in out, out)
with tree() as t:
    before = mcp(t).read_text().splitlines()
    edit(t, "implementer.internal.yaml", lambda d: d["tools"]["mcp-victorialogs"].append("query"))
    code, out = run(t)
    check("a profile edited without --write fails", code == 1 and "differs" in out, out)
    code, out = run(t, "--write")
    after = mcp(t).read_text().splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    expr = gen.expression("implementer", "internal", "mcp-victorialogs", ["documentation", "query"])
    want = f"            - '{expr}'"
    check("--write moves exactly that expression", code == 0 and len(before) == len(after)
          and changed == [(changed[0][0], want)] and "implementer.internal" in changed[0][0], str(changed))
    check("the result is in sync", run(t)[0] == 0)
    policies = [d for d in yaml.safe_load_all(mcp(t).read_text()) if d and d["kind"] == "AgentgatewayPolicy"]
    exprs = [e for p in policies for e in p["spec"]["backend"]["mcp"]["authorization"]["policy"]["matchExpressions"]]
    check("the written YAML parses back to the expressions", expr in exprs and len(exprs) == 32, str(len(exprs)))

print("refused profiles")
for name, change, needle in [
    ("egress waits for the ConfigMap", on("reviewer.internal.yaml", lambda d: d.update(egress=[])),
     "egress arrives with the agent-capability-profiles ConfigMap"),
    ("readOnly waits for the ConfigMap", on("reviewer.internal.yaml", lambda d: d.update(readOnly=["room-broker/*"])),
     "readOnly arrives with the agent-capability-profiles ConfigMap"),
    ("an unknown key", on("reviewer.internal.yaml", lambda d: d.update(namespaces=["x"])), "unknown key namespaces"),
    ("an argument constraint waits for P3", on("reviewer.internal.yaml", constrained),
     "get_kubernetes_resources: argument constraints (when) arrive with P3"),
    ("a narrower model list waits for P2", on("tester.public.yaml", lambda d: d.update(models=["agent-default"])),
     "until P2"),
    ("an alias no backend serves", on("tester.public.yaml", lambda d: d["models"].append("tier-huge")), "until P2"),
    ("an unknown target", on("triager.internal.yaml", renamed_target), "mcp-victoria-logs is not a target"),
    ("a target with no tool", on("triager.internal.yaml", lambda d: d["tools"].update({"room-broker": []})),
     "room-broker lists no tool"),
    ("a tool listed twice", on("triager.internal.yaml", lambda d: d["tools"]["room-broker"].append("room_read")),
     "room_read twice"),
    ("not a tool name", on("triager.internal.yaml", lambda d: d["tools"]["room-broker"].append("room read")),
     "'room read', which is not a tool name"),
    ("a role that disagrees with its file name", on("reviewer.public.yaml", lambda d: d.update(role="tester")),
     "reviewer.public.yaml: a profile is named <role>.<dataClass>.yaml"),
    ("a profile without tools", on("reviewer.public.yaml", lambda d: d.pop("tools")), "missing tools"),
    ("a class no listener serves", restricted, "reviewer.restricted.yaml: no MCP Allow policy"),
    ("a listener with no profile", no_public, "no profile of class public"),
    ("no profiles at all", lambda t: shutil.rmtree(t / gen.PROFILES), "profiles: no profile"),
]:
    refused(name, change, needle)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
