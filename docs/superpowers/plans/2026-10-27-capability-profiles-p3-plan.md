# Capability profiles, P3: argument constraints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `get_kubernetes_resources` never runs with `kind: Secret`: the gateway refuses that call
with a 403 before it reaches flux-operator-mcp, for every role that holds the tool. Every other call,
the tool lists and the room tools, behaves as today.

**Architecture:** One pull request in ai-native-ref. A profile's tool may carry
`when: 'mcp.tool.arguments.<argument> != "<value>"'`. `scripts/ci/gen-capabilities.py` renders each
such entry into a route-level `authorization` Require on the listener's MCP HTTPRoute: a new policy,
`capabilities-mcp-<listener>`, in `policy-capabilities.yaml` (the generator already owns this file).
Four checks hold the result:

- AG6's grammar gains the argument rule.
- `test-agent-mcp-scope` freezes the expected rule.
- `test-gen-capabilities` gets a golden.
- `test-agent-capabilities-wire` runs the rule on the pinned agentgateway against a fake
  flux-operator-mcp.

The `mcpAuthorization` Allow lists in `mcp.yaml` do not change: the tool stays listed.

**Tech Stack:** Python 3 with PyYAML; Bash suites run by `scripts/ci/run-tests.sh` inside
`.composite/`; agentgateway 1.6.0, which provides route-level `authorization` CEL, `default()` and
`lowerAscii()`; Docker in CI.

**Spec:** [the capability profiles design](../specs/2026-10-21-capability-profiles-design.md),
decision P3, the "What the generator emits" row for `tools[].when`, the S0 result and its "After SDK
1.55" note, and gate item 2. The P2/P4 plan's R5 records P3's dependency on a harness with SDK ≥ 1.55.

**Out of P3:**
- `room_read`'s `kinds` scope (loops L4). It waits for the broker to give the tool a `kinds`
  argument, an agent-platform change.
