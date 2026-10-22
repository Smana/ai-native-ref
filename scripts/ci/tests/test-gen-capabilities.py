#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/gen-capabilities.py, which renders mcp.yaml's MCP Allow lists (P1) and
policy-capabilities.yaml's model rules (P2) from the profiles.

Each case copies the real infrastructure/base/agent-gateway/ into a temporary root, changes one
thing and runs the generator there: the profiles rebuild every list and the policy file byte for
byte, a profile edit moves its own expression only, and each malformed profile is refused, by name,
without a write.

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


def caps(root):
    return root / gen.CAPABILITIES


def rules(root):
    """{policy name: (its targetRefs' sectionNames, its expressions)} from policy-capabilities.yaml."""
    return {d["metadata"]["name"]: ([t["sectionName"] for t in d["spec"]["targetRefs"]],
                                    d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"])
            for d in yaml.safe_load_all(caps(root).read_text()) if d}


def edit(root, name, change):
    path = root / gen.PROFILES / name
    doc = yaml.safe_load(path.read_text())
    change(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves both files alone."""
    with tree() as t:
        before = mcp(t).read_text(), caps(t).read_text()
        change(t)
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and (mcp(t).read_text(), caps(t).read_text()) == before, out)


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


def stray_yml(t):
    shutil.copy(t / gen.PROFILES / "reviewer.public.yaml", t / gen.PROFILES / "reviewer.public.yml")


def stray_dir(t):
    (t / gen.PROFILES / "extra").mkdir()
    shutil.copy(t / gen.PROFILES / "reviewer.public.yaml", t / gen.PROFILES / "extra" / "reviewer.public.yaml")


def valueless_target(d):
    d["tools"]["room-broker"] = None


def no_public(t):
    for p in (t / gen.PROFILES).glob("*.public.yaml"):
        p.unlink()


def no_listener_require(t):
    path = t / gen.IDENTITY
    path.write_text(path.read_text().replace("    authorization:\n      action: Require\n", "    x-authorization:\n      action: Require\n", 1))


print("parity")
with tree() as t:
    code, out = run(t)
    check("today's profiles render today's mcp.yaml and policy-capabilities.yaml",
          code == 0 and out.count("is its profiles' rendering") == 2, out)
with tree() as t:
    caps(t).unlink()
    code, out = run(t, "--write")
    check("--write rebuilds policy-capabilities.yaml from the profiles alone, byte for byte",
          code == 0 and caps(t).read_bytes() == (GW / "policy-capabilities.yaml").read_bytes(), out)
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

print("model rules (P2)")
P = gen.Profile
pair = [P("x", "reviewer", "internal", ["tier-frontier"], {}), P("x", "implementer", "internal", ["agent-default", "tier-light"], {}),
        P("x", "tester", "public", ["agent-default"], {})]
check("a model rule binds the effective model once, one alternative per role of the class, roles in name order",
      gen.model_rule("internal", pair) ==
      '("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model).with(m, '
      '("agent-router.implementer.internal" in jwt.aud && m in ["agent-default", "tier-light"]) || '
      '("agent-router.reviewer.internal" in jwt.aud && m in ["tier-frontier"]))')
with tree() as t:
    got = rules(t)
    check("one policy per listener with LLM routes, public first", list(got) == ["capabilities-public", "capabilities-internal"],
          str(list(got)))
    check("each targets its LLM rules but never the /v1/models one",
          all(sections == ["openai", "anthropic"] for sections, _ in got.values()), str(got))
    check("each repeats its listener's Require first",
          all(exprs[0] == 'jwt.sub.startsWith("system:serviceaccount:agents:")' and len(exprs) == 2
              for _, exprs in got.values()), str(got))
with tree() as t:
    before = caps(t).read_text().splitlines()
    edit(t, "reviewer.internal.yaml", lambda d: d.update(models=["tier-frontier", "agent-default"]))
    code, out = run(t)
    check("a profile narrowed without --write fails", code == 1 and "policy-capabilities.yaml differs" in out, out)
    code, out = run(t, "--write")
    after = caps(t).read_text().splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    check("--write moves exactly the internal model rule", code == 0 and len(before) == len(after)
          and len(changed) == 1 and '"agent-router.reviewer.internal" in jwt.aud && m in ["tier-frontier", "agent-default"]'
          in changed[0][1] and "public" not in changed[0][1], str(changed))
    check("mcp.yaml is untouched by a model change", mcp(t).read_bytes() == (GW / "mcp.yaml").read_bytes())

print("drift (design gate 5)")
with tree() as t:
    text = caps(t).read_text()
    caps(t).write_text(text.replace(', "tier-frontier"]) || ("agent-router.reviewer.public"', ']) || ("agent-router.reviewer.public"', 1))
    code, out = run(t)
    check("policy-capabilities.yaml edited by hand fails, with the diff and the fix",
          caps(t).read_text() != text and code == 1 and "policy-capabilities.yaml (rendered from" in out and "--write" in out, out)
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

print("lists the generator does not fully own")
STRAY = "items the generator does not own (a comment or a multi-line item inside the list?)"
with tree() as t:
    text = mcp(t).read_text()
    first = LISTS.search(text)
    lines = first.group(0).splitlines(True)
    commented = text[:first.start()] + "".join(lines[:3]) + f"{first['i']}  # note\n" + "".join(lines[3:]) + text[first.end():]
    mcp(t).write_text(commented)
    code, out = run(t)
    check("a comment inside a list fails the check", code == 1 and STRAY in out, out)
    code, out = run(t, "--write")
    check("--write refuses it and leaves the file untouched", code == 1 and STRAY in out
          and mcp(t).read_text() == commented, out)
with tree() as t:
    text = mcp(t).read_text()
    mcp(t).write_text(text.rstrip("\n"))
    code, out = run(t, "--write")
    check("no final newline: refused, never written with a surviving duplicate",
          code == 1 and STRAY in out and mcp(t).read_text() == text.rstrip("\n"), out)

print("refused profiles")
for name, change, needle in [
    ("egress waits for the ConfigMap", on("reviewer.internal.yaml", lambda d: d.update(egress=[])),
     "egress arrives with the agent-capability-profiles ConfigMap"),
    ("readOnly waits for the ConfigMap", on("reviewer.internal.yaml", lambda d: d.update(readOnly=["room-broker/*"])),
     "readOnly arrives with the agent-capability-profiles ConfigMap"),
    ("an unknown key", on("reviewer.internal.yaml", lambda d: d.update(namespaces=["x"])), "unknown key namespaces"),
    ("an argument constraint waits for P3", on("reviewer.internal.yaml", constrained),
     "get_kubernetes_resources: argument constraints (when) arrive with P3"),
    ("an alias no backend serves", on("tester.public.yaml", lambda d: d["models"].append("tier-huge")),
     "models names tier-huge, which no LLM backend serves"),
    ("no model at all", on("tester.public.yaml", lambda d: d.update(models=[])), "at least one"),
    ("a model listed twice", on("tester.public.yaml", lambda d: d["models"].append("agent-default")),
     "models lists agent-default twice"),
    ("a listener with LLM routes and no Require to repeat", no_listener_require,
     "no Require authorization on the public listener to repeat"),
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
    ("a .yml file reads like a rule but grants nothing", stray_yml,
     "profiles/reviewer.public.yml: only <role>.<dataClass>.yaml files are profiles"),
    ("a subdirectory reads like a rule but grants nothing", stray_dir,
     "profiles/extra: only <role>.<dataClass>.yaml files are profiles"),
    ("a target with no value ends in the refusal, not a traceback",
     on("triager.internal.yaml", valueless_target), "room-broker lists no tool"),
    ("a class no listener serves", restricted, "reviewer.restricted.yaml: no MCP Allow policy"),
    ("a listener with no profile", no_public, "no profile of class public"),
    ("no profiles at all", lambda t: shutil.rmtree(t / gen.PROFILES), "profiles: no profile"),
]:
    refused(name, change, needle)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
