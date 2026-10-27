#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/gen-capabilities.py, which renders mcp.yaml's MCP Allow lists (P1) and
policy-capabilities.yaml's model rules (P2) and argument rules (P3) from the profiles.

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
    """{policy name: (its targetRefs' sectionNames, its expressions)} for the model rules (P2)."""
    return {d["metadata"]["name"]: ([t.get("sectionName") for t in d["spec"]["targetRefs"]],
                                    d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"])
            for d in yaml.safe_load_all(caps(root).read_text())
            if d and not d["metadata"]["name"].startswith("capabilities-mcp-")}


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
                                          "when": 'mcp.tool.arguments.kind not in ["secret", "secretlist", "secrets"]'}


def unconstrained(t):
    """Every profile with its tools' `when` dropped, as before P3."""
    for p in (t / gen.PROFILES).glob("*.yaml"):
        edit(t, p.name, lambda d: d.update(tools={k: [n["name"] if isinstance(n, dict) else n for n in v]
                                                  for k, v in d["tools"].items()}))


def when(form):
    return lambda d: d["tools"]["flux-operator-mcp"].__setitem__(3, {"name": "get_kubernetes_resources", "when": form})


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

print("argument rules (P3)")
GOLDEN = """\
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: capabilities-mcp-internal
  namespace: agent-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agentgateway-mcp-internal
  traffic:
    authorization:
      action: Require
      policy:
        matchExpressions:
          - 'jwt.sub.startsWith("system:serviceaccount:agents:")'
          - '!("agent-router.reviewer.internal" in jwt.aud && default(mcp.tool.target, "") == "flux-operator-mcp" && default(mcp.tool.name, "") == "get_kubernetes_resources") || !(default(mcp.tool.arguments.kind, "").lowerAscii() in ["secret", "secretlist", "secrets"])'
"""
with tree() as t:
    unconstrained(t)
    code, out = run(t, "--write")
    check("profiles without a when render no argument policy", code == 0 and "name: capabilities-mcp-" not in caps(t).read_text(), out)
    edit(t, "reviewer.internal.yaml", constrained)
    code, out = run(t, "--write")
    text = caps(t).read_text()
    check("a constrained tool renders capabilities-mcp-internal on the internal MCP route (golden)",
          code == 0 and text.split("---\n")[-1] == GOLDEN, out + text)
    check("its name stays in the Allow list: mcp.yaml is untouched", mcp(t).read_bytes() == (GW / "mcp.yaml").read_bytes())
    check("the model rules are untouched", rules(t) == rules(ROOT))
    edit(t, "triager.internal.yaml", constrained)
    run(t, "--write")
    exprs = [e for d in yaml.safe_load_all(caps(t).read_text()) if d and d["metadata"]["name"] == "capabilities-mcp-internal"
             for e in d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]]
    check("roles render in name order, after the listener's Require",
          [e.split('"')[1] for e in exprs[1:]] == ["agent-router.reviewer.internal", "agent-router.triager.internal"], str(exprs))
check("an argument rule binds one audience, target and tool, and folds the value",
      gen.argument_rule("reviewer", "internal", "flux-operator-mcp", "get_kubernetes_resources", "kind",
                        ("secret", "secretlist", "secrets")) ==
      '!("agent-router.reviewer.internal" in jwt.aud && default(mcp.tool.target, "") == "flux-operator-mcp"'
      ' && default(mcp.tool.name, "") == "get_kubernetes_resources")'
      ' || !(default(mcp.tool.arguments.kind, "").lowerAscii() in ["secret", "secretlist", "secrets"])')

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
    ("a when of another form", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind != "Pod"')), "when takes one form"),
    ("the single-value form, which cannot hold SecretList", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind != "secret"')),
     "when takes one form"),
    ("a when with an upper-case value, which the folded argument never equals",
     on("reviewer.internal.yaml", when('mcp.tool.arguments.kind not in ["Secret"]')), "when takes one form"),
    ("a when with an empty set", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind not in []')), "when takes one form"),
    ("a when on a tool with a bad name", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"].__setitem__(
        3, {"name": "Get-Resources", "when": 'mcp.tool.arguments.kind not in ["secret"]'})), "not a tool name"),
    ("a when with an appended || true", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind not in ["secret", "secretlist", "secrets"] || true')),
     "when takes one form"),
    ("a when with a quote in its value", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind not in ["se"cret"]')),
     "when takes one form"),
    ("a constrained tool with another key", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .__setitem__(3, {"name": "get_kubernetes_resources", "when": 'mcp.tool.arguments.kind not in ["secret", "secretlist", "secrets"]', "unless": "x"})),
     "a constrained tool is {name, when}"),
    ("a when with no name", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .__setitem__(3, {"when": 'mcp.tool.arguments.kind not in ["secret", "secretlist", "secrets"]'})), "a constrained tool is {name, when}"),
    ("a constrained tool listed twice", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .append({"name": "get_kubernetes_resources", "when": 'mcp.tool.arguments.kind not in ["secret", "secretlist", "secrets"]'})),
     "get_kubernetes_resources twice"),
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