- Namespace scopes.
- Any `when` form other than the one below.
- The `agent-capability-profiles` ConfigMap (P5).
- The live half of gate item 2: one check, batched into the next gcp-0 session (Task 6).

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **The rule is a route-level `traffic.authorization` on each listener's MCP HTTPRoute, in a separate generated policy, `capabilities-mcp-<listener>`.** It is not in `mcpAuthorization`, and it is not added to `capabilities-<listener>` | agentgateway v1.6.0 (`ea56086`) fills `mcp.tool.arguments` only for HTTP request policies. In `crates/agentgateway/src/proxy/httpproxy.rs`, `set_mcp_cel_context` calls `MCPInfo::from_request`, which calls `capture_call_arguments` (`crates/agentgateway/src/mcp/mod.rs`) before `apply_request_policies` runs the route's `authorization`. `mcpAuthorization` evaluates with `exec.mcp` set to a `ResourceType` that holds `{tool: {target, name}}` only (`crates/agentgateway/src/mcp/rbac.rs`, `CelExecWrapper`), so it never sees arguments. Requires are AND-ed within a policy. Sharing `capabilities-<listener>` would therefore apply its model rule, which reads `json(request.body).model`, to every MCP call, and refuse them all |
| R2 | **`when` takes exactly one form: `mcp.tool.arguments.<argument> != "<value>"`**, with `<argument>` an identifier and `<value>` matching `[A-Za-z0-9._/-]+`. The generator refuses any other form | This is the smallest form that states "never this value of this argument". Because the form is fixed, the generator, AG6 and the scope suite each parse it and can recompute the rule exactly, as AG6 does for tool names; a free CEL string could not be checked that way. The spec leaves list-valued arguments to the builder. No rule needs them yet, so none is added |
| R3 | **The rendered Require:** `!("<aud>" in jwt.aud && default(mcp.tool.target, "") == "<target>" && default(mcp.tool.name, "") == "<tool>") \|\| default(mcp.tool.arguments.<argument>, "").lowerAscii() != "<value, lower-cased>"`. There is one Require per role and constrained tool, roles in name order. The listener's Require comes first | **Requires and errors.** A Require must hold, and an evaluation error counts as false (`crates/agentgateway/src/http/authorization.rs`: `all_requires_match` → `eval_bool`). **What passes.** `default()` turns NoSuchKey and UndeclaredReference into its fallback (`crates/celx/src/general.rs`). So `initialize`, `tools/list`, notifications and a `GET` all pass, since none of them carries an `mcp.tool`. A call without the argument also passes, and the server answers it with `kind is required`. **Why fold.** flux-operator-mcp v0.60.0 hands `kind` to the RESTMapper verbatim (`cmd/mcp/k8s/client.go`, `ParseGroupVersionKind`), so whether `secret` resolves depends on the mapper. Folding refuses it either way, at no cost. **What refuses.** A non-string `kind` errors in `lowerAscii()` and is refused. **One Require per rule.** A rule can only narrow its own tool, and no `when` can loosen another rule |
| R4 | **A 403 is acceptable for P3.** Every run reaches the harness through a pin of SDK 1.56.0 | **The harness runs uses.** The host at `HOST_REF` (`2b2e496`) pins crossplane-configuration v0.9.20. Its AgentRun composition runs `agent-harness:v0.19.0`. **The pre-pulled image.** This repository pins `agent-harness:v0.23.2` (headroom pre-pull). **The SDK.** Both images pin `openhands-sdk==1.56.0` (agent-platform `images/agent-harness/requirements.in`, bumped by #170). **The SDK fix.** Since 1.55, a 403 on `tools/call` keeps the session (agent-platform SDK 1.56 plan, R8 and its measured table: calls 2 and 3 succeed). That measurement is the S0 re-run the spec asks for. **What the gateway sends.** agentgateway keeps the 403 on MCP: `maybe_convert_mcp_error` (`crates/agentgateway/src/mcp/mod.rs`) turns only rate limits into JSON-RPC errors |
| R5 | **The rule binds every role that holds the tool**: `reviewer`, `tester` and `triager` on `internal`. No implementer profile and no public profile holds `get_kubernetes_resources` | "Never with `kind: Secret`" is a property of the tool, not of one role. The scope suite derives the three roles from its frozen sets, so a fourth role that gains the tool must gain the rule too |
| R6 | **AG6 is amended; no new gate id is added.** On an MCP route, a route-level `authorization` is a Require that holds the listener's sub prefix and argument rules only, each one in AG6's argument grammar for an audience of the route's class. The value must be lower case, because an upper-case value would never match the folded argument and the rule would refuse nothing. `test-agent-mcp-scope` freezes the expected rules and reads them from the profiles and from the policy file independently. The drift suite stays `test-agent-capabilities` (P1 R5) | This mirrors the split for names: AG6 holds the grammar on the bundle and the scope suite holds the content (P1 R6). The gate count stays 15 |
| R7 | **The offline proof is `test-agent-capabilities-wire`, extended.** The same container, on the image `parameters.yaml` pins, gains the internal MCP route, its Allow list and the rendered `capabilities-mcp-internal`, in front of a fake flux-operator-mcp | It uses the same listener and the same tokens, and runs on the image the cluster runs. It covers the data plane only; the controller's translation of the CRD is the live check's job |
| R8 | **No switch (D4).** The rule refuses only calls that the server's RBAC already refuses: the `flux-operator-mcp` ServiceAccount reads no Secret (scope suite; runbook 06, Step 5). For every other call it changes nothing | A security control that is a no-op for every legitimate call needs no off switch |

**Verified from source, not measured.** This plan ran nothing: the cited code is agentgateway at
tag v1.6.0 (`ea56086`), flux-operator at tag v0.60.0, and agent-platform at tags v0.19.0 and
v0.23.2. Task 3's run is the first time this rule is measured. If a case fails there because of the
rendering (and not because the profiles have no `when` yet), change `argument_rule` in the generator
and `argument_rule` in the gate together. Then update the golden and record what the run showed.

## Global Constraints

- **Worktree:** `/home/smana/Sources/ai-native-ref-p3`, branch `feat/capability-profiles-p3`, from
  `origin/main` `edc1717`. Run `mise trust mise.toml` there once. Rebase onto a freshly fetched
  `origin/main` before every push.
- **`$SCRATCH`** is a scratch directory outside the repository. It holds two helpers and
  `bin/python3 -> /usr/bin/python3`, the `python3` that has PyYAML:
  - `check.sh <worktree>` runs `task check` with `$SCRATCH/bin` ahead of `PATH`, logs to
    `$SCRATCH/check-<worktree directory name>.log` and ends the log with `exit=N`.
  - `run-suite.sh <command…>` runs one command with that `PATH`.

  Every Python command and every suite goes through one of the two helpers. Create them if they are
  missing:

  ```bash
  mkdir -p "$SCRATCH/bin" && ln -sf /usr/bin/python3 "$SCRATCH/bin/python3"
  printf '#!/usr/bin/env bash\nPATH="%s/bin:$PATH" exec "$@"\n' "$SCRATCH" > "$SCRATCH/run-suite.sh"
  printf '#!/usr/bin/env bash\nlog="%s/check-$(basename "$1").log"\n(cd "$1" && PATH="%s/bin:$PATH" task check) >"$log" 2>&1; echo "exit=$?" >>"$log"\n' "$SCRATCH" "$SCRATCH" > "$SCRATCH/check.sh"
  ```
- **`task check` is the evidence** (AGENTS.md). Never claim done without its log.
- **Docker:** the daemon is off by default on the owner's machine. Docker suites SKIP without it,
  and CI (`CI=true`) fails them instead. Task 3's red and green runs need a daemon. Ask the owner to
  start it, and never start it yourself. Without one, record the SKIP; CI is where the suite must
  pass.
- **Run the gate's unit test inside the composite:**
  `bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh && bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`.
- **Git hygiene:** `export PYTHONDONTWRITEBYTECODE=1`. Always `git add` named paths, never `-A`.
- **The suite contract:** line 1 is the shebang and line 2 is `# requires: <tools>`. Exit 77 means
  SKIP. Suites read the real tree.
- **Before pushing:** run `pre-commit run --all-files`. `task check` does not run it.
- **Commits:** conventional, in English, with **no trailers**.
- **Verbatim from the spec:**
  - P3: "Argument constraints in the same route-level policy on `mcp.tool.arguments`. The first one
    is `get_kubernetes_resources` never with `kind: Secret`". R1 places the rule in a separate
    policy of the same file.
  - S0: "Whichever P3 takes must amend AG6's grammar and the scope suite's regex, which hold tool
    names only today."

## File structure

| File | Change | Responsibility |
|---|---|---|
| `scripts/ci/gen-capabilities.py` | modify | Parses `tools[].when` and renders `capabilities-mcp-<listener>` |
| `scripts/ci/tests/test-gen-capabilities.py` | modify | Golden, the rule's text, refusals |
| `infrastructure/base/agent-gateway/policy-capabilities.yaml` | regenerate | Header (Task 1), `capabilities-mcp-internal` (Task 4) |
| `scripts/ci/flux-schema/assert-agent-gateway.py` | modify: AG6 | The argument grammar on MCP routes |
| `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py` | modify | AG6's argument cases |
| `scripts/ci/tests/test-agent-capabilities-wire.sh` | modify | An MCP route on the pinned image |
| `scripts/ci/tests/test-agent-mcp-scope.sh` | modify | The frozen argument rules |
| `infrastructure/base/agent-gateway/profiles/{reviewer,tester,triager}.internal.yaml` | modify | The `when` |
| `website/content/docs/platform/ai-platform/gateways.md` | modify | The argument rule |
| `website/content/docs/platform/ai-platform/status.md` | modify: one row | P3 built |
| `docs/superpowers/specs/2026-10-21-capability-profiles-design.md` | modify | Status, P3's row, gate item 2, rulings |

---

### Task 1: The generator renders argument rules

**Files:**
- Modify: `scripts/ci/gen-capabilities.py`
- Modify: `scripts/ci/tests/test-gen-capabilities.py`
- Regenerate: `infrastructure/base/agent-gateway/policy-capabilities.yaml` (header only)

**Interfaces:**
- Produces, for Tasks 2 and 4:
  - `argument_rule(role, cls, target, tool, arg, value) -> str`;
  - the `WHEN` regex;
  - `Profile.rules`, a tuple of `(target, tool, arg, value)`;
  - the policy name `capabilities-mcp-<cls>`.

- [ ] **Step 1: Write the failing tests**

In `scripts/ci/tests/test-gen-capabilities.py`:

(a) In `rules()`, use `t.get("sectionName")` and skip the argument policies, so the P2 checks stay
about the model rules:

```python
def rules(root):
    """{policy name: (its targetRefs' sectionNames, its expressions)} for the model rules (P2)."""
    return {d["metadata"]["name"]: ([t.get("sectionName") for t in d["spec"]["targetRefs"]],
                                    d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"])
            for d in yaml.safe_load_all(caps(root).read_text())
            if d and not d["metadata"]["name"].startswith("capabilities-mcp-")}
```

(b) After `constrained`, add:

```python
def unconstrained(t):
    """Every profile with its tools' `when` dropped, as before P3."""
    for p in (t / gen.PROFILES).glob("*.yaml"):
        edit(t, p.name, lambda d: d.update(tools={k: [n["name"] if isinstance(n, dict) else n for n in v]
                                                  for k, v in d["tools"].items()}))


def when(form):
    return lambda d: d["tools"]["flux-operator-mcp"].__setitem__(3, {"name": "get_kubernetes_resources", "when": form})
```

(c) Before `print("drift (design gate 5)")`, add:

```python
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
          - '!("agent-router.reviewer.internal" in jwt.aud && default(mcp.tool.target, "") == "flux-operator-mcp" && default(mcp.tool.name, "") == "get_kubernetes_resources") || default(mcp.tool.arguments.kind, "").lowerAscii() != "secret"'
"""
with tree() as t:
    unconstrained(t)
    code, out = run(t, "--write")
    check("profiles without a when render no argument policy", code == 0 and "capabilities-mcp-" not in caps(t).read_text(), out)
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
      gen.argument_rule("reviewer", "internal", "flux-operator-mcp", "get_kubernetes_resources", "kind", "Secret") ==
      '!("agent-router.reviewer.internal" in jwt.aud && default(mcp.tool.target, "") == "flux-operator-mcp"'
      ' && default(mcp.tool.name, "") == "get_kubernetes_resources")'
      ' || default(mcp.tool.arguments.kind, "").lowerAscii() != "secret"')
```

(d) In the `refused` list, replace the entry:

```python
    ("an argument constraint waits for P3", on("reviewer.internal.yaml", constrained),
     "get_kubernetes_resources: argument constraints (when) arrive with P3"),
```

with:

```python
    ("a when of another form", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind == "Pod"')), "when takes one form"),
    ("a when with an appended || true", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind != "Secret" || true')),
     "when takes one form"),
    ("a when with a quote in its value", on("reviewer.internal.yaml", when('mcp.tool.arguments.kind != "Se"cret"')),
     "when takes one form"),
    ("a constrained tool with another key", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .__setitem__(3, {"name": "get_kubernetes_resources", "when": 'mcp.tool.arguments.kind != "Secret"', "unless": "x"})),
     "a constrained tool is {name, when}"),
    ("a when with no name", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .__setitem__(3, {"when": 'mcp.tool.arguments.kind != "Secret"'})), "a constrained tool is {name, when}"),
    ("a constrained tool listed twice", on("reviewer.internal.yaml", lambda d: d["tools"]["flux-operator-mcp"]
     .append({"name": "get_kubernetes_resources", "when": 'mcp.tool.arguments.kind != "Secret"'})),
     "get_kubernetes_resources twice"),
```

(e) Update the module docstring's first sentence to cover the argument rules (P3).

- [ ] **Step 2: Run them and watch them fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | grep -v '^  ok'
```

Expected:
- `FAIL a constrained tool renders capabilities-mcp-internal …` and `FAIL roles render in name order
  …`, because today's generator refuses every `when`;
- then a traceback ending
  `AttributeError: module 'gen_capabilities' has no attribute 'argument_rule'`.

- [ ] **Step 3: The generator**

In `scripts/ci/gen-capabilities.py`:

(a) In the docstring, replace

```
`egress`, `readOnly` and a tool's `when` are refused until the steps that render them: a field
nothing enforces must not read as a rule.
```

with

```
A tool's `when` (P3), `{name: <tool>, when: 'mcp.tool.arguments.<argument> != "<value>"'}`, the one
form this script takes: each renders one Require into policy-capabilities.yaml's
capabilities-mcp-<listener>, on the listener's MCP route. A call of that tool by that role carrying
that value, compared ASCII case-folded, is refused 403; any other request, and a call without the
argument, passes. The tool keeps its name in mcp.yaml's list. 1.6's mcpAuthorization cannot read
arguments (its CEL holds the tool's target and name only), so the rule is route-level.

`egress` and `readOnly` are refused until the steps that render them: a field nothing enforces must
not read as a rule.
```

(b) After `TOOL = re.compile(...)`, add:

```python
# P3: a tool's `when` takes one form, an argument that must not hold one value. The generator, gate AG6
# and test-agent-mcp-scope each parse it, so each can recompute the rule exactly.
WHEN = re.compile(r'^mcp\.tool\.arguments\.(?P<arg>[A-Za-z_][A-Za-z0-9_]*) != "(?P<value>[A-Za-z0-9._/-]+)"$')
```

(c) Replace HEADER's first two lines:

```python
# Generated by scripts/ci/gen-capabilities.py --write from profiles/*.yaml (capability profiles design,
# P2): edit the profiles, never this file. test-agent-capabilities fails on any difference.
```

with:

```python
# Generated by scripts/ci/gen-capabilities.py --write from profiles/*.yaml (capability profiles design,
# P2 and P3): edit the profiles, never this file. test-agent-capabilities fails on any difference.
```

and append to HEADER, after its last line (`# 1.6 adds route rules to the listener's; …`):

```python
#
# capabilities-mcp-<listener>, on the listener's MCP route, where a profile constrains a tool's
# arguments (P3): one Require per role and constrained tool that the call never carries the value the
# profile's `when` excludes, compared ASCII case-folded. default() lets every other request through,
# and a call without the argument too: the server answers it. 1.6's mcpAuthorization cannot read
# arguments, so a refusal answers HTTP 403 rather than hiding the tool; the harness's OpenHands SDK
# keeps its MCP session after one since 1.55.
```

(d) Give `Profile` a last field `rules: tuple = ()`. Existing callers pass five fields and keep
working.

(e) After `model_rule`, add:

```python
def argument_rule(role, cls, target, tool, arg, value):
    """One Require (P3): this role's call of this tool never carries this argument value, folded.
    default() passes every request without that tool call, and a call without the argument."""
    return (f'!("{AUD_PREFIX}.{role}.{cls}" in jwt.aud && default(mcp.tool.target, "") == "{target}"'
            f' && default(mcp.tool.name, "") == "{tool}")'
            f' || default(mcp.tool.arguments.{arg}, "").lowerAscii() != "{value.lower()}"')
```

(f) In `load_profile`, replace the block from `for target, names in tools.items():` to the
`return Profile(…)` line with:

```python
    names_of, rules = {}, []
    for target, names in tools.items():
        if target not in targets:
            errors.append(f"{rel}: {target} is not a target of the agent-mcp backend ({', '.join(targets)})")
        if not isinstance(names, list) or not names:
            errors.append(f"{rel}: {target} lists no tool; leave the target out instead")
            continue
        plain = []
        for n in names:
            if isinstance(n, dict):
                if set(n) != {"name", "when"}:
                    errors.append(f"{rel}: {target} {n!r}: a constrained tool is {{name, when}}")
                    continue
                n, w = n["name"], WHEN.match(str(n["when"]))
                if w:
                    rules.append((target, n, w["arg"], w["value"]))
                elif isinstance(n, str) and TOOL.match(n):
                    errors.append(f'{rel}: {target} {n}: when takes one form, mcp.tool.arguments.<argument> != "<value>"')
            if not isinstance(n, str) or not TOOL.match(n):
                errors.append(f"{rel}: {target} names {n!r}, which is not a tool name")
            else:
                plain.append(n)
        twice = sorted({n for n in plain if plain.count(n) > 1})
        if twice:
            errors.append(f"{rel}: {target} lists {', '.join(twice)} twice")
        names_of[target] = plain
    return Profile(rel, str(doc.get("role")), str(doc.get("dataClass")), models, names_of, tuple(rules))
```

(g) Replace `render_capabilities` whole:

```python
def render_capabilities(root, profiles, mcp_routes, errors):
    """policy-capabilities.yaml as the profiles render it: the model rules (P2), then the argument rules (P3)."""
    requires = listener_requires(root, errors)
    rules = llm_rules(root, errors)
    for p in profiles:
        if p.data_class not in rules:
            errors.append(f"{p.path}: no LLM route on the {p.data_class} listener for its models to bind")
    policies = []  # (name, namespace, targetRefs text, expressions)
    for cls, targets in rules.items():
        if not any(p.data_class == cls for p in profiles):
            errors.append(f"{GATEWAY}: LLM routes on the {cls} listener and no profile of class {cls}")
            continue
        if cls not in requires:
            errors.append(f"{IDENTITY}: no Require authorization on the {cls} listener to repeat")
            continue
        ns = {t[0] for t in targets}
        if len(ns) != 1:
            errors.append(f"{GATEWAY}: the {cls} listener's LLM routes span namespaces {sorted(map(str, ns))}")
            continue
        refs = "".join(f"    - group: gateway.networking.k8s.io\n      kind: HTTPRoute\n"
                       f"      name: {route}\n      sectionName: {rule}\n" for _, route, rule in targets)
        policies.append((f"capabilities-{cls}", ns.pop(), refs, requires[cls] + [model_rule(cls, profiles)]))
    for cls, routes in mcp_routes.items():
        exprs = [argument_rule(p.role, cls, *r) for p in sorted(profiles, key=lambda p: p.role)
                 if p.data_class == cls for r in p.rules]
        if not exprs:
            continue
        if cls not in requires:
            errors.append(f"{IDENTITY}: no Require authorization on the {cls} listener to repeat")
            continue
        ns = {n for n, _ in routes}
        if len(ns) != 1:
            errors.append(f"{MCP}: the {cls} listener's MCP routes span namespaces {sorted(map(str, ns))}")
            continue
        refs = "".join(f"    - group: gateway.networking.k8s.io\n      kind: HTTPRoute\n      name: {route}\n"
                       for _, route in routes)
        policies.append((f"capabilities-mcp-{cls}", ns.pop(), refs, requires[cls] + exprs))
    docs = [f"apiVersion: agentgateway.dev/v1alpha1\nkind: AgentgatewayPolicy\nmetadata:\n"
            f"  name: {name}\n  namespace: {ns}\nspec:\n  targetRefs:\n{refs}"
            f"  traffic:\n    authorization:\n      action: Require\n      policy:\n"
            f"        matchExpressions:\n" + "".join(f"          - '{e}'\n" for e in exprs)
            for name, ns, refs, exprs in policies]
    text = HEADER + "---\n".join(docs)
    if not errors:
        # Every expression is written between single quotes: one that held a quote would parse back
        # as something else, so the file must parse back to exactly what was rendered.
        held = [d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]
                for d in yaml.safe_load_all(text) if d]
        if held != [exprs for *_, exprs in policies]:
            errors.append(f"{CAPABILITIES}: the rendering does not parse back to its expressions")
    return text
```

(h) In `render`:
- Add `mcp_routes = {}` before `served = set()`.
- In the Allow-policy loop, right after `served.add(cls)`, add:

  ```python
          mcp_routes.setdefault(cls, []).extend((d["metadata"].get("namespace"), t.get("name"))
                                                for t in d["spec"].get("targetRefs") or [] if t.get("kind") == "HTTPRoute")
  ```
- Change the call to `capabilities = render_capabilities(root, profiles, mcp_routes, errors)`.

- [ ] **Step 4: Run the tests, then write the header**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | tail -3
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-capabilities.py --write
git diff --stat
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | tail -1
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities.sh
```

Expected:
- The first run fails only `today's profiles render today's … policy-capabilities.yaml` and
  `--write rebuilds policy-capabilities.yaml …`, because the committed header is still P2's.
- `--write` prints `wrote infrastructure/base/agent-gateway/policy-capabilities.yaml`.
- The diff touches that file's header lines only: no profile has a `when` yet, so there is no
  argument policy.
- Then `all passed`, and two `is its profiles' rendering` lines.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/gen-capabilities.py scripts/ci/tests/test-gen-capabilities.py infrastructure/base/agent-gateway/policy-capabilities.yaml
git commit -m "feat(agent-gateway): the capability generator renders argument rules (P3)"
```

---

### Task 2: AG6 holds the argument rules on the MCP routes

**Files:**
- Modify: `scripts/ci/flux-schema/assert-agent-gateway.py` (AG6's docstring, `argument_rule`,
  `check_mcp_authz`)
- Test: `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`

- [ ] **Step 1: Write the failing test**

In `test-assert-agent-gateway.py`:

(a) After `model_rule`, add:

```python
def argument(prof, listener, value="secret"):
    """A P3 argument rule as gen-capabilities.py renders it."""
    return (f'!("{prof.aud_prefix}.reviewer.{listener}" in jwt.aud && default(mcp.tool.target, "") == "room-broker"'
            f' && default(mcp.tool.name, "") == "room_read") || default(mcp.tool.arguments.kind, "").lowerAscii() != "{value}"')
```

(b) In `compliant()`, right after the `agent-mcp-public` AgentgatewayPolicy, add:

```python
        obj("AgentgatewayPolicy", rns, "capabilities-mcp-public", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-mcp-public"}],
            "traffic": {"authorization": {"action": "Require", "policy": {"matchExpressions": [
                gate.sub_prefix(prof), argument(prof, "public")]}}}}),
```

(c) Replace `print("main")` with:

```python
print("AG6 argument rules (capability profiles P3)")


def arg_authz(o):
    return spec_at(o, "AgentgatewayPolicy", "capabilities-mcp-public", "traffic", "authorization")


def arg_expr(o, value):
    arg_authz(o)["policy"]["matchExpressions"][1] = value


R = gate.PROFILES[REAL]
expect("an upper-case value, which the folded argument never equals, fails",
       lambda o: arg_expr(o, argument(R, "public", "Secret")), "AG6", "not one argument rule")
expect("the unfolded form fails", lambda o: arg_expr(o, 'mcp.tool.arguments.kind != "Secret"'), "AG6", "not one argument rule")
expect("an appended || true fails", lambda o: arg_expr(o, argument(R, "public") + " || true"), "AG6", "not one argument rule")
expect("a body read fails", lambda o: arg_authz(o)["policy"]["matchExpressions"].append(
    'json(request.body).method != "tools/call"'), "AG6", "not one argument rule")
expect("an internal audience on a public MCP route fails",
       lambda o: arg_expr(o, argument(R, "internal")), "AG6", "binds a internal audience")
expect("Allow instead of Require fails", lambda o: arg_authz(o).update({"action": "Allow"}), "AG6", "must Require")
expect("no repeated sub prefix fails", lambda o: arg_authz(o)["policy"]["matchExpressions"].pop(0), "AG6", "must Require")
check("the gate's grammar takes the generator's rule", bool(gate.argument_rule(R).match(
    gen.argument_rule("reviewer", "internal", "flux-operator-mcp", "get_kubernetes_resources", "kind", "Secret"))))

print("main")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py | grep -v '^  ok'
```

Expected: seven `FAIL` lines from the AG6 argument section, then a traceback ending
`AttributeError: module 'assert_agent_gateway' has no attribute 'argument_rule'`. The compliant
bundle, which now carries `capabilities-mcp-public`, still passes `main`.

- [ ] **Step 3: The gate**

In `assert-agent-gateway.py`:

(a) Replace AG6's docstring paragraph with:

```
  AG6  Every MCP authorization is an Allow list whose expressions are each one
       complete alternative (role AND target AND tool names), for the route's
       own class: Allow expressions are OR-ed at runtime (PoC N7). A route-level
       authorization on an MCP route (capability profiles P3: 1.6's
       mcpAuthorization cannot read arguments) is a Require holding the
       listener's sub prefix, repeated, and argument rules only, each in
       argument_rule's one form for an audience of the route's class. Its value
       is lower case: the rule folds the argument, so an upper-case value would
       never match and the rule would refuse nothing.
```

(b) After `alternative`, add:

```python
def argument_rule(prof):
    """P3's grammar, as gen-capabilities.py renders it: one audience's call of one tool never carries one
    argument value, compared folded. Reused by test-agent-mcp-scope."""
    return re.compile(
        rf'^!\("{re.escape(prof.aud_prefix)}\.(?P<role>[a-z]+)\.(?P<cls>public|internal)" in jwt\.aud'
        r' && default\(mcp\.tool\.target, ""\) == "(?P<target>[a-z0-9-]+)"'
        r' && default\(mcp\.tool\.name, ""\) == "(?P<tool>[a-z0-9_]+)"\)'
        r' \|\| default\(mcp\.tool\.arguments\.(?P<arg>[A-Za-z_][A-Za-z0-9_]*), ""\)\.lowerAscii\(\)'
        r' != "(?P<value>[a-z0-9._/-]+)"$')
```

(c) In `check_mcp_authz`, before `return out`, add:

```python
    mcp_backends = {key(b) for b in kind(objs, "AgentgatewayBackend") if spec_of(b).get("mcp")}
    for g, prof in profiled(objs):
        grammar = argument_rule(prof)
        for p in policies(objs):
            authz = (spec_of(p).get("traffic") or {}).get("authorization")
            names = {t.get("name") for t in spec_of(p).get("targetRefs") or [] if t.get("kind") in ROUTE_KINDS}
            routes = [r for r in routes_on(objs, g) if meta(r).get("name") in names
                      and meta(r).get("namespace") == meta(p).get("namespace") and backend_refs(r) & mcp_backends]
            if authz is None or not routes:
                continue
            classes = {s for r in routes for s in listeners_of(r, g)}
            exprs = (authz.get("policy") or {}).get("matchExpressions") or []
            if authz.get("action") != "Require" or sub_prefix(prof) not in exprs:
                out.append(f"AG6: {ref(p)} on an MCP route must Require {sub_prefix(prof)}: the listener's rule, repeated")
            for e in exprs:
                if e == sub_prefix(prof):
                    continue
                m = grammar.match(e)
                if not m:
                    out.append(f"AG6: {ref(p)} expression is not one argument rule (P3): {e}")
                elif m.group("cls") not in classes:
                    out.append(f"AG6: {ref(p)} binds a {m.group('cls')} audience on {sorted(classes)} routes: {e}")
```

- [ ] **Step 4: Run it and watch it pass**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py | tail -1
```

Expected: `all passed` (or the file's own success line), with no `FAIL`.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/flux-schema/assert-agent-gateway.py scripts/ci/tests/flux-schema/test-assert-agent-gateway.py
git commit -m "feat(agent-gateway): AG6 holds the argument rules on the MCP routes"
```

---

### Task 3: The wire test calls `get_kubernetes_resources` through the pinned gateway

**Files:**
- Modify: `scripts/ci/tests/test-agent-capabilities-wire.sh`

The suite renders the committed profiles; only the models of `reviewer.internal` are narrowed. No
profile carries a `when` until Task 4, so this task's run is the red one: no argument policy is
rendered, and the two Secret cases reach the server.

- [ ] **Step 1: The fake server, the route and the cases**

(a) In the header comment, after `(design P2, P4; gate items 1 and 3).`, add:
`And its argument rule (P3, gate item 2): the internal MCP route, its Allow list and the rendered
capabilities-mcp-internal in front of a fake flux-operator-mcp.`

(b) Add the MCP server's port and process:
- `mcp_port="$(free_port)"` joins the `up_port=…` line.
- `mcp_pid=""` goes next to `fake_pid=""`.
- The trap gains `[ -n "$mcp_pid" ] && kill "$mcp_pid" 2>/dev/null;`.

(c) After `python3 "$tmp/fake.py" … & fake_pid=$!`, add:

```bash
cat > "$tmp/fake_mcp.py" <<'PY'
"""Stands in for flux-operator-mcp: answers the handshake, lists two tools, records each tools/call."""
import http.server, json, sys
PORT, OUT = int(sys.argv[1]), sys.argv[2]
TOOLS = [{"name": n, "inputSchema": {"type": "object"}} for n in ("search_flux_docs", "get_kubernetes_resources")]
class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, code, body=b"", kind="application/json"):
        self.send_response(code)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        msg = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        if "id" not in msg:  # a notification
            return self.reply(202)
        method = msg.get("method")
        if method == "initialize":
            result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake-flux-operator-mcp", "version": "0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            with open(OUT, "a") as f:
                f.write(json.dumps(msg["params"]) + "\n")
            result = {"content": [{"type": "text", "text": "ok"}], "isError": False}
        else:
            result = {}
        self.reply(200, json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}).encode())
    def do_GET(self):
        self.reply(405)
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
PY
python3 "$tmp/fake_mcp.py" "$mcp_port" "$tmp/mcp.jsonl" & mcp_pid=$!
```

(d) In the gateway-config Python:
- Pass `$mcp_port` as a sixth word of `PORTS`, and read it as
  `port, admin, ready, stats, upstream, mcp_port = os.environ["PORTS"].split()`.
- Before `jwt = listener[…]`, add:

```python
mcp_docs = docs(f"{gw}/mcp.yaml")
allow = next(d for d in mcp_docs if d["kind"] == "AgentgatewayPolicy" and d["metadata"]["name"] == "agentgateway-mcp-internal")
mcp_route = next(d for d in mcp_docs if d["kind"] == "HTTPRoute" and d["metadata"]["name"] == "agentgateway-mcp-internal")
args = next((d for d in docs(f"{gw}/policy-capabilities.yaml") if d["metadata"]["name"] == "capabilities-mcp-internal"), None)
mcp_policies = {"mcpAuthorization": {"rules": [
    {"allow": e} for e in allow["spec"]["backend"]["mcp"]["authorization"]["policy"]["matchExpressions"]]}}
