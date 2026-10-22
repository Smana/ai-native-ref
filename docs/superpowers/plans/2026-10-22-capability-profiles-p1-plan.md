# Capability profiles, P1: the profiles and a generator at parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One profile per role and data class declares today's MCP tools, `mcp.yaml`'s two Allow
lists are generated from those profiles byte for byte, and a suite fails when the committed lists
drift from them.

**Architecture:** Eight YAML profiles under `infrastructure/base/agent-gateway/profiles/`.
`scripts/ci/gen-capabilities.py` reads them and rewrites only the `matchExpressions` items of the two
MCP authorization policies in `mcp.yaml`. A policy's class is the listener its route attaches to.
Roles come in name order, targets in the backend's order and tools in the profile's order, which is
exactly how today's file is written. Three suites hold the result:

- `test-agent-mcp-scope` checks the profiles against today's frozen per-role sets (design gate 4).
- `test-gen-capabilities` unit-tests the generator on copies of the tree.
- `test-agent-capabilities` fails when the committed lists differ from the rendering (gate 5). AG8
  holds the budget cost string to `meter.prices` the same way.

Nothing that reaches a cluster changes: kustomize renders the agent-gateway root byte-identical
before and after.

**Tech Stack:** Python 3 with PyYAML, Bash suites run by `scripts/ci/run-tests.sh` inside
`.composite/`, agentgateway 1.6 `mcpAuthorization` CEL.

**Spec:** [the capability profiles design](../specs/2026-10-21-capability-profiles-design.md),
decision P1 and gates 4 and 5. This plan is the first step of its migration order: "profiles first,
generated files equal to today's hand-written ones, then the new rules, then the composition's
ConfigMap read".

**Out of P1** (later plans): the per-role model allow-lists (P2). The argument constraints (P3),
which wait for spike S0, now running. The per-run model pin (P4). The `agent-capability-profiles`
ConfigMap and the AgentRun composition's read of it, a crossplane-configuration change. The bridge's
read-only map. Gate items 1 to 3.

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **Byte equality by splicing.** The generator owns the `matchExpressions` items of each MCP authorization policy in `mcp.yaml`, and nothing else in the file. The backend, the routes and every comment stay hand-written | Rendering the whole file would turn the backend and routes into a template for no gain. Splicing keeps today's bytes, so parity can be proved with `cmp` |
| R2 | **Order.** Roles render in name order and targets in the order of the `agent-mcp` backend's `targets`. Tools render in the order the profile lists them | Today's file follows exactly this order, so it needs no reordering. A profile's target order then has no effect, which the unit tests show |
| R3 | **Today's tool order, without `when`.** The spec's example profile puts `get_kubernetes_resources` before `get_kubernetes_metrics` and adds a `when`. That example is illustrative. P1 writes the order `mcp.yaml` uses today and no constraint | Required for parity (R2); constraints are P3 |
| R4 | **Fields.** `role`, `dataClass` and `tools` are rendered. `models` is **carried but not rendered**: it must name exactly the aliases the LLM backends serve, since today any role may ask for any of the four. P2 will narrow it and render it. `egress` and `readOnly` are **refused** until the ConfigMap step: their current values live outside this repository (`MCP_READ_ONLY_TOOLS` in crossplane-configuration's AgentRun composition, and the run API's egress profiles), so a copy here would be checked by nothing. A tool's `when` is refused until P3 | A field that nothing enforces must not look like a rule. `models` can be checked here, against the backends' `modelAliases`, so it is carried. It also makes P2's change a reviewable narrowing of each profile |
| R5 | **The drift gate is a suite, not a new gate id in `assert-agent-gateway.py`.** (1) The profiles are not Kubernetes objects and reach no bundle until the ConfigMap step. (2) The property being checked is the committed file's bytes, which a render loses. (3) No overlay patches these policies: both clusters' `agent-gateway` kustomizations are bare `resources: [../../base/agent-gateway]`. The suite follows AG8's pattern: it regenerates the expected value from its source on every run, and its failure prints the fix. AG6 keeps checking the rendered expressions on the bundle | A gate id would have to read the source tree, which no AG check does today, and its fixtures would need the profiles. Once the ConfigMap carries the profiles into the bundle, a bundle gate can take this suite's place |
| R6 | **`test-agent-mcp-scope` keeps its frozen expected sets**, the guard from external review M2/M3. It checks the profiles against those sets, parsing the profiles itself rather than through the generator. Its existing check of `mcp.yaml` stays | If expectations were derived from the profiles, editing a profile would update its own test. Parsing independently means a bug in the generator's loader cannot hide a grant |