if args:  # absent while no profile constrains a tool: nothing then binds arguments, and the Secret cases fail
    mcp_policies["authorization"] = {"rules": [
        {"require": e} for e in args["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]]}
routes.append({"name": "mcp",
               "matches": [{"path": {"pathPrefix": mcp_route["spec"]["rules"][0]["matches"][0]["path"]["value"]}}],
               "policies": mcp_policies,
               "backends": [{"mcp": {"prefixMode": "always", "statefulMode": "stateless", "targets": [
                   {"name": "flux-operator-mcp", "mcp": {"host": f"http://127.0.0.1:{mcp_port}/mcp"}}]}}]})
```

(e) Before `[ "$fails" -eq 0 ] || …`, add:

```bash
# rpc <aud> <JSON-RPC message>: prints "<status> <arguments of the tools/call the server saw, or ->".
rpc() {
  : > "$tmp/mcp.jsonl"
  local code
  code="$(curl -s -o "$tmp/rpc.out" -w '%{http_code}' --max-time 10 "http://127.0.0.1:$gw_port/mcp" \
    -H "authorization: Bearer $(cat "$tmp/$1.jwt")" -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' -H 'mcp-protocol-version: 2025-06-18' -d "$2")"
  echo "$code $(python3 -c 'import json,sys; l=open(sys.argv[1]).read().splitlines(); print(json.dumps(json.loads(l[-1])["arguments"], sort_keys=True, separators=(",", ":")) if l else "-")' "$tmp/mcp.jsonl")"
}
tool() {  # tool <aud> <tool> <arguments JSON>
  rpc "$1" "{\"jsonrpc\": \"2.0\", \"id\": 7, \"method\": \"tools/call\", \"params\": {\"name\": \"flux-operator-mcp_$2\", \"arguments\": $3}}"
}
passes() {  # passes <what> <status and rest>: anything but the rule's 403
  [ "${2%% *}" != 403 ] && echo "ok    $1 (${2%% *})" || fail "$1: refused 403"
}

echo "the argument rule (P3, gate item 2)"
passes "initialize passes the rule" "$(rpc $R '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "wire", "version": "0"}}}')"
passes "a notification passes the rule" "$(rpc $R '{"jsonrpc": "2.0", "method": "notifications/initialized"}')"
expect "tools/list passes the rule" "200 -" "$(rpc $R '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}')"
grep -q 'flux-operator-mcp_get_kubernetes_resources' "$tmp/rpc.out" \
  && echo "ok    the constrained tool is still listed (gate item 4)" || fail "tools/list lost get_kubernetes_resources"
expect "kind Secret is refused 403, the server untouched" "403 -" \
  "$(tool $R get_kubernetes_resources '{"apiVersion": "v1", "kind": "Secret"}')"
expect "kind secret, folded, is refused 403" "403 -" "$(tool $R get_kubernetes_resources '{"apiVersion": "v1", "kind": "secret"}')"
expect "kind Pod reaches the server" '200 {"apiVersion":"v1","kind":"Pod"}' \
  "$(tool $R get_kubernetes_resources '{"apiVersion": "v1", "kind": "Pod"}')"
expect "no kind reaches the server, which answers it" '200 {"apiVersion":"v1"}' "$(tool $R get_kubernetes_resources '{"apiVersion": "v1"}')"
expect "another tool's argument is not the rule's" '200 {"query":"Secret"}' "$(tool $R search_flux_docs '{"query": "Secret"}')"
passes "a GET passes the rule (the stateless backend answers it)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  "http://127.0.0.1:$gw_port/mcp" -H "authorization: Bearer $(cat "$tmp/$R.jwt")" -H 'accept: text/event-stream')"
```

- [ ] **Step 2: Run it and watch it fail** (needs a Docker daemon; see Global Constraints)

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities-wire.sh | grep -v '^ok'
```

Expected: the two Secret cases fail, `want '403 -', got '200 {"apiVersion":"v1","kind":"Secret"}'`
(and the same with `secret`), then `2 failure(s)`. Every other case and every P2 case is `ok`. A
failure anywhere else is a finding about the rendering, not about the missing profile. Handle it as
the "Verified from source" paragraph says, before Task 4.

- [ ] **Step 3: Commit** (red until Task 4, which turns the suite green; the PR carries both)

```bash
git add scripts/ci/tests/test-agent-capabilities-wire.sh
git commit -m "test(agent-gateway): the wire test calls get_kubernetes_resources through the pinned gateway"
```

---

### Task 4: `get_kubernetes_resources` never reads a Secret

**Files:**
- Modify: `scripts/ci/tests/test-agent-mcp-scope.sh`
- Modify: `infrastructure/base/agent-gateway/profiles/{reviewer,tester,triager}.internal.yaml`
- Regenerate: `infrastructure/base/agent-gateway/policy-capabilities.yaml`

- [ ] **Step 1: Freeze the expected rules in the scope suite**

In `test-agent-mcp-scope.sh`:

(a) In the header comment, after `(capability profiles design, gate 4).`, add:
`get_kubernetes_resources never runs with kind Secret: the profiles' when and
policy-capabilities.yaml hold exactly the frozen argument rules (P3), read independently.`

(b) After the profiles block (the loop ending in
`errors.append(f"profiles: {aud} grants {got.get(aud)}, expected {want.get(aud)}")`), add:

```python
# --- P3: the argument rules, frozen like the sets above: every role that holds get_kubernetes_resources
#     never calls it with kind Secret. The profiles' `when` and policy-capabilities.yaml must both hold
#     exactly these, each read here on its own so a generator bug cannot hide a missing rule. ---
NO_SECRET = {("flux-operator-mcp", "get_kubernetes_resources"): ("kind", "secret")}
EXPECTED_ARGUMENT_RULES = {aud: NO_SECRET for per_route in EXPECTED_ROLE_TOOLS.values() for aud, grants in per_route.items()
                           if "get_kubernetes_resources" in grants.get("flux-operator-mcp", set())}
WHEN = re.compile(r'^mcp\.tool\.arguments\.([A-Za-z_][A-Za-z0-9_]*) != "([^"]+)"$')
got = {}
for fname in sorted(os.listdir(PROFILE_DIR)) if os.path.isdir(PROFILE_DIR) else []:
    if not fname.endswith(".yaml"):
        continue
    prof = yaml.safe_load(open(os.path.join(PROFILE_DIR, fname))) or {}
    for target, names in (prof.get("tools") or {}).items():
        for n in names:
            if isinstance(n, dict):
                m = WHEN.match(str(n.get("when")))
                if not m:
                    errors.append(f"profiles/{fname}: {target} {n.get('name')}: when outside the one form: {n.get('when')}")
                    continue
                got.setdefault(f"agent-router.{prof.get('role')}.{prof.get('dataClass')}", {})[(target, n.get("name"))] = \
                    (m.group(1), m.group(2).lower())
if got != EXPECTED_ARGUMENT_RULES:
    errors.append(f"profiles: argument rules are {got}, expected {EXPECTED_ARGUMENT_RULES}")
args = _agw.argument_rule(_agw.PROFILES[("agent-gateway", "agent-router")])
CAPS_FILE = os.path.join(root, "infrastructure/base/agent-gateway/policy-capabilities.yaml")
got = {}
for pol in (d for d in yaml.safe_load_all(open(CAPS_FILE)) if d):
    if not {t.get("name") for t in pol["spec"]["targetRefs"]} & set(AGW_ROUTES):
        continue
    for e in pol["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]:
        m = args.match(e)
        if m:
            got.setdefault(f"agent-router.{m['role']}.{m['cls']}", {})[(m["target"], m["tool"])] = (m["arg"], m["value"])
        elif not e.startswith("jwt.sub.startsWith("):
            errors.append(f"policy-capabilities.yaml: {pol['metadata']['name']}: outside the argument grammar: {e}")
if got != EXPECTED_ARGUMENT_RULES:
    errors.append(f"policy-capabilities.yaml: argument rules are {got}, expected {EXPECTED_ARGUMENT_RULES}")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-mcp-scope.sh
```

Expected: exit 1. Two lines, `profiles: argument rules are {}, expected {…}` and
`policy-capabilities.yaml: argument rules are {}, expected {…}`, each naming
`agent-router.reviewer.internal`, `agent-router.tester.internal` and `agent-router.triager.internal`.

- [ ] **Step 3: The profiles, then the rendering**

In `reviewer.internal.yaml`, `tester.internal.yaml` and `triager.internal.yaml`, replace
`    - get_kubernetes_resources` with:

```yaml
    - {name: get_kubernetes_resources, when: 'mcp.tool.arguments.kind != "Secret"'}
```

After the `# models is rendered …` comment line of each of the three files, add:

```yaml
# A tool's when is rendered into policy-capabilities.yaml (P3): a call carrying the value it excludes answers 403.
```

Then render:

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-capabilities.py --write
git diff --stat infrastructure/base/agent-gateway/
```

Expected:
- `wrote …/policy-capabilities.yaml`, and `mcp.yaml is its profiles' rendering`, untouched.
- The policy file gains one document, `capabilities-mcp-internal`, targeting HTTPRoute
  `agentgateway-mcp-internal` in `agent-system`.
- Its expressions are the listener's Require followed by three argument rules, in this order:
  reviewer, tester, triager. Each reads
  `!("agent-router.<role>.internal" in jwt.aud && default(mcp.tool.target, "") == "flux-operator-mcp" && default(mcp.tool.name, "") == "get_kubernetes_resources") || default(mcp.tool.arguments.kind, "").lowerAscii() != "secret"`.

- [ ] **Step 4: Every suite this touches, green**

```bash
for s in test-agent-mcp-scope.sh test-agent-capabilities.sh test-agent-capabilities-wire.sh; do
  echo "== $s"; bash $SCRATCH/run-suite.sh bash scripts/ci/tests/$s | tail -1; done
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | tail -1
```

Expected:
- `PASS` for the scope suite.
- `… is its profiles' rendering` twice for `test-agent-capabilities`.
- `PASS` for the wire suite. With no Docker daemon it prints `SKIP: no docker daemon`; CI decides.
- `all passed` for the generator test. Its golden runs on profiles stripped of their `when`, so the
  new profiles do not move it.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/tests/test-agent-mcp-scope.sh infrastructure/base/agent-gateway/profiles/reviewer.internal.yaml \
  infrastructure/base/agent-gateway/profiles/tester.internal.yaml infrastructure/base/agent-gateway/profiles/triager.internal.yaml \
  infrastructure/base/agent-gateway/policy-capabilities.yaml
git commit -m "feat(agent-gateway): get_kubernetes_resources never reads a Secret (capability profiles P3)"
```

---

### Task 5: The gateways page, the status row and the spec

**Files:**
- Modify: `website/content/docs/platform/ai-platform/gateways.md`
- Modify: `website/content/docs/platform/ai-platform/status.md`
- Modify: `docs/superpowers/specs/2026-10-21-capability-profiles-design.md`

- [ ] **Step 1: The gateways page**

In the Identity table, after the row
`| The model the call reaches is one the caller's profile names | … | 403 |`, add:

```markdown
| A tool call carries no argument value the caller's profile excludes (today: `get_kubernetes_resources` with `kind: Secret`) | `capabilities-mcp-<listener>` on the MCP route (`policy-capabilities.yaml`) | 403 |
```

After the paragraph ending `refuse a model the factory's tiers pin.`, add:

```markdown

The arguments are generated too. A tool in a profile may read
`{name: <tool>, when: 'mcp.tool.arguments.<argument> != "<value>"'}`, the one form the generator
takes. It becomes a route-level `Require` on the listener's MCP route (`capabilities-mcp-<listener>`),
because agentgateway 1.6's `mcpAuthorization` cannot read arguments. A call that carries the excluded
value, compared case-insensitively, is refused 403 before it reaches the server. The tool stays listed,
and a call without the argument reaches the server, which answers it. One rule exists today:
`get_kubernetes_resources` never with `kind: Secret`, for every role that has the tool. It adds to the
Flux MCP server's own RBAC, which grants no Secret. The harness's OpenHands SDK keeps its MCP session
after such a 403 (since 1.55), so the run keeps its other tools.
```

- [ ] **Step 2: The status row**

In `status.md`, in the Capability profiles row, replace:

```markdown
and argument constraints (P3) are not built yet ([design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-21-capability-profiles-design.md))
```

with:

```markdown
and argument constraints (P3) are built: `get_kubernetes_resources` never reads a Secret, refused 403 at the gateway, with its live check waiting on a gcp-0 session ([design](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-21-capability-profiles-design.md))
```

The badge stays `built, off`: the sidecar half is still off.

- [ ] **Step 3: The spec**

(a) Status line: replace
`built ([plan](../plans/2026-10-22-capability-profiles-p2-p4-plan.md)) · **Part of:** the` with:

```markdown
built ([plan](../plans/2026-10-22-capability-profiles-p2-p4-plan.md)); **2026-10-27**: P3, the
argument constraints, is built ([plan](../plans/2026-10-27-capability-profiles-p3-plan.md)) ·
**Part of:** the
```

(b) In P3's row, replace
`a 403 instead of a hidden tool is not acceptable: the SDK's MCP client does not survive one (see the [S0 result](#gate-the-spike-and-the-live-checks))`
with:

```markdown
a refused call answers 403 rather than hiding the tool, which the harness's SDK survives since 1.55 (see the [S0 result](#gate-the-spike-and-the-live-checks))
```

(c) In "What the generator emits", in the Enforces cell, replace
`` `tools[].when`: superseded by the S0 result (deny at the JSON-RPC level or ExtMCP, not a 403) `` with
`` `tools[].when`: 403 on a `tools/call` carrying the excluded value, from `capabilities-mcp-<listener>` on the MCP route (P3) ``.

(d) Gate item 2: replace

```markdown
2. Superseded by the S0 result (deny at the JSON-RPC level or ExtMCP, not a 403): `get_kubernetes_resources`
   with `kind: Secret` from a reviewer is refused; without the argument it answers.
```

with:

```markdown
2. `get_kubernetes_resources` with `kind: Secret` from a reviewer is refused 403; with another kind,
   or without the argument, it answers, and the run's later MCP calls succeed.
```

(e) Append to the end of the file:

```markdown

Ruled in P3 ([plan](../plans/2026-10-27-capability-profiles-p3-plan.md#this-plans-rulings)):

- **The rule is route-level, in its own policy.** agentgateway 1.6 sets `mcp.tool.arguments` for HTTP
  request policies only. `mcpAuthorization` sees the tool's target and name, not its arguments. Each
  listener whose profiles constrain a tool gets `capabilities-mcp-<listener>` on its MCP route. Sharing
  `capabilities-<listener>` would AND the model rule into every MCP call.
- **`when` takes one form, `mcp.tool.arguments.<argument> != "<value>"`.** The generator renders it
  as `!(<aud> && <target> && <tool>) || default(mcp.tool.arguments.<argument>, "").lowerAscii() !=
  "<value>"`, with one Require per role and tool. Any other request, and a call without the argument,
  passes; a non-string value is refused. AG6 and `test-agent-mcp-scope` parse the same form.
- **The 403 is accepted.** Every harness a run can get pins OpenHands SDK 1.56.0, which keeps its MCP
  session after a refused `tools/call` (S0's re-run, measured by the SDK 1.56 plan).
- **The first rule binds every role that holds the tool**: the reviewer, the tester and the triager
  on `internal`.
```

- [ ] **Step 4: Links**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/validate-links.sh
```

Expected: `==> All relative Markdown links resolve`.

- [ ] **Step 5: Commit**

```bash
git add website/content/docs/platform/ai-platform/gateways.md website/content/docs/platform/ai-platform/status.md \
  docs/superpowers/specs/2026-10-21-capability-profiles-design.md docs/superpowers/plans/2026-10-27-capability-profiles-p3-plan.md
git commit -m "docs(agent-gateway): capability profiles P3, the argument rule, built"
```

---

### Task 6: Verify, push, open the PR; the live check

- [ ] **Step 1: The gate: `task check`**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|test-gen-capabilities|test-agent-capabilities|mcp-scope|test-assert-agent-gateway|passed,|resolve|docs site exists|exit=" \
  "$SCRATCH/check-$(basename "$PWD").log"
```

Expected:
- `assert-agent-gateway: 15 checks, 0 violations (clusters: aws-0, gcp-0)`. AG6 now reads
  `capabilities-mcp-internal` in both clusters' renders.
- `PASS` for `test-gen-capabilities`, `test-agent-capabilities`, `test-agent-mcp-scope` and
  `flux-schema/test-assert-agent-gateway`.
- `test-agent-capabilities-wire`: `PASS` with a Docker daemon, `SKIP` without one.
- `0 failed`. This plan adds no suite, so the passed and skipped counts equal `origin/main`'s.
- Links, the site build and the doc paths pass; `exit=0`.

- [ ] **Step 2: Pre-commit, rebase, push**

```bash
pre-commit run --all-files
git fetch origin && git rebase origin/main
git push -u origin feat/capability-profiles-p3
```

If the rebase touched a file this PR changes, run Step 1 again before pushing.

- [ ] **Step 3: Open the pull request**

Title: `feat(agent-gateway): capability profiles P3, get_kubernetes_resources never reads a Secret`.

The body, in English:
- **Outcome:** a 403 at the gateway; tool lists unchanged; server RBAC already refuses the call.
- **Rulings:** R1 to R8, with the agentgateway v1.6.0 source lines behind R1, R3 and R4.
- **Harness SDK pin:** 1.56.0 in both harness images.
- **Suites and gate:** the suites and AG6's amendment.
- **`task check` summary.**
- **Test plan:**
  - a hand edit of `policy-capabilities.yaml` fails `test-agent-capabilities`;
  - CI shows `PASS  test-agent-capabilities-wire` with the P3 cases.
- **What waits:** the live check below.

No attribution line.

- [ ] **Step 4: Wait for CI and read the wire test**

```bash
gh pr checks --watch
gh run view --log "$(gh run list --branch feat/capability-profiles-p3 -L 1 --json databaseId -q '.[0].databaseId')" \
  | grep -E "test-agent-capabilities-wire|argument rule|passed,"
```

Expected: every check is green. `PASS  test-agent-capabilities-wire` shows, with its P3 cases `ok`.

- [ ] **Step 5: The one live check, in the next gcp-0 session** (gate item 2, end to end)

The live check proves the two things the offline tests cannot: the controller's translation of
`capabilities-mcp-internal`, and the real harness's MCP client surviving the 403.

1. Start a reviewer run on `internal` on gcp-0, through the factory, with the harness the
   composition pins.
2. Have it call, in this order:
   1. `flux-operator-mcp_get_kubernetes_resources` with `{apiVersion: v1, kind: Secret, namespace: agent-system}`;
   2. the same tool with `kind: Pod`;
   3. `room-broker_room_post`.
3. Pass if all of these hold:
   - the first call returns an error observation;
   - the agent-router access log has a line with `http.status=403`, `reason=Authorization` and the
     run's `jwt.sub`;
   - flux-operator-mcp logs no request for it;
   - the second and third calls succeed in the same conversation.

Record the result in the spec's Gate section, item 2.