**Measured 2026-10-22** on a prototype in `$SCRATCH/capprof/` (the code below is that prototype's):

- **Parity:** run on today's `mcp.yaml`, the generator prints `is its profiles' rendering`.
- **Rebuild from nothing:** with each list cut down to a single placeholder item, `--write` rebuilt
  all 32 expressions, and `cmp` against the committed `mcp.yaml` found no difference.
- **Composite copy:** `test-agent-mcp-scope`, `test-gen-capabilities`, `test-agent-capabilities` and
  `test-assert-agent-gateway` all pass. On the existing bundle the gate reports
  `assert-agent-gateway: 14 checks, 0 violations`.
- **Boundary and render:** the host's `check-ai-boundary.py` passes with 0 crossings. The kustomize
  render of `infrastructure/aws-0/agent-gateway` is byte-identical with the profiles in place.
- **Gate 5:** a hand edit to a list fails `test-agent-capabilities` with the diff.

## Global Constraints

- **Branch:** work on `feat/capability-profiles-p1`, which carries this plan, in its own worktree.
  In a new worktree, run `mise trust mise.toml` once. Rebase onto a freshly fetched `origin/main`
  before every push.
- **`$SCRATCH`** is a scratch directory outside the repository. It holds two helpers:
  - `check.sh <worktree>` runs `task check` with a `python3` that has PyYAML ahead of mise's. It
    logs to `$SCRATCH/check-<worktree directory name>.log` and ends the log with `exit=N`.
  - `run-suite.sh <command…>` runs one command with that `python3`.
  The `python3` on `PATH` lacks PyYAML, so every Python and suite command below goes through one of
  the two helpers.
- **`task check` is the evidence** (AGENTS.md). Never claim done without its log.
- **Run `test-agent-mcp-scope` inside the composite.** It imports `assert-agent-gateway.py`, which
  imports the host's `yamlcompat`, and that module exists only in `.composite/`. The command is:
  `bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh && bash $SCRATCH/run-suite.sh bash .composite/scripts/ci/tests/test-agent-mcp-scope.sh`.
  `host-profile.sh` copies the working tree as it is on disk, untracked files included.
- **`__pycache__/` is not ignored here.** Run `export PYTHONDONTWRITEBYTECODE=1` in the shell first,
  and `git add` named paths only, never `-A`.
- **The suite contract:** line 1 is the shebang and line 2 is `# requires: <tools>`. Exit 77 is a
  SKIP. Suites read the real tree. `run-tests.sh` runs them inside `.composite/` and finds them with
  `git ls-files`, so a new suite counts only once it is committed.
- **Host scripts are never vendored.** The generator is this repository's own CI script, like
  `check-sources.sh`. It imports nothing from the host.
- **No new workload in P1.** The rendered objects are unchanged, so the platform constitution's
  workload rules gain nothing new to apply to.
- **Commits** are conventional, in English, with **no trailers**.
- **Verbatim from the spec:**
  - Profiles live at `infrastructure/base/agent-gateway/profiles/` and the generator at
    `scripts/ci/gen-capabilities.py`.
  - Gate 4: "`tools/list` per role is unchanged from today, and `test-agent-mcp-scope` passes from
    the profiles".
  - Gate 5: "Editing a rendered policy by hand fails the drift gate".
- **Parity is the acceptance criterion.** At every commit, the generated lists are byte-identical to
  today's. Any diff inside a `matchExpressions` list is a bug in this plan's execution.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `infrastructure/base/agent-gateway/profiles/{implementer,reviewer,tester,triager}.{public,internal}.yaml` | create: 8 files | One role × class each. `tools` is rendered; `models` is carried and checked |
| `scripts/ci/tests/test-agent-mcp-scope.sh` | modify: header and one block | The profiles grant today's sets (gate 4) |
| `scripts/ci/gen-capabilities.py` | create | Renders `mcp.yaml`'s Allow lists from the profiles: checks by default, `--write` writes |
| `scripts/ci/tests/test-gen-capabilities.py` | create | The generator's unit tests, run on temporary copies of the tree |
| `scripts/ci/tests/test-agent-capabilities.sh` | create | The drift gate (gate 5) |
| `infrastructure/base/agent-gateway/mcp.yaml` | modify: comments only | Says the lists are generated, and from what |
| `docs/runbooks/agent-factory/06-mcp.md` | modify: one sentence | Points readers to the profiles |
| `website/content/docs/platform/ai-platform/gateways.md` | modify: one paragraph | How the lists are made |
| `docs/superpowers/specs/2026-10-21-capability-profiles-design.md` | modify: status line and "Left to the builder" | Records that P1 is built and the rulings above |

---

### Task 1: The eight profiles, held to today's access

**Files:**
- Create: `infrastructure/base/agent-gateway/profiles/implementer.public.yaml`,
  `reviewer.public.yaml`, `tester.public.yaml`, `triager.public.yaml`,
  `implementer.internal.yaml`, `reviewer.internal.yaml`, `tester.internal.yaml`,
  `triager.internal.yaml` (all in `profiles/`)
- Modify: `scripts/ci/tests/test-agent-mcp-scope.sh`: the header (line 6), and a new block after the
  `seen_policies` check (line 151)

**Interfaces:**
- Produces: the profile format that Task 2's generator reads:
  - Top-level keys: exactly `role`, `dataClass`, `models` and `tools`.
  - `tools`: a mapping from target (`flux-operator-mcp`, `mcp-victoriametrics`, `mcp-victorialogs`,
    `room-broker`) to a non-empty list of tool-name strings, in today's order.
  - File names: `<role>.<dataClass>.yaml`.

- [ ] **Step 1: Write the failing test**

In `scripts/ci/tests/test-agent-mcp-scope.sh`, replace:

```bash
# MCP server reads ConfigMaps and pod logs in flux-system only. The real tree.
```

with:

```bash
# MCP server reads ConfigMaps and pod logs in flux-system only. The real tree.
#
# The capability profiles (infrastructure/base/agent-gateway/profiles/) must grant the same sets
# as mcp.yaml's Allow lists (capability profiles design, gate 4).
```

Then replace:

```python
if seen_policies != set(AGW_ROUTES):
    errors.append(f"agent-gateway/mcp.yaml: missing Allow list(s) {sorted(set(AGW_ROUTES) - seen_policies)}")
```

with:

```python
if seen_policies != set(AGW_ROUTES):
    errors.append(f"agent-gateway/mcp.yaml: missing Allow list(s) {sorted(set(AGW_ROUTES) - seen_policies)}")

# --- The capability profiles grant exactly these sets too, read here without the generator so a
#     loader bug cannot hide a grant. A {name, when} entry (P3) still grants its name. ---
PROFILE_DIR = os.path.join(root, "infrastructure/base/agent-gateway/profiles")
want = {aud: grants for per_route in EXPECTED_ROLE_TOOLS.values() for aud, grants in per_route.items()}
got = {}
for fname in sorted(os.listdir(PROFILE_DIR)) if os.path.isdir(PROFILE_DIR) else []:
    if not fname.endswith(".yaml"):
        continue
    prof = yaml.safe_load(open(os.path.join(PROFILE_DIR, fname))) or {}
    aud = f"agent-router.{prof.get('role')}.{prof.get('dataClass')}"
    if aud in got:
        errors.append(f"profiles/{fname}: a second profile for {aud}")
    got[aud] = {target: {n if isinstance(n, str) else n.get("name") for n in names}
                for target, names in (prof.get("tools") or {}).items()}
for aud in sorted(set(got) | set(want)):
    if got.get(aud) != want.get(aud):
        errors.append(f"profiles: {aud} grants {got.get(aud)}, expected {want.get(aud)}")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh bash .composite/scripts/ci/tests/test-agent-mcp-scope.sh; echo "exit=$?"
```

Expected: eight lines of the form `profiles: agent-router.<role>.<class> grants None, expected {…}`,
one per role and class, then `exit=1`.

- [ ] **Step 3: Write the four public profiles**

`infrastructure/base/agent-gateway/profiles/implementer.public.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: implementer
dataClass: public
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
  mcp-victoriametrics:
    - documentation
  mcp-victorialogs:
    - documentation
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
```

`infrastructure/base/agent-gateway/profiles/reviewer.public.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: reviewer
dataClass: public
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
  mcp-victoriametrics:
    - documentation
  mcp-victorialogs:
    - documentation
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_verdict
```

`infrastructure/base/agent-gateway/profiles/tester.public.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: tester
dataClass: public
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
  mcp-victoriametrics:
    - documentation
  mcp-victorialogs:
    - documentation
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
    - room_verdict
```

`infrastructure/base/agent-gateway/profiles/triager.public.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: triager
dataClass: public
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
  mcp-victoriametrics:
    - documentation
  mcp-victorialogs:
    - documentation
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
```

- [ ] **Step 4: Write the four internal profiles**

`infrastructure/base/agent-gateway/profiles/implementer.internal.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
# No get_kubernetes_resources or get_kubernetes_logs, and VictoriaLogs' documentation only
# (external review M2, M3); no role gets VictoriaMetrics' tsdb_status, active_queries or top_queries.
role: implementer
dataClass: internal
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
    - get_flux_instance
    - get_kubernetes_api_versions
    - get_kubernetes_metrics
  mcp-victoriametrics:
    - documentation
    - query
    - query_range
    - metrics
    - metrics_metadata
    - labels
    - label_values
    - series
    - alerts
    - rules
    - explain_query
    - prettify_query
    - metric_statistics
  mcp-victorialogs:
    - documentation
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
```

`infrastructure/base/agent-gateway/profiles/reviewer.internal.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: reviewer
dataClass: internal
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
    - get_flux_instance
    - get_kubernetes_api_versions
    - get_kubernetes_resources
    - get_kubernetes_metrics
    - get_kubernetes_logs
  mcp-victoriametrics:
    - documentation
    - query
    - query_range
    - metrics
    - metrics_metadata
    - labels
    - label_values
    - series
    - alerts
    - rules
    - explain_query
    - prettify_query
    - metric_statistics
  mcp-victorialogs:
    - documentation
    - query
    - hits
    - facets
    - field_names
    - field_values
    - stats_query
    - stats_query_range
    - streams
    - stream_ids
    - stream_field_names
    - stream_field_values
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_verdict
```

`infrastructure/base/agent-gateway/profiles/tester.internal.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: tester
dataClass: internal
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
    - get_flux_instance
    - get_kubernetes_api_versions
    - get_kubernetes_resources
    - get_kubernetes_metrics
    - get_kubernetes_logs
  mcp-victoriametrics:
    - documentation
    - query
    - query_range
    - metrics
    - metrics_metadata
    - labels
    - label_values
    - series
    - alerts
    - rules
    - explain_query
    - prettify_query
    - metric_statistics
  mcp-victorialogs:
    - documentation
    - query
    - hits
    - facets
    - field_names
    - field_values
    - stats_query
    - stats_query_range
    - streams
    - stream_ids
    - stream_field_names
    - stream_field_values
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
    - room_verdict
```

`infrastructure/base/agent-gateway/profiles/triager.internal.yaml`:

```yaml
# Rendered into mcp.yaml by scripts/ci/gen-capabilities.py --write (capability profiles design).
# models is checked against the backends' aliases, not rendered, until P2.
role: triager
dataClass: internal
models: [agent-default, tier-light, tier-standard, tier-frontier]
tools:
  flux-operator-mcp:
    - search_flux_docs
    - get_flux_instance
    - get_kubernetes_api_versions
    - get_kubernetes_resources
    - get_kubernetes_metrics
    - get_kubernetes_logs
  mcp-victoriametrics:
    - documentation
    - query
    - query_range
    - metrics
    - metrics_metadata
    - labels
    - label_values
    - series
    - alerts
    - rules
    - explain_query
    - prettify_query
    - metric_statistics
  mcp-victorialogs:
    - documentation
    - query
    - hits
    - facets
    - field_names
    - field_values
    - stats_query
    - stats_query_range
    - streams
    - stream_ids
    - stream_field_names
    - stream_field_values
  room-broker:
    - room_read
    - room_post
    - room_progress
    - room_handoff
```

- [ ] **Step 5: Run it and watch it pass**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh bash .composite/scripts/ci/tests/test-agent-mcp-scope.sh; echo "exit=$?"
```

Expected: `PASS`, `exit=0`.

- [ ] **Step 6: Prove that it catches a widened profile**

Append `    - get_kubernetes_logs` under `flux-operator-mcp:` in `implementer.internal.yaml`, then repeat
Step 5. Expected: `profiles: agent-router.implementer.internal grants {…'get_kubernetes_logs'…},
expected {…}`, then `exit=1`. Delete the line again (the file is not committed yet, so `git checkout`
cannot restore it), then re-run Step 5 to get `PASS`.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/base/agent-gateway/profiles/ scripts/ci/tests/test-agent-mcp-scope.sh
git commit -m "feat(agent-gateway): capability profiles, one per role and data class, at today's access"
```

---

### Task 2: The generator and its unit tests

**Files:**
- Create: `scripts/ci/gen-capabilities.py`
- Create: `scripts/ci/tests/test-gen-capabilities.py`

**Interfaces:**
- Consumes: Task 1's profiles; `mcp.yaml`'s `agent-mcp` backend, its HTTPRoutes and its two MCP
  authorization policies; the `modelAliases` of the LLM backends in `llm.yaml` and `anthropic.yaml`.
- Produces (Task 3 and later plans rely on these):
  - The CLI: `python3 scripts/ci/gen-capabilities.py [--write] [ROOT]`. Exit 0 means in sync or
    written; exit 1 means drift or an invalid profile, with every problem printed as `FAIL …`.
  - The module constants `GATEWAY`, `PROFILES` and `MCP`, all `PurePosixPath` relative to ROOT.
  - `expression(role, cls, target, tools) -> str`.
  - `render(root) -> tuple[str | None, list[str]]`.
  - `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

`scripts/ci/tests/test-gen-capabilities.py`:

```python
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
```

- [ ] **Step 2: Run it and watch it fail**

```bash
chmod +x scripts/ci/tests/test-gen-capabilities.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py; echo "exit=$?"
```

Expected: `FileNotFoundError: … scripts/ci/gen-capabilities.py`, then `exit=1`.

- [ ] **Step 3: Write the generator**

`scripts/ci/gen-capabilities.py`:

```python
#!/usr/bin/env python3
"""Render the agent router's MCP Allow lists from the capability profiles (capability profiles design, P1).

One profile per role and data class, infrastructure/base/agent-gateway/profiles/<role>.<dataClass>.yaml:

    role: reviewer
    dataClass: internal
    models: [agent-default, tier-light, tier-standard, tier-frontier]
    tools:
      flux-operator-mcp:
        - search_flux_docs

This script owns the `matchExpressions` items of each MCP authorization policy in
infrastructure/base/agent-gateway/mcp.yaml and nothing else in that file. A policy's class is the
listener its HTTPRoute attaches to; its list holds one expression per profile of that class (roles
in name order) and target (in the agent-mcp backend's order) the profile names, with the tools in
the profile's order: the N7 grammar gate AG6 enforces. A tool no expression names is hidden from
tools/list and answers `Unknown tool`.

P1 renders `tools` only. `models` is carried and checked, not rendered: until P2 compiles it into a
route-level authorization, it names every alias the LLM backends serve, since any role may ask for
any of them today. `egress`, `readOnly` and a tool's `when` are refused until the steps that render
them: a field nothing enforces must not read as a rule.

Usage: gen-capabilities.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed lists are the rendering (or --write wrote it), 1 drift or a bad profile.
"""
import difflib
import pathlib
import re
import sys
from typing import NamedTuple

import yaml

GATEWAY = pathlib.PurePosixPath("infrastructure/base/agent-gateway")
PROFILES = GATEWAY / "profiles"
MCP = GATEWAY / "mcp.yaml"
AUD_PREFIX = "agent-router"
KEYS = ("role", "dataClass", "models", "tools")
# Rendered from the agent-capability-profiles ConfigMap step on; refused until then.
CONFIGMAP_KEYS = ("egress", "readOnly")
FILE = re.compile(r"^(?P<role>[a-z]+)\.(?P<cls>[a-z]+)\.yaml$")
TOOL = re.compile(r"^[a-z0-9_]+$")
SEPARATOR = re.compile(r"^---\n", re.M)
LIST = re.compile(r"^(?P<indent> *)matchExpressions:\n(?:(?P=indent)  - .*\n)+", re.M)


class Profile(NamedTuple):
    path: str
    role: str
    data_class: str
    tools: dict


def expression(role, cls, target, tools):
    """One N7 alternative: one role's audience, one target, its tool names."""
    names = ", ".join(f'"{t}"' for t in tools)
    return f'"{AUD_PREFIX}.{role}.{cls}" in jwt.aud && mcp.tool.target == "{target}" && mcp.tool.name in [{names}]'


def served_aliases(root):
    """Every model alias an LLM backend beside mcp.yaml serves (AG12 pins them to AGENT_MODELS)."""
    aliases = set()
    for path in sorted((root / GATEWAY).glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if isinstance(doc, dict) and doc.get("kind") == "AgentgatewayBackend":
                ai = (((doc.get("spec") or {}).get("policies") or {}).get("ai") or {})
                aliases |= set(ai.get("modelAliases") or {})
    return aliases


def load_profile(root, path, targets, aliases, errors):
    rel = path.relative_to(root).as_posix()
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict):
        errors.append(f"{rel}: a profile is a mapping of {', '.join(KEYS)}")
        return None
    for key in sorted(set(doc) - set(KEYS)):
        errors.append(f"{rel}: {key} arrives with the agent-capability-profiles ConfigMap; a field nothing renders "
                      "must not read as a rule" if key in CONFIGMAP_KEYS
                      else f"{rel}: unknown key {key}; a profile holds {', '.join(KEYS)}")
    for key in KEYS:
        if key not in doc:
            errors.append(f"{rel}: missing {key}")
    m = FILE.match(path.name)
    if not m or (doc.get("role"), doc.get("dataClass")) != (m["role"], m["cls"]):
        errors.append(f"{rel}: a profile is named <role>.<dataClass>.yaml after its own role and dataClass")
    models = doc.get("models")
    if not isinstance(models, list) or len(set(map(str, models))) != len(models) or set(map(str, models)) != aliases:
        errors.append(f"{rel}: models must name each alias the LLM backends serve once, {sorted(aliases)}: it is "
                      "checked, not rendered, until P2, and today any role may ask for any of them")
    tools = doc.get("tools")
    if not isinstance(tools, dict) or not tools:
        errors.append(f"{rel}: tools maps each MCP target to its tool names")
        return None
    for target, names in tools.items():
        if target not in targets:
            errors.append(f"{rel}: {target} is not a target of the agent-mcp backend ({', '.join(targets)})")
        if not isinstance(names, list) or not names:
            errors.append(f"{rel}: {target} lists no tool; leave the target out instead")
            continue
        for n in names:
            if isinstance(n, dict):
                errors.append(f"{rel}: {target} {n.get('name')}: argument constraints (when) arrive with P3, "
                              "after spike S0")
            elif not isinstance(n, str) or not TOOL.match(n):
                errors.append(f"{rel}: {target} names {n!r}, which is not a tool name")
        twice = sorted({n for n in names if isinstance(n, str) and names.count(n) > 1})
        if twice:
            errors.append(f"{rel}: {target} lists {', '.join(twice)} twice")
    return Profile(rel, str(doc.get("role")), str(doc.get("dataClass")), tools)


def render(root):
    """(mcp.yaml as the profiles render it, None) or (None, the errors that prevent it)."""
    root = pathlib.Path(root)
    errors = []
    chunks = SEPARATOR.split((root / MCP).read_text())
    docs = [yaml.safe_load(c) or {} for c in chunks]
    backends = [d for d in docs if d.get("kind") == "AgentgatewayBackend" and (d.get("spec") or {}).get("mcp")]
    if len(backends) != 1:
        return None, [f"{MCP}: expected one MCP AgentgatewayBackend, found {len(backends)}"]
    targets = [t.get("name") for t in backends[0]["spec"]["mcp"].get("targets") or []]
    aliases = served_aliases(root)
    if not aliases:
        errors.append(f"{GATEWAY}: no LLM backend serves a model alias")
    files = sorted((root / PROFILES).glob("*.yaml"))
    if not files:
        errors.append(f"{PROFILES}: no profile")
    profiles = [p for p in (load_profile(root, f, targets, aliases, errors) for f in files) if p]
    routes = {d["metadata"]["name"]: {p.get("sectionName") for p in d["spec"].get("parentRefs") or []}
              for d in docs if d.get("kind") == "HTTPRoute"}
    served = set()
    for i, d in enumerate(docs):
        authz = (((d.get("spec") or {}).get("backend") or {}).get("mcp") or {}).get("authorization")
        if d.get("kind") != "AgentgatewayPolicy" or authz is None:
            continue
        name = d["metadata"]["name"]
        sections = set().union(*(routes.get(t.get("name"), set()) for t in d["spec"].get("targetRefs") or []
                                 if t.get("kind") == "HTTPRoute"))
        if len(sections) != 1:
            errors.append(f"{MCP}: {name} must target routes on one listener, got {sorted(map(str, sections))}")
            continue
        cls = sections.pop()
        served.add(cls)
        exprs = [expression(p.role, cls, t, p.tools[t])
                 for p in sorted((p for p in profiles if p.data_class == cls), key=lambda p: p.role)
                 for t in targets if t in p.tools]
        found = list(LIST.finditer(chunks[i]))
        if not exprs:
            errors.append(f"{MCP}: no profile of class {cls} for {name}")
        elif len(found) != 1:
            errors.append(f"{MCP}: {name} must hold one block-style matchExpressions list, found {len(found)}")
        else:
            m, indent = found[0], found[0]["indent"]
            items = "".join(f"{indent}  - '{e}'\n" for e in exprs)
            spliced = f"{chunks[i][:m.start()]}{indent}matchExpressions:\n{items}{chunks[i][m.end():]}"
            # The splice replaces the run of plain items only: whatever else sits in the list (a comment, a
            # multi-line item, a last item with no newline) would survive it, so the list must parse back to
            # exactly the rendering.
            # Skipped once a profile is refused: its names may not be renderable at all.
            held = None if errors else ((((yaml.safe_load(spliced) or {}).get("spec") or {}).get("backend") or {}
                                         ).get("mcp") or {}).get("authorization", {}).get("policy", {}
                                                                                           ).get("matchExpressions")
            if not errors and held != exprs:
                errors.append(f"{MCP}: policy {name}: matchExpressions holds items the generator does not own "
                              "(a comment or a multi-line item inside the list?): move them above matchExpressions:")
            chunks[i] = spliced
    for p in profiles:
        if p.data_class not in served:
            errors.append(f"{p.path}: no MCP Allow policy in {MCP} serves the {p.data_class} listener")
    return (None, errors) if errors else ("---\n".join(chunks), [])


def main(argv):
    args = argv[1:]
    write = "--write" in args
    paths = [a for a in args if a != "--write"]
    root = pathlib.Path(paths[0]) if paths else pathlib.Path(__file__).resolve().parents[2]
    rendered, errors = render(root)
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if errors:
        return 1
    current = (root / MCP).read_text()
    if rendered == current:
        print(f"gen-capabilities: {MCP} is its profiles' rendering")
        return 0
    if write:
        (root / MCP).write_text(rendered)
        print(f"gen-capabilities: wrote {MCP}")
        return 0
    sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), rendered.splitlines(True),
                                               f"{MCP} (committed)", f"{MCP} (rendered from {PROFILES})"))
    print(f"FAIL {MCP} differs from its profiles' rendering: edit the profiles, run "
          "python3 scripts/ci/gen-capabilities.py --write and commit both", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

Two details matter here. The documents are split on `^---\n` so that each chunk keeps its trailing
newline. A split on `\n---\n` cuts that newline off the public policy's last item, and the list regex
then leaves that item behind as a duplicate; the prototype measured exactly this. Also, every
expression is single-quoted YAML, and `TOOL`, `FILE` and the backend's target names exclude `'`, so
no expression ever needs escaping.

- [ ] **Step 4: Run the unit tests**

```bash
chmod +x scripts/ci/gen-capabilities.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py; echo "exit=$?"
```

Expected: 27 `ok` lines (4 parity, 5 drift, 3 foreign list content, 15 refusals), `all passed` and `exit=0`.

- [ ] **Step 5: Prove parity on the real tree**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-capabilities.py; echo "exit=$?"
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-capabilities.py --write
git diff --exit-code infrastructure/base/agent-gateway/mcp.yaml && echo PARITY
```

Expected: `gen-capabilities: infrastructure/base/agent-gateway/mcp.yaml is its profiles' rendering`,
then `exit=0`. `--write` prints the same line, writes nothing, and the run ends with `PARITY`. Any
diff here means a profile does not match today's order or contents: fix the profile, never
`mcp.yaml`.

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/gen-capabilities.py scripts/ci/tests/test-gen-capabilities.py
git commit -m "feat(ci): gen-capabilities renders the MCP Allow lists from the capability profiles"
```

---

### Task 3: The drift gate, the generated-list markers and the docs

**Files:**
- Create: `scripts/ci/tests/test-agent-capabilities.sh`
- Modify: `infrastructure/base/agent-gateway/mcp.yaml`: header lines 3–4, and one comment line
  above each `matchExpressions:`
- Modify: `docs/runbooks/agent-factory/06-mcp.md` (line 95)
- Modify: `website/content/docs/platform/ai-platform/gateways.md` (the "MCP federation" section)
- Modify: `docs/superpowers/specs/2026-10-21-capability-profiles-design.md`

**Interfaces:**
- Consumes: Task 2's CLI and its exit codes.
- Produces: the suite name `test-agent-capabilities`, which Task 4's PR body cites as the drift gate.

- [ ] **Step 1: Write the drift suite**

`scripts/ci/tests/test-agent-capabilities.sh`:

```bash
#!/usr/bin/env bash
# requires: python3
#
# Capability profiles design, gate 5: the MCP Allow lists committed in
# infrastructure/base/agent-gateway/mcp.yaml are exactly what scripts/ci/gen-capabilities.py
# renders from infrastructure/base/agent-gateway/profiles/, as AG8 holds the budgets' cost string
# to meter.prices. A list edited by hand, or a profile changed without --write, fails here with
# the diff. The real tree.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
python3 "$ROOT/scripts/ci/gen-capabilities.py" "$ROOT"
```

```bash
chmod +x scripts/ci/tests/test-agent-capabilities.sh
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities.sh; echo "exit=$?"
shellcheck scripts/ci/tests/test-agent-capabilities.sh
```

Expected: `gen-capabilities: … is its profiles' rendering`, then `exit=0`. shellcheck prints nothing.

- [ ] **Step 2: Prove that a hand edit fails it (gate 5)**

```bash
sed -i '0,/, "get_kubernetes_logs"\]/s//]/' infrastructure/base/agent-gateway/mcp.yaml
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities.sh; echo "exit=$?"
git checkout -- infrastructure/base/agent-gateway/mcp.yaml
```

Expected: a unified diff with one `-` line and one `+` line, both the reviewer's internal
`flux-operator-mcp` expression, the `+` line ending in `"get_kubernetes_logs"]'`. Then
`FAIL infrastructure/base/agent-gateway/mcp.yaml differs from its profiles' rendering: …`, then
`exit=1`. Re-running the suite after the checkout prints `exit=0`.

- [ ] **Step 3: Mark the lists as generated in `mcp.yaml`**

Replace:

```yaml
# listener, one Allow list per route. test-agent-mcp-scope.sh holds both files
# to the same per-role sets.
```

with:

```yaml
# listener, one Allow list per route. The lists are generated from one profile per
# role and data class (profiles/, capability profiles design): edit a profile, then
# run scripts/ci/gen-capabilities.py --write. test-agent-capabilities fails on a
# list edited by hand; test-agent-mcp-scope holds the profiles to the per-role sets.
```

In `agentgateway-mcp-public`, replace:

```yaml
          matchExpressions:
            - '"agent-router.implementer.public" in jwt.aud
```

with:

```yaml
          # Generated from profiles/*.public.yaml by scripts/ci/gen-capabilities.py.
          matchExpressions:
            - '"agent-router.implementer.public" in jwt.aud
```

In `agentgateway-mcp-internal`, replace:

```yaml
          matchExpressions:
            - '"agent-router.implementer.internal" in jwt.aud
```

with:

```yaml
          # Generated from profiles/*.internal.yaml by scripts/ci/gen-capabilities.py.
          matchExpressions:
            - '"agent-router.implementer.internal" in jwt.aud
```

In each case, match only the start of the first item's line; the rest of that line stays as it is.

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities.sh; echo "exit=$?"
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | tail -1
```

Expected: `exit=0` and `all passed`. The comments sit outside the lists, which the generator does not
own.

- [ ] **Step 4: The runbook, the site and the spec**

In `docs/runbooks/agent-factory/06-mcp.md`, replace:

```markdown
Other roles, from `infrastructure/base/agent-gateway/mcp.yaml` (its Allow lists): reviewer, tester and triager also
```

with:

```markdown
Other roles, from their profiles in `infrastructure/base/agent-gateway/profiles/` (rendered into `mcp.yaml`'s Allow lists): reviewer, tester and triager also
```

In `website/content/docs/platform/ai-platform/gateways.md`, after the paragraph that ends
`` `x-room-mcp-key`. `` and before the `| Role | `public` | `internal` adds |` table, insert:

```markdown
The lists are generated. One profile per role and data class in
`infrastructure/base/agent-gateway/profiles/` names its tools, `scripts/ci/gen-capabilities.py --write`
renders them into `mcp.yaml`, and `task check` fails when the two differ: adding a tool is a line in a
profile.

```

In `docs/superpowers/specs/2026-10-21-capability-profiles-design.md`, replace:

```markdown
**Date:** 2026-10-21 · **Status:** draft; no owner decision pending (O3 and O4 taken 2026-10-21) · **Part of:** the
```

with:

```markdown
**Date:** 2026-10-21 · **Status:** draft; no owner decision pending (O3 and O4 taken 2026-10-21) · **Amended
2026-10-22**: the migration's first step, the profiles and a generator at parity, is built
([plan](../plans/2026-10-22-capability-profiles-p1-plan.md)) · **Part of:** the
```

At the end of the file, after the paragraph that ends `ConfigMap read).`, append:

```markdown

Ruled in P1 ([plan](../plans/2026-10-22-capability-profiles-p1-plan.md#this-plans-rulings)):

- **The generator:** Python, unit-tested by `test-gen-capabilities`. It owns only the
  `matchExpressions` items of `mcp.yaml`'s MCP policies. Roles render in name order, targets in the
  backend's order and tools in the profile's order, which is how the hand-written lists were
  ordered, so the first rendering changed no byte.
- **The drift gate:** the suite `test-agent-capabilities`. The profiles reach the bundle only with
  the ConfigMap, so the suite reads the tree and regenerates the lists, as AG8 regenerates its cost
  string.
- **The fields:** `models` is carried and checked against the backends' aliases until P2 renders it.
  `egress`, `readOnly` and `when` are refused until their steps.
```

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/validate-links.sh
```

Expected: no broken link. The two `../plans/…` links resolve to this plan.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/tests/test-agent-capabilities.sh infrastructure/base/agent-gateway/mcp.yaml \
  docs/runbooks/agent-factory/06-mcp.md website/content/docs/platform/ai-platform/gateways.md \
  docs/superpowers/specs/2026-10-21-capability-profiles-design.md
git commit -m "feat(ci): fail on capability drift, and mark the MCP Allow lists as generated"
```

---

### Task 4: Verify, push, open the pull request

- [ ] **Step 1: The whole check**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|mcp-scope|capabilities|passed,|exit=" "$SCRATCH/check-$(basename "$PWD").log"
```

Expected:
- `assert-agent-gateway: 14 checks, 0 violations (clusters: aws-0, gcp-0)`
- `PASS` for `test-agent-mcp-scope`, `test-gen-capabilities` and `test-agent-capabilities`
- `23 passed, 1 skipped, 0 failed`. The skip is `test-agent-traces-filter` when no Docker daemon
  runs; the baseline on 2026-10-22 was 21 passed and 1 skipped, and this plan adds two suites.
- `exit=0`

- [ ] **Step 2: Rebase and push**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/capability-profiles-p1
```

- [ ] **Step 3: Open the pull request**

Title: `feat(agent-gateway): capability profiles P1, the profiles and a generator at parity`.

The body is in English and covers:
- **The outcome:** eight profiles, `mcp.yaml`'s Allow lists generated byte for byte, and
  `tools/list` unchanged for every role.
- **The rulings:** R1 to R6, and which fields are carried but not yet rendered. `models` is checked
  against the backends' aliases; `egress`, `readOnly` and `when` are refused.
- **The three suites,** with design gates 4 and 5.
- **What waits:** P2 to P4 and the ConfigMap.
- **The `task check` summary.**
- **A test plan:** a hand edit fails `test-agent-capabilities`, and `--write` after a profile edit
  moves one line.

No attribution line.
