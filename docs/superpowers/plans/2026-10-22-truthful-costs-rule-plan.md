# Truthful costs, PR 1: the charge rule generated from meter.prices — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every cost the dashboards and fleet alerts read comes from `meter.prices`, cache rates
included: a generated `llm_gateway:charge_usd_per_mtoken` replaces the hand-kept list prices, its
two readers move to it, and a new alert fires when a gateway stops counting cache tokens inside
`input`, the precondition the charge rests on.

**Architecture:** `scripts/ci/gen-prices.py` reads `meter.prices` from the factory's values and
rewrites only the `llm-gateway-prices` group of `vmrule-llm-gateway.yaml`: four
`llm_gateway:charge_usd_per_mtoken` rules per model, zeros included. The charge is what one counted
token adds, so a cache read is `cacheRead − input`, since `input` already counts it. Each reader
then prices with one join over the four token types. Four suites hold the result:

- `test-gen-prices` unit-tests the generator on copies of the tree (offline proof 2).
- `test-agent-prices` fails when the committed group differs from the rendering (offline proof 1).
  AG8 holds the budget CEL to the same table the same way.
- `test-agent-cost-rules` runs promtool on synthetic series through the committed rules, the
  dashboard's real query included (offline proof 3).
- `test-agent-gateway-cache-wire`, from [#95](https://github.com/Smana/ai-native-ref/pull/95),
  gains a streamed reply (offline proof 4).

**Tech Stack:** Python 3 with PyYAML and `decimal`, Bash suites run by `scripts/ci/run-tests.sh`
inside `.composite/`, promtool 3.15.0 (`promtool test rules`), VictoriaMetrics VMRules, a Grafana
dashboard JSON, agentgateway 1.6.

**Spec:** [truthful costs](../specs/2026-10-22-truthful-costs-design.md): decisions TC1–TC4, the
PR 1 row of "Pull requests, in order", and offline proofs 1–5.

**Out of PR 1** (PRs 2–4): the USD ledger, settlement, admission and the config keys (agent-platform).
The USD gauges, the factory alerts and dashboard on them, AG8's fleet floor from `factoryDailyUSD`.
`source` and `checkedAt` on the rows. Runbook 04's budget prose and `routing.md`'s budget layers.
The nightly drift check. The raw-token alerts and the sizes of B1, B2 and B6 stay as they are.

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **The generator owns the whole group and splices it in place.** It owns the lines from `- name: llm-gateway-prices` to the next line indented no deeper: the name, `interval: 5m`, the 24 rules and one comment per model naming its row. The comment above the group and the `llm-gateway-budgets` group stay hand-written. The spliced file must parse back to exactly the rendering, every other group unchanged, through a loader that refuses a key written twice | The spec left it open. P1 owns list items inside a hand-written policy; this group is pure data, so owning all of it makes any hand edit inside it drift. The duplicate-key loader closes the one way a splice could pass parse-back: a blank line inside the group leaves a second `rules:` that PyYAML would let win |
| R2 | **Numbers.** Each price is read as `Decimal(str(value))`, so `0.26 − 1.40` is `-1.14` and not `-1.1399999999999999`. Charges are written in plain notation with at least two places: `-1.14`, `-0.295`, `0.125`, `0.00` | The spec left it open. This prints exactly the spec's table |
| R3 | **Order.** Models render in `meter.prices` order. Each model's types render as `input`, `output`, `cached_input`, `cache_creation_input`, the spec table's column order | A new row then lands where its author put it, and moves no other line |
| R4 | **Rows.** `input`, `cacheRead` and `output` are required and `cacheWrite` is optional; each must be a positive, finite number. TC1's `source` and `checkedAt` are already accepted and ignored. Any other key is refused, as the factory's decoder refuses it (`DisallowUnknownFields`). A model name must match `^[a-z0-9][a-z0-9.-]*$` | PR 3 adds `source` and `checkedAt` to every row and should not need a generator change. A typo such as `cacheWirte` would otherwise render a write charge of 0. The name pattern keeps quoting trivial, and keeps out `${`: the `llm-gateway` Kustomization has no postBuild substitution |
| R5 | **The suites' names:** `test-gen-prices`, `test-agent-prices`, `test-agent-cost-rules` | Left to the builder. They follow the `test-gen-capabilities` and `test-agent-capabilities` pair, and #95's `test-agent-cache-alerts` |
| R6 | **`AgentMeterInputExcludesCache` compares with an hour ago, absence read as 0:** `sum by (model) (clamp_min(X - (X offset 1h or X * 0), 0)) > 0`, where the spec wrote `sum by (model) (increase(X[1h])) > 0` | The counter is born at its first increment (an OpenTelemetry counter), and promtool's `increase()` reads a series born at 1 as 0. Measured: the spec's form fails the born-at-1 case, so offline proof 3 could not pass on the real shape. VictoriaMetrics' `increase()` guesses a start of 0 for small first values, but nothing offline proves that. This is the repository's own pattern for the same problem (`agent_router:budget_*` in `vmrule.yaml`). It keeps the hour and resolves an hour after the last increment |
| R7 | **The alert's home and links:** after `AgentModelUnpriced` in `vmrule-agent-factory.yaml`, severity `warning`, `dashboard` `agent-factory`. `runbook_url` is runbook 04's Part E (#95), which gains its row | The spec names the file. Part E is the cache-read share's runbook, and #95's own comment says the share rests on the same counting |
| R8 | **promtool reads what ships:** the panel's query comes from the dashboard JSON, with `$${run}` set to `wire` and `$__range` to `1h`. The alert's expression is taken without its `> 13.6` and recorded as `test:anthropic_fleet:usd24h`, so the dollars are asserted and not only the firing. The prices group keeps its `interval: 5m` | A copied query could drift from the panel. Measured: the 5m group interval passes as is |
| R9 | **The streamed reply in the wire test** is the marked request plus `stream: true`, sent after the first scrape. Its usage is asserted as the delta between two scrapes: `input` +1050, reads +900, writes +50, output +10. The second scrape retries for up to 5 s, since the gateway records a stream's usage as it ends. The existing assertions keep their meaning: `n` counts the replies before the stream | The spec asks for "a streamed reply"; a delta proves that reply alone. The earlier replies' totals stay as #95 wrote them |
| R10 | **One commit switches the series** (Task 2): the generated group, the removal of `llm_gateway:price_usd_per_mtoken` and the `glm-5.2` rows, and both readers | The spec puts them in one PR; one commit leaves no reader without its series at any commit |
| R11 | **Docs:** `routing.md`'s "What a call costs" section (one price table, the charge series, the counting bullet corrected to the measurement, the closed known gap). `cohort-row.py`'s comment, which cites the old rule's prices, becomes one line. The spec gets a status line and a "Ruled in PR 1" list, as capability profiles P1 did | The budget layers are PR 3's |

**Measured 2026-10-22** on a prototype in `$SCRATCH/tcost/` (the code below is that prototype's):

- **The rendering:** on the real `meter.prices`, the generator writes 24 rules at exactly the spec's
  charges, and `promtool check rules --lint-fatal` passes on the file (25 rules). On today's file
  the check fails with the diff.
- **Unit tests:** `test-gen-prices` prints 26 `ok` lines, both against today's group and against
  the rendered one.
- **promtool:** on the same synthetic series, today's expressions read $0.0044 for the measured reply,
  $20 for the $5 day (and fire) and $56 for the $14 day. The new ones read $0.00103, $5 (silent)
  and $14 (fires). The spec's `increase()` form of the new alert stays silent on a series born at 1;
  R6's form fires.
- **Wire test:** the agentgateway v1.6.0 binary (`ea56086`, the pinned image's version) stood in for
  the container through a `docker` shim. #95's test passes, the extended test passes, and with the
  fake's streamed `input_tokens` at 200 it fails with `got {'input': 1150.0, …}`.
- **`task check`** on a branch holding #95 and every change below: `25 passed, 2 skipped, 0 failed`
  (both skips are Docker suites). `assert-agent-gateway: 14 checks, 0 violations`,
  `114 PromQL expression(s) in 18 group(s) parse`, links, doc paths and sources pass, `exit=0`.

## Global Constraints

- **Branch:** `feat/truthful-costs-rule`, in its own worktree, carrying this plan on top of
  `origin/main`. The spec landed on main with #98 (rebased 2026-10-22: the branch's own spec commit
  was dropped). In a new worktree, run `mise trust mise.toml` once.
- **#95 first.** Tasks 3 and 4 extend #95's content: the wire test
  `scripts/ci/tests/test-agent-gateway-cache-wire.sh` and runbook 04's Part E. #95 merged on
  2026-10-22 and the branch is rebased onto it, so Task 3's rebase step is already done. Rebase onto
  a freshly fetched `origin/main` before every push.
- **`$SCRATCH`** is a scratch directory outside the repository. It holds two helpers:
  - `check.sh <worktree>` runs `task check` with a `python3` that has PyYAML ahead of mise's. It
    logs to `$SCRATCH/check-<worktree directory name>.log` and ends the log with `exit=N`.
  - `run-suite.sh <command…>` runs one command with that `python3`.
  The `python3` on `PATH` lacks PyYAML, so every Python and suite command below goes through one of
  the two helpers.
- **`task check` is the evidence** (AGENTS.md). Never claim done without its log.
- **Docker suites SKIP locally** when no daemon runs. CI sets `CI=true`, where the wire test fails
  without Docker instead of skipping, so CI is where it must pass.
- **`__pycache__/` is ignored since #97.** Still run `export PYTHONDONTWRITEBYTECODE=1` in the shell
  first, and `git add` named paths only, never `-A`.
- **The suite contract:** line 1 is the shebang and line 2 is `# requires: <tools>`. Exit 77 is a
  SKIP. Suites read the real tree. `run-tests.sh` runs them inside `.composite/` and finds them with
  `git ls-files`, so a new suite counts only once it is committed.
- **Host scripts are never vendored.** The generator is this repository's own CI script, like
  `gen-capabilities.py`. It imports nothing from the host.
- **Substitution:** `vmrule-llm-gateway.yaml` gains no `${…}`: its Kustomization
  (`clusters/*-ai-gateway/infrastructure-llm-gateway.yaml`) has no postBuild. The dashboard JSON
  keeps `$${…}` for Grafana variables. The new alert's `dashboard` annotation reuses
  `${private_domain_name}`, as every alert in its file already does.
- **No new workload.** The constitution's workload rules gain nothing new to apply to.
- **Commits** are conventional, in English, with **no trailers**.
- **Verbatim from the spec:**
  - TC2: "`input` → input; `output` → output; `cached_input` → cacheRead − input;
    `cache_creation_input` → cacheWrite − input, which is 0 without a cacheWrite".
  - TC3: "`scripts/ci/gen-prices.py` checks by default and writes with `--write`. It renders the
    `llm-gateway-prices` group of `vmrule-llm-gateway.yaml` from `meter.prices`: four rows per model,
    zeros included, so no token type of a priced model drops out of the join."
  - TC3: "`llm_gateway:price_usd_per_mtoken` and the `glm-5.2` rows go in the same PR as their
    readers move".
  - TC4: "PR 1 adds a streamed reply to it. Live, a new alert `AgentMeterInputExcludesCache` reads
    the meter's existing counter".
  - Readers: `AnthropicFleetNearCap` becomes "the four types × the charge, > 13.6", and the
    `agent-run` Cost panel "the same".
  - Offline proofs 1–5 (the spec's Gate section): proof 1 in Tasks 1 and 2, proof 2 in Task 1,
    proof 3 in Tasks 2 and 3, proof 4 in Tasks 4 and 6, proof 5 in Task 6.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `scripts/ci/gen-prices.py` | create | Renders the `llm-gateway-prices` group from `meter.prices`: checks by default, `--write` writes |
| `scripts/ci/tests/test-gen-prices.py` | create | The generator's unit tests, on temporary copies of the two files (offline proof 2) |
| `scripts/ci/tests/test-agent-prices.sh` | create | The drift check on the real tree (offline proof 1) |
| `scripts/ci/tests/test-agent-cost-rules.sh` | create | promtool on the readers and the new alert (offline proof 3) |
| `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml` | modify: the group, generated, and its comment | `llm_gateway:charge_usd_per_mtoken`, 24 rules |
| `observability/base/agent-platform/vmrule.yaml` | modify: `AnthropicFleetNearCap` | The four types × the charge |
| `observability/base/agent-platform/grafana-dashboard-agent-run.yaml` | modify: the Cost panel | The same |
| `observability/base/agent-platform/vmrule-agent-factory.yaml` | modify: append one alert | `AgentMeterInputExcludesCache` |
| `scripts/ci/tests/test-agent-gateway-cache-wire.sh` | modify (#95's file) | A streamed reply, counted as the others (offline proof 4) |
| `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md` | modify (#95's Part E) | The alert's row; the offline proofs |
| `website/content/docs/platform/ai-platform/routing.md` | modify: "What a call costs" and one gap row | One price table, the charge series, the counting |
| `scripts/ops/github/cohort-row.py` | modify: one comment | Cites `meter.prices`, not the old rule |
| `docs/superpowers/specs/2026-10-22-truthful-costs-design.md` | modify: status line and "Left to the builder" | Records PR 1 and its rulings |

---

### Task 1: The generator and its unit tests

**Files:**
- Create: `scripts/ci/gen-prices.py`
- Create: `scripts/ci/tests/test-gen-prices.py`

**Interfaces:**
- Consumes: `tooling/base/agent-factory/helm-values-configmap.yaml` (ConfigMap
  `agent-factory-helm-values`, key `values.yaml`, path `config.meter.prices`) and
  `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml` (its `- name: llm-gateway-prices` group
  and the `- name: llm-gateway-budgets` group after it).
- Produces (Task 2 and PR 3 rely on these):
  - The CLI: `python3 scripts/ci/gen-prices.py [--write] [ROOT]`. Exit 0 means in sync or written;
    exit 1 means drift or a bad row, every problem printed as `FAIL …`. In sync, it prints
    `gen-prices: infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml group llm-gateway-prices is meter.prices' rendering`.
  - Module constants `VALUES`, `RULES` (`PurePosixPath`, relative to ROOT), `GROUP`, `RECORD`
    (`"llm_gateway:charge_usd_per_mtoken"`), `TYPES`.
  - `usd(Decimal) -> str`, `charges(row: dict) -> dict[str, Decimal]`,
    `groups_of(text) -> list | None`, `render(root) -> tuple[str | None, list[str]]`,
    `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

`scripts/ci/tests/test-gen-prices.py`:

```python
#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/gen-prices.py, which renders the llm-gateway-prices group from meter.prices.

Each case copies the real factory values and price rule into a temporary root, changes one thing and
runs the generator there: the rendering holds the design's charges, it rebuilds the group byte for
byte, a hand edit or a price changed without --write fails with the diff, and each malformed row is
refused, by name, without a write.

Run: python3 scripts/ci/tests/test-gen-prices.py
"""
import contextlib
import importlib.util
import io
import pathlib
import shutil
import sys
import tempfile
from decimal import Decimal

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen_prices", ROOT / "scripts/ci/gen-prices.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FAILURES = []
# The truthful costs design, "The charge series": input, output, cached_input, cache_creation_input.
DESIGN = {
    "glm-5.3": ("1.40", "4.40", "-1.14", "0.00"),
    "glm-5.3-flashx": ("0.37", "1.25", "-0.295", "0.00"),
    "glm-5.3-flash": ("0.15", "0.50", "-0.12", "0.00"),
    "claude-opus-5-5": ("4.00", "20.00", "-3.80", "1.00"),
    "claude-sonnet-5-5": ("2.00", "10.00", "-1.90", "0.50"),
    "claude-haiku-5-5": ("0.50", "2.50", "-0.45", "0.125"),
}
HAIKU = "claude-haiku-5-5: {input: 0.50, cacheRead: 0.05, cacheWrite: 0.625, output: 2.50}"
FLASH = "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: 0.50}"


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def run(root, *flags):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = gen.main(["gen-prices.py", *flags, str(root)])
    return code, out.getvalue()


@contextlib.contextmanager
def tree():
    """A temporary root holding copies of the factory values and the price rule, the group rendered."""
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for rel in (gen.VALUES, gen.RULES):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, root / rel)
        run(root, "--write")
        yield root


def rules(root):
    return root / gen.RULES


def replace(root, rel, old, new):
    path = root / rel
    text = path.read_text()
    assert text.count(old) == 1, f"{rel}: {old!r} found {text.count(old)} times"
    path.write_text(text.replace(old, new))


def charges_in(root):
    """{model: (input, output, cached_input, cache_creation_input)} as the file's group holds them."""
    group = next(g for g in gen.groups_of(rules(root).read_text()) if g["name"] == gen.GROUP)
    got = {}
    for r in group["rules"]:
        assert r["record"] == gen.RECORD and r["expr"].startswith("vector(")
        got.setdefault(r["labels"]["gen_ai_request_model"], {})[r["labels"]["gen_ai_token_type"]] = r["expr"][7:-1]
    return {m: tuple(t.get(k) for k in gen.TYPES) for m, t in got.items()}, len(group["rules"])


def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves the rule file alone."""
    with tree() as t:
        change(t)
        before = rules(t).read_text()
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and rules(t).read_text() == before, out)


def row(old, new):
    """A tree change that rewrites one meter.prices row."""
    return lambda t: replace(t, gen.VALUES, old, new)


print("the rendering (design offline proof 2)")
with tree() as t:
    got, n = charges_in(t)
    check("four rows per model, in meter.prices' order, at the design's charges",
          got == DESIGN and list(got) == list(DESIGN) and n == 24, str(got))
    text = rules(t).read_text()
    check("no glm-5.2 and no llm_gateway:price_usd_per_mtoken",
          "glm-5.2" not in text and "price_usd_per_mtoken" not in text)
check("exact decimals: 0.26 - 1.40 is -1.14, not float noise",
      gen.usd(Decimal("0.26") - Decimal("1.40")) == "-1.14" and gen.usd(Decimal("20")) == "20.00"
      and gen.usd(Decimal("0.625") - Decimal("0.50")) == "0.125" and gen.usd(Decimal("1.4") - Decimal("1.40")) == "0.00")
check("a write the provider does not bill is charged as input",
      gen.charges({"input": 1.4, "cacheRead": 0.26, "output": 4.4})["cache_creation_input"] == 0)

print("parity")
with tree() as t:
    code, out = run(t)
    check("the rendered tree is in sync", code == 0 and "is meter.prices' rendering" in out, out)
    once = rules(t).read_bytes()
    code, out = run(t, "--write")
    check("--write on a tree in sync writes nothing", code == 0 and rules(t).read_bytes() == once, out)
with tree() as t:
    want = rules(t).read_bytes()
    text = rules(t).read_text()
    start = text.index(f"    - name: {gen.GROUP}\n")
    end = text.index("    - name: llm-gateway-budgets\n")
    rules(t).write_text(text[:start] + f"    - name: {gen.GROUP}\n      rules: []\n" + text[end:])
    code, out = run(t, "--write")
    check("--write rebuilds the group from nothing, byte for byte", code == 0 and rules(t).read_bytes() == want, out)
    budgets = [g for g in gen.groups_of(rules(t).read_text()) if g["name"] == "llm-gateway-budgets"]
    check("the hand-written group beside it is untouched", len(budgets) == 1 and
          budgets == [g for g in gen.groups_of((ROOT / gen.RULES).read_text()) if g["name"] == "llm-gateway-budgets"])

print("drift (design offline proof 1)")
with tree() as t:
    replace(t, gen.RULES, "expr: vector(-3.80)", "expr: vector(-3.70)")
    code, out = run(t)
    check("a hand edit to a row fails, with the diff and the fix",
          code == 1 and "-          expr: vector(-3.70)" in out and "+          expr: vector(-3.80)" in out
          and "--write" in out, out)
with tree() as t:
    before = rules(t).read_text().splitlines()
    replace(t, gen.VALUES, HAIKU, HAIKU + "\n          claude-mythos-5: {input: 25.00, cacheRead: 2.50, cacheWrite: 31.25, output: 125.00}")
    code, out = run(t)
    check("a row added to meter.prices without --write fails", code == 1 and "differs" in out, out)
    code, out = run(t, "--write")
    after = rules(t).read_text().splitlines()
    got, n = charges_in(t)
    i = before.index("    - name: llm-gateway-budgets")
    check("--write inserts its comment and four rules at the group's end, and nothing else",
          code == 0 and n == 28 and after[:i] == before[:i] and after[i + 21:] == before[i:]
          and after[i] == "        # claude-mythos-5: input 25.00, cacheRead 2.50, cacheWrite 31.25, output 125.00",
          "\n".join(after[i - 1:i + 2]))
    check("its charges", got["claude-mythos-5"] == ("25.00", "125.00", "-22.50", "6.25"), str(got["claude-mythos-5"]))
    check("the result is in sync", run(t)[0] == 0)
with tree() as t:
    replace(t, gen.VALUES, FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: 0.60}")
    code, out = run(t, "--write")
    check("a price change moves its own rule only",
          code == 0 and charges_in(t)[0]["glm-5.3-flash"] == ("0.15", "0.60", "-0.12", "0.00"), out)

print("a group the generator does not fully own")
STRAY = "holds lines the generator does not own"
with tree() as t:
    replace(t, gen.RULES, "      interval: 5m\n", "      interval: 5m\n\n")
    code, out = run(t, "--write")
    check("a blank line inside the group is refused, untouched", code == 1 and STRAY in out
          and "\n\n      rules:" in rules(t).read_text(), out)

print("refused rows and files")
for name, change, needle in [
    ("a row without cacheRead", row(FLASH, "glm-5.3-flash: {input: 0.15, output: 0.50}"),
     "meter.prices.glm-5.3-flash: missing cacheRead"),
    ("a price that is not a number", row(FLASH, "glm-5.3-flash: {input: '0.15', cacheRead: 0.03, output: 0.50}"),
     "input must be a positive number of USD per million tokens, got '0.15'"),
    ("a zero price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0, output: 0.50}"),
     "cacheRead must be a positive number"),
    ("a boolean price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: true}"),
     "output must be a positive number"),
    ("not a finite price", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: .nan, output: 0.50}"),
     "cacheRead must be a positive number"),
    ("an unknown key", row(FLASH, "glm-5.3-flash: {input: 0.15, cacheRead: 0.03, cacheWirte: 0.2, output: 0.50}"),
     "unknown key cacheWirte"),
    ("not a model name", row(FLASH, "'glm 5.3 flash': {input: 0.15, cacheRead: 0.03, output: 0.50}"),
     "meter.prices key 'glm 5.3 flash' is not a served model name"),
    ("no row at all", row("        prices:\n", "        prices: {}\n        unused:\n"), "config.meter.prices holds no row"),
    ("no group in the rule file", lambda t: replace(t, gen.RULES, f"- name: {gen.GROUP}\n", "- name: other\n"),
     f"expected one group `- name: {gen.GROUP}`, found 0"),
    ("the group twice", lambda t: replace(t, gen.RULES, "    - name: llm-gateway-budgets\n",
                                          f"    - name: {gen.GROUP}\n      rules: []\n    - name: llm-gateway-budgets\n"),
     f"expected one group `- name: {gen.GROUP}`, found 2"),
]:
    refused(name, change, needle)
with tree() as t:
    replace(t, gen.VALUES, FLASH, 'glm-5.3-flash: {input: 0.15, cacheRead: 0.03, output: 0.50, source: "https://docs.z.ai/guides/overview/pricing", checkedAt: "2026-10-16"}')
    code, out = run(t)
    check("TC1's source and checkedAt are accepted and not rendered", code == 0, out)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
chmod +x scripts/ci/tests/test-gen-prices.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-prices.py; echo "exit=$?"
```

Expected: `FileNotFoundError: … scripts/ci/gen-prices.py`, then `exit=1`.

- [ ] **Step 3: Write the generator**

`scripts/ci/gen-prices.py`:

```python
#!/usr/bin/env python3
"""Render the llm-gateway-prices group of vmrule-llm-gateway.yaml from meter.prices (truthful costs, TC2 and TC3).

meter.prices, in the factory's values (tooling/base/agent-factory/helm-values-configmap.yaml), is the
one place a price is edited: USD per million tokens per served model, `input`, `cacheRead`, `output`,
and `cacheWrite` where the provider bills one. This script renders each row as four series of
llm_gateway:charge_usd_per_mtoken{gen_ai_request_model, gen_ai_token_type}, what one counted token of
that type adds to the cost. Every gateway counts cache tokens inside `input`, so:

    input                 input
    output                output
    cached_input          cacheRead - input
    cache_creation_input  cacheWrite - input, 0 without a cacheWrite (an unbilled write costs as input)

and a cost is one join over the four types:
sum(tokens * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:charge_usd_per_mtoken) / 1e6.
Zeros are rendered too, so no token type of a priced model drops out of the join.

The script owns the group, from its `- name: llm-gateway-prices` line to the next line indented no
deeper, and nothing else in the file. Charges are exact decimals: 0.26 - 1.40 is written -1.14.

Usage: gen-prices.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed group is the rendering (or --write wrote it), 1 drift or a bad row.
"""
import difflib
import math
import pathlib
import re
import sys
from decimal import Decimal

import yaml

VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
VALUES_NAME = "agent-factory-helm-values"
RULES = pathlib.PurePosixPath("infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml")
GROUP = "llm-gateway-prices"
INTERVAL = "5m"
RECORD = "llm_gateway:charge_usd_per_mtoken"
TYPES = ("input", "output", "cached_input", "cache_creation_input")
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
REQUIRED = ("input", "cacheRead", "output")
# Truthful costs TC1: provenance a row may carry. The meter ignores it, and so does this script.
METADATA = ("source", "checkedAt")
MODEL = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
BLOCK = re.compile(rf"^(?P<indent> *)- name: {re.escape(GROUP)}\n(?:(?P=indent)  .*\n)*", re.M)


class Strict(yaml.SafeLoader):
    """SafeLoader that refuses a key written twice in one mapping, where PyYAML would let the last win."""


def _mapping(loader, node):
    keys = [loader.construct_object(k, deep=True) for k, _ in node.value]
    if len(set(map(str, keys))) != len(keys):
        raise yaml.constructor.ConstructorError(None, None, "a key written twice", node.start_mark)
    return loader.construct_mapping(node, deep=True)


Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def usd(d):
    """A charge as the rule writes it: plain decimal notation, at least two places, no float noise."""
    text = format(d.normalize() if d else Decimal(0), "f")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def charges(row):
    """{token type: Decimal} for one valid meter.prices row."""
    p = {f: Decimal(str(row[f])) for f in FIELDS if f in row}
    write = p.get("cacheWrite", p["input"])
    return {"input": p["input"], "output": p["output"],
            "cached_input": p["cacheRead"] - p["input"], "cache_creation_input": write - p["input"]}


def load_prices(root, errors):
    """meter.prices as written, rows in file order; {} after an error."""
    docs = [d for d in yaml.safe_load_all((root / VALUES).read_text()) if isinstance(d, dict)]
    cm = next((d for d in docs if d.get("kind") == "ConfigMap"
               and (d.get("metadata") or {}).get("name") == VALUES_NAME), None)
    if cm is None:
        errors.append(f"{VALUES}: no ConfigMap {VALUES_NAME}")
        return {}
    values = yaml.safe_load((cm.get("data") or {}).get("values.yaml") or "") or {}
    prices = ((values.get("config") or {}).get("meter") or {}).get("prices")
    if not isinstance(prices, dict) or not prices:
        errors.append(f"{VALUES}: config.meter.prices holds no row")
        return {}
    for model, row in prices.items():
        where = f"{VALUES}: meter.prices.{model}"
        if not isinstance(model, str) or not MODEL.match(model):
            errors.append(f"{VALUES}: meter.prices key {model!r} is not a served model name")
        if not isinstance(row, dict):
            errors.append(f"{where} is a mapping of {', '.join(FIELDS)}")
            continue
        for key in sorted(set(row) - set(FIELDS) - set(METADATA), key=str):
            errors.append(f"{where}: unknown key {key}; a row holds {', '.join(FIELDS + METADATA)}")
        for f in FIELDS:
            v = row.get(f)
            if f not in row:
                if f in REQUIRED:
                    errors.append(f"{where}: missing {f}")
            elif isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                errors.append(f"{where}: {f} must be a positive number of USD per million tokens, got {v!r}")
    return prices


def group(prices, indent):
    """The group's text at `indent`, and the structure it must parse back to."""
    rules, lines = [], [f"{indent}- name: {GROUP}", f"{indent}  interval: {INTERVAL}", f"{indent}  rules:"]
    for model, row in prices.items():
        listed = ", ".join(f"{f} {usd(Decimal(str(row[f])))}" for f in FIELDS if f in row)
        lines.append(f"{indent}    # {model}: {listed}" + ("" if "cacheWrite" in row else "; writes cost as input"))
        for t, charge in charges(row).items():
            rules.append({"record": RECORD, "expr": f"vector({usd(charge)})",
                          "labels": {"gen_ai_request_model": model, "gen_ai_token_type": t}})
            lines += [f"{indent}    - record: {RECORD}", f"{indent}      expr: vector({usd(charge)})",
                      f"{indent}      labels:", f'{indent}        gen_ai_request_model: "{model}"',
                      f"{indent}        gen_ai_token_type: {t}"]
    return "".join(f"{line}\n" for line in lines), {"name": GROUP, "interval": INTERVAL, "rules": rules}


def groups_of(text):
    """Every group of the file's VMRule documents, in order; None when a mapping repeats a key."""
    try:
        docs = list(yaml.load_all(text, Loader=Strict))
    except yaml.constructor.ConstructorError:
        return None
    return [g for d in docs if isinstance(d, dict) and d.get("kind") == "VMRule"
            for g in (d.get("spec") or {}).get("groups") or []]


def render(root):
    """(the rule file with the group rendered from meter.prices, []) or (None, the errors that prevent it)."""
    root = pathlib.Path(root)
    errors = []
    prices = load_prices(root, errors)
    if errors:
        return None, errors
    current = (root / RULES).read_text()
    found = list(BLOCK.finditer(current))
    if len(found) != 1:
        return None, [f"{RULES}: expected one group `- name: {GROUP}`, found {len(found)}"]
    m = found[0]
    text, want = group(prices, m["indent"])
    spliced = current[:m.start()] + text + current[m.end():]
    # The splice replaces the lines indented under the group's name only: a group whose lines are
    # written otherwise (a flow mapping, a blank line inside, no final newline) would leave pieces
    # behind, so the result must parse back to exactly the rendering, and every other group unchanged.
    before = [g for g in groups_of(current) or [] if g.get("name") != GROUP]
    after = groups_of(spliced) or []
    if [g for g in after if g.get("name") == GROUP] != [want] or [g for g in after if g.get("name") != GROUP] != before:
        return None, [f"{RULES}: group {GROUP} holds lines the generator does not own (a blank line, a flow "
                      "mapping, or no final newline?): write it as a block, or delete it and run --write"]
    return spliced, []


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
    current = (root / RULES).read_text()
    if rendered == current:
        print(f"gen-prices: {RULES} group {GROUP} is meter.prices' rendering")
        return 0
    if write:
        (root / RULES).write_text(rendered)
        print(f"gen-prices: wrote {RULES} group {GROUP}")
        return 0
    sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), rendered.splitlines(True),
                                               f"{RULES} (committed)", f"{RULES} (rendered from meter.prices)"))
    print(f"FAIL {RULES} group {GROUP} differs from meter.prices' rendering: edit the price in {VALUES}, run "
          "python3 scripts/ci/gen-prices.py --write and commit both", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

Two details matter here. The values file's `values.yaml` holds `${cluster_name}`, which is a plain
YAML string, so `safe_load` reads it as is. And `Decimal(str(v))` takes Python's shortest repr of
the YAML float (`0.26` → `"0.26"`), which is why the subtraction is exact.

- [ ] **Step 4: Run the unit tests**

```bash
chmod +x scripts/ci/gen-prices.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-prices.py; echo "exit=$?"
```

Expected: 26 `ok` lines (4 rendering, 4 parity, 6 drift, 1 for a group the generator does not fully
own, 11 for refused and accepted rows), then `all passed` and `exit=0`. The tests copy the tree and
render it first, so they pass whatever state the committed group is in.

- [ ] **Step 5: Run it on the real tree, which still holds the hand-kept prices**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-prices.py 2>&1 | tail -3; echo "exit=${PIPESTATUS[0]}"
```

Expected: the tail of a unified diff whose `-` lines name `llm_gateway:price_usd_per_mtoken` and
whose `+` lines name `llm_gateway:charge_usd_per_mtoken`, then
`FAIL infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml group llm-gateway-prices differs from meter.prices' rendering: edit the price in tooling/base/agent-factory/helm-values-configmap.yaml, run python3 scripts/ci/gen-prices.py --write and commit both`,
then `exit=1`. Task 2 writes the group. Do not run `--write` here.

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/gen-prices.py scripts/ci/tests/test-gen-prices.py
git commit -m "feat(ci): gen-prices renders the charge rule from meter.prices"
```

---

### Task 2: The charge rule, its readers, and the suites that hold them

**Files:**
- Create: `scripts/ci/tests/test-agent-cost-rules.sh`
- Create: `scripts/ci/tests/test-agent-prices.sh`
- Modify: `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml`: the group (generated) and the
  comment above it (lines 10–14)
- Modify: `observability/base/agent-platform/vmrule.yaml`: `AnthropicFleetNearCap` (lines 110–112)
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-run.yaml`: panel 10,
  *Cost (USD)* (lines 75 and 80)

**Interfaces:**
- Consumes: Task 1's CLI and its exit codes.
- Produces: the series `llm_gateway:charge_usd_per_mtoken{gen_ai_request_model, gen_ai_token_type}`,
  24 rules. The suite `test-agent-cost-rules`, whose extraction Task 3 extends: it builds
  `rules.yaml` with the groups `llm-gateway-prices` and `cost-alerts`, and in its tests the shell
  variable `G` holds the token series' selector prefix.

- [ ] **Step 1: Write the failing promtool suite**

`scripts/ci/tests/test-agent-cost-rules.sh`:

```bash
#!/usr/bin/env bash
# requires: promtool python3
#
# Truthful costs, offline proof 3: the costs read through llm_gateway:charge_usd_per_mtoken, evaluated
# by promtool on synthetic series shaped as the agent router's scrape leaves them (vmpodscrape.yaml:
# cache tokens counted inside input). The rules are the committed ones: the generated
# llm-gateway-prices group, AnthropicFleetNearCap and the agent-run dashboard's Cost panel query.
# - The measured reply (input 1050 with 900 read and 50 written, output 10, on Opus) costs $0.00103
#   on the Cost panel.
# - A cache-heavy Opus day of $5 ($20 at list prices) does not fire AnthropicFleetNearCap; $14 does.
#   GLM spend never counts toward it.
# Annotations are stripped from the copy promtool reads: it compares them exactly, and
# test-agent-alert-annotations owns them.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp" python3 - <<'PY' || exit 1
import json
import os
import sys

import yaml

root, out = os.environ["ROOT"], os.environ["OUT"]


def docs(rel):
    return [d for d in yaml.safe_load_all(open(os.path.join(root, rel))) if isinstance(d, dict)]


def group(rel, name):
    found = [g for d in docs(rel) if d.get("kind") == "VMRule" for g in d["spec"]["groups"] if g["name"] == name]
    if len(found) != 1:
        sys.exit(f"{rel}: expected one group {name}, found {len(found)}")
    return found[0]


def alert(rel, group_name, name):
    found = [r for r in group(rel, group_name)["rules"] if r.get("alert") == name]
    if len(found) != 1:
        sys.exit(f"{rel}: expected one alert {name}, found {len(found)}")
    found[0].pop("annotations", None)
    return found[0]


prices = group("infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml", "llm-gateway-prices")
near = alert("observability/base/agent-platform/vmrule.yaml", "agent-gateway", "AnthropicFleetNearCap")
THRESHOLD = " > 13.6"
if not near["expr"].endswith(THRESHOLD):
    sys.exit(f"AnthropicFleetNearCap no longer ends with{THRESHOLD}: update this test's days")
# The alert's figure, without its threshold, so a test can read the dollars.
fleet = {"record": "test:anthropic_fleet:usd24h", "expr": near["expr"][:-len(THRESHOLD)]}
dashboard = next(d for d in docs("observability/base/agent-platform/grafana-dashboard-agent-run.yaml")
                 if d.get("kind") == "GrafanaDashboard")
panel = next(p for p in json.loads(dashboard["spec"]["json"])["panels"] if p.get("title") == "Cost (USD)")
# The panel as Grafana runs it on run "wire" over a 1h range ($${run} is Flux's escape for ${run}).
query = panel["targets"][0]["expr"].replace("$${run}", "wire").replace("$__range", "1h")
if "$" in query or "'" in query:
    sys.exit(f"the Cost panel's query holds a variable this test does not set: {query}")
yaml.safe_dump({"groups": [prices, {"name": "cost-alerts", "rules": [near, fleet]}]},
               open(os.path.join(out, "rules.yaml"), "w"), sort_keys=False)
open(os.path.join(out, "panel.promql"), "w").write(query)
PY

PANEL="$(cat "$tmp/panel.promql")"
G='gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent="system:serviceaccount:agents:xplane-run-'
cat > "$tmp/tests.yaml" <<EOF
rule_files: [rules.yaml]
evaluation_interval: 1m
tests:
  # The reply the wire test sends, measured on agentgateway 1.6: input 1050 counts the 900 read and
  # the 50 written. 1050 x 4.00 - 900 x 3.80 + 50 x 1.00 + 10 x 20.00 = 1030 per million. The
  # reasoning series is inside output and has no charge: it adds nothing.
  - interval: 1m
    input_series:
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0 1050x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0 900x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0 50x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0 10x10'}
      - {series: '${G}wire", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="reasoning"}', values: '0 4x10'}
    promql_expr_test:
      - expr: '${PANEL}'
        eval_time: 10m
        exp_samples:
          - value: 0.00103
  # A cache-heavy Opus day: 4.75M input with 4.0M read and 0.2M written, 0.05M output. The meter's
  # formula: 0.55M x 4.00 + 4.0M x 0.20 + 0.2M x 5.00 + 0.05M x 20.00 = \$5.00; input at list price
  # would read \$20. GLM-5.3's \$20 that day is not Anthropic's.
  - interval: 1m
    input_series:
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0+95000x50 4750000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0+80000x50 4000000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0+4000x50 200000x40'}
      - {series: '${G}day", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0+1000x50 50000x40'}
      - {series: '${G}glm", gen_ai_request_model="glm-5.3", gen_ai_token_type="input"}', values: '0+200000x50 10000000x40'}
      - {series: '${G}glm", gen_ai_request_model="glm-5.3", gen_ai_token_type="output"}', values: '0+20000x50 1000000x40'}
    promql_expr_test:
      - expr: test:anthropic_fleet:usd24h
        eval_time: 90m
        exp_samples:
          - {labels: 'test:anthropic_fleet:usd24h', value: 5}
    alert_rule_test:
      - {eval_time: 90m, alertname: AnthropicFleetNearCap, exp_alerts: []}
  # The same mix at 2.8x: \$14.00, over 80% of B6's \$17. It crosses \$13.60 at about 49 minutes.
  - interval: 1m
    input_series:
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="input"}', values: '0+266000x50 13300000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cached_input"}', values: '0+224000x50 11200000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="cache_creation_input"}', values: '0+11200x50 560000x40'}
      - {series: '${G}big", gen_ai_request_model="claude-opus-5-5", gen_ai_token_type="output"}', values: '0+2800x50 140000x40'}
    promql_expr_test:
      - expr: test:anthropic_fleet:usd24h
        eval_time: 90m
        exp_samples:
          - {labels: 'test:anthropic_fleet:usd24h', value: 14}
    alert_rule_test:
      - {eval_time: 45m, alertname: AnthropicFleetNearCap, exp_alerts: []}
      - eval_time: 90m
        alertname: AnthropicFleetNearCap
        exp_alerts:
          - exp_labels: {severity: warning}
EOF

cd "$tmp" && promtool test rules tests.yaml
```

Every counter starts at 0, which keeps `increase()` exact: Prometheus extrapolates no further back
than the point where a counter would reach zero, and each evaluation lands on a sample.

- [ ] **Step 2: Run it and watch today's rules fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
chmod +x scripts/ci/tests/test-agent-cost-rules.sh
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh; echo "exit=$?"
```

Expected: `FAILED:` with today's figures, about 4× high:
- the panel query `exp: {} 1.03E-03`, `got: {} 4.4E-03`;
- `test:anthropic_fleet:usd24h` `exp … 5E+00`, `got … 2E+01`, and `AnthropicFleetNearCap` firing at
  1h30m on the $5 day;
- `exp … 1.4E+01`, `got … 5.6E+01`, and the alert already firing at 45m;

then `exit=1`.

- [ ] **Step 3: Write the drift suite and watch it fail**

`scripts/ci/tests/test-agent-prices.sh`:

```bash
#!/usr/bin/env bash
# requires: python3
#
# Truthful costs TC3, offline proof 1: the llm-gateway-prices group committed in
# infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml is exactly what scripts/ci/gen-prices.py
# renders from meter.prices (tooling/base/agent-factory/helm-values-configmap.yaml), as AG8 holds
# the budgets' cost string to the same table. A row edited by hand, or a price changed without
# --write, fails here with the diff. The real tree.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
python3 "$ROOT/scripts/ci/gen-prices.py" "$ROOT"
```

```bash
chmod +x scripts/ci/tests/test-agent-prices.sh
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-prices.sh 2>&1 | tail -1; echo "exit=${PIPESTATUS[0]}"
shellcheck scripts/ci/tests/test-agent-prices.sh scripts/ci/tests/test-agent-cost-rules.sh
```

Expected: `FAIL infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml group llm-gateway-prices differs from meter.prices' rendering: …`,
then `exit=1`. shellcheck prints nothing.

- [ ] **Step 4: Render the group, and rewrite the comment above it**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-prices.py --write
grep -c 'record: llm_gateway:charge_usd_per_mtoken' infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml
```

Expected: `gen-prices: wrote infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml group llm-gateway-prices`,
then `24`.

In `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml`, replace:

```yaml
    # List price per 1M tokens, keyed by the model actually served
    # (gen_ai_request_model, after modelNameOverride). This is data, not a
    # measurement: SP3's cost reports and the routing dashboard multiply token
    # counters by it. Cached-input prices are left out, because budgets assume
    # no cache discount (design section 6).
```

with:

```yaml
    # Generated from meter.prices (tooling/base/agent-factory/helm-values-configmap.yaml)
    # by scripts/ci/gen-prices.py --write: edit a price there, never here, and
    # test-agent-prices fails on a hand edit. Per served model (gen_ai_request_model,
    # after modelNameOverride), what one counted token of each type adds to the cost
    # (truthful costs TC2). Every gateway counts cache tokens inside input, so a read
    # adds cacheRead - input and a write cacheWrite - input (0 where none is billed).
    # A cost joins all four types; the agent-run Cost panel and AnthropicFleetNearCap
    # show how, and test-agent-cost-rules evaluates both.
```

The file's head now reads:

```yaml
    - name: llm-gateway-prices
      interval: 5m
      rules:
        # glm-5.3: input 1.40, cacheRead 0.26, output 4.40; writes cost as input
        - record: llm_gateway:charge_usd_per_mtoken
          expr: vector(1.40)
          labels:
            gen_ai_request_model: "glm-5.3"
            gen_ai_token_type: input
```

and the 24 values are the spec's table. The comment sits outside the group, so the drift suite
ignores it.

- [ ] **Step 5: Move `AnthropicFleetNearCap` to the charge**

In `observability/base/agent-platform/vmrule.yaml`, replace:

```yaml
        # B6's mirror in USD (ratelimit.yaml: 10M reference tokens = $17/day), before it refuses.
        - alert: AnthropicFleetNearCap
          expr: sum(sum by (gen_ai_request_model, gen_ai_token_type) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_request_model=~"claude-.*", gen_ai_token_type=~"input|output"}[24h])) * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:price_usd_per_mtoken) / 1e6 > 13.6
```

with:

```yaml
        # B6's mirror in USD (ratelimit.yaml: 10M reference tokens = $17/day), before it refuses.
        # The four counted types, each at its charge (vmrule-llm-gateway.yaml, generated from
        # meter.prices): cache tokens are counted inside input, so a read adds cacheRead - input.
        - alert: AnthropicFleetNearCap
          expr: sum(sum by (gen_ai_request_model, gen_ai_token_type) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_request_model=~"claude-.*", gen_ai_token_type=~"input|output|cached_input|cache_creation_input"}[24h])) * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:charge_usd_per_mtoken) / 1e6 > 13.6
```

- [ ] **Step 6: Move the *Cost (USD)* panel to the charge**

In `observability/base/agent-platform/grafana-dashboard-agent-run.yaml`, replace:

```json
         "description": "Gateway tokens × llm_gateway:price_usd_per_mtoken.",
```

with:

```json
         "description": "The run's gateway tokens, input, output, cache reads and cache writes, each × llm_gateway:charge_usd_per_mtoken: what one counted token of that type adds, generated from meter.prices. The meter's agent_factory_run_cost_usd is the figure the caps use.",
```

Then, in the same panel's target, replace:

```text
gen_ai_token_type=~\"input|output\"}[$__range])) * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:price_usd_per_mtoken) / 1e6"
```

with:

```text
gen_ai_token_type=~\"input|output|cached_input|cache_creation_input\"}[$__range])) * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:charge_usd_per_mtoken) / 1e6"
```

The *Tokens vs budget* panel (id 3) also reads `input|output` over `$__range`, without a join: leave
it alone. The match above ends in `price_usd_per_mtoken) / 1e6"`, so it is unique.

- [ ] **Step 7: Run the three suites**

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh; echo "exit=$?"
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-prices.sh; echo "exit=$?"
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-prices.py | tail -1
git grep -n "price_usd_per_mtoken\|glm-5.2" -- infrastructure observability
```

Expected: `SUCCESS` and `exit=0`; `gen-prices: … is meter.prices' rendering` and `exit=0`;
`all passed`; and no `git grep` output.

- [ ] **Step 8: Prove that a hand edit fails (offline proof 1)**

```bash
sed -i 's/expr: vector(-3.80)/expr: vector(-3.70)/' infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-prices.sh; echo "exit=$?"
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-prices.py --write
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-prices.sh; echo "exit=$?"
```

Expected: a diff with `-          expr: vector(-3.70)` and `+          expr: vector(-3.80)`, the `FAIL`
line and `exit=1`. Then `--write` restores the rendering, and the last run prints `exit=0`. Use
`--write` here, not `git checkout`: the group is not committed yet.

- [ ] **Step 9: Commit**

```bash
git add scripts/ci/tests/test-agent-cost-rules.sh scripts/ci/tests/test-agent-prices.sh \
  infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml observability/base/agent-platform/vmrule.yaml \
  observability/base/agent-platform/grafana-dashboard-agent-run.yaml
git commit -m "feat(observability): price the fleet alert and the run's cost with the generated charge rule"
```

---

### Task 3: `AgentMeterInputExcludesCache`

**Files:**
- Modify: `scripts/ci/tests/test-agent-cost-rules.sh` (Task 2's file)
- Modify: `observability/base/agent-platform/vmrule-agent-factory.yaml`: append after
  `AgentModelUnpriced`, the file's last rule
- Modify: `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md`: Part E, from #95

**Interfaces:**
- Consumes: the meter's counter `agent_factory_meter_input_excludes_cache_runs_total{model}`, in
  agent-platform v0.15.6, the pinned release (`internal/factory/fmetrics/fmetrics.go:247`), and its
  log line `the gateway reported a model's input without its cache tokens` (`meter.go`,
  `excludesCache`). Task 2's suite.
- Produces: the alert `AgentMeterInputExcludesCache{model, severity="warning"}`, which Task 5's site
  text names.

- [ ] **Step 1: Rebase onto #95**

```bash
gh pr view 95 --json state -q .state
git fetch origin && git rebase origin/main
test -f scripts/ci/tests/test-agent-gateway-cache-wire.sh && grep -c '^## Part E — the cache-read share' docs/runbooks/agent-factory/04-gateway-secrets-budgets.md
```

Expected: `MERGED`, a clean rebase, then `1`. If #95 is not `MERGED`, stop here and report: Tasks 3
and 4 extend its files.

- [ ] **Step 2: Extend the suite**

In `scripts/ci/tests/test-agent-cost-rules.sh`, make five replacements.

The header: replace

```bash
# llm-gateway-prices group, AnthropicFleetNearCap and the agent-run dashboard's Cost panel query.
```

with

```bash
# llm-gateway-prices group, AnthropicFleetNearCap, AgentMeterInputExcludesCache, and the agent-run
# dashboard's Cost panel query.
```

and replace

```bash
#   GLM spend never counts toward it.
# Annotations are stripped
```

with

```bash
#   GLM spend never counts toward it.
# - The meter's input-excludes-cache counter, born at 1, fires AgentMeterInputExcludesCache.
# Annotations are stripped
```

The extraction: replace

```python
near = alert("observability/base/agent-platform/vmrule.yaml", "agent-gateway", "AnthropicFleetNearCap")
```

with

```python
near = alert("observability/base/agent-platform/vmrule.yaml", "agent-gateway", "AnthropicFleetNearCap")
excludes = alert("observability/base/agent-platform/vmrule-agent-factory.yaml", "agent-factory",
                 "AgentMeterInputExcludesCache")
```

and replace `"rules": [near, fleet]` with `"rules": [near, excludes, fleet]`.

The test: replace

```bash
G='gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent="system:serviceaccount:agents:xplane-run-'
```

with

```bash
G='gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent="system:serviceaccount:agents:xplane-run-'
M='agent_factory_meter_input_excludes_cache_runs_total{namespace="agent-system", pod="agent-factory-0"'
```

and insert, after the line `          - exp_labels: {severity: warning}` and before `EOF`:

```yaml
  # The meter counts a run whose input came without its cache tokens. A new series is born at 1
  # (its first increment) and fires at once, until it is an hour old. An hour-old series fires when
  # it moves, and not while it stands still.
  - interval: 1m
    input_series:
      - {series: '${M}, model="claude-opus-5-5"}', values: '_x65 1x135'}
      - {series: '${M}, model="glm-5.3"}', values: '2x200'}
      - {series: '${M}, model="glm-5.3-flash"}', values: '2x100 3x100'}
    alert_rule_test:
      - {eval_time: 64m, alertname: AgentMeterInputExcludesCache, exp_alerts: []}
      - eval_time: 70m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: claude-opus-5-5}
      - eval_time: 110m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: claude-opus-5-5}
          - exp_labels: {severity: warning, model: glm-5.3-flash}
      - eval_time: 130m
        alertname: AgentMeterInputExcludesCache
        exp_alerts:
          - exp_labels: {severity: warning, model: glm-5.3-flash}
      - {eval_time: 170m, alertname: AgentMeterInputExcludesCache, exp_alerts: []}
```

- [ ] **Step 3: Run it and watch it fail**

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh; echo "exit=$?"
```

Expected: `observability/base/agent-platform/vmrule-agent-factory.yaml: expected one alert AgentMeterInputExcludesCache, found 0`,
then `exit=1`.

- [ ] **Step 4: Write the alert**

Append to `observability/base/agent-platform/vmrule-agent-factory.yaml`, after `AgentModelUnpriced`'s
last line (`            dashboard: "https://grafana.${private_domain_name}/d/agent-factory"`, the file's
last line):

```yaml
        - alert: AgentMeterInputExcludesCache
          # Truthful costs TC4. Every gateway counts cache tokens inside `input`: the charge rule
          # (vmrule-llm-gateway.yaml), the agent-cache share and the gateway budgets' CEL rest on it.
          # The meter counts each run whose input reads below its cache tokens, once per model, and
          # prices it right. The counter is born at its first increment, which promtool's increase()
          # reads as 0: compare with an hour ago, absence read as 0 (as agent_router:budget_*).
          expr: sum by (model) (clamp_min(agent_factory_meter_input_excludes_cache_runs_total - (agent_factory_meter_input_excludes_cache_runs_total offset 1h or agent_factory_meter_input_excludes_cache_runs_total * 0), 0)) > 0
          labels:
            severity: warning
          annotations:
            summary: "A gateway counted {{ $labels.model }}'s input without its cache tokens"
            description: "The meter priced those runs right, as fresh input. Every cost read through llm_gateway:charge_usd_per_mtoken under-counts them, down to a negative figure: the agent-run Cost panel and AnthropicFleetNearCap. A gateway path or the provider changed its usage shape: run test-agent-gateway-cache-wire against the deployed agentgateway digest. The leader's log names each run: kubectl logs -n agent-system -l app.kubernetes.io/name=agent-factory --prefix | grep 'without its cache tokens'"
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-e--the-cache-read-share"
            dashboard: "https://grafana.${private_domain_name}/d/agent-factory"
```

- [ ] **Step 5: Run it and the annotation suite**

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh; echo "exit=$?"
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-alert-annotations.sh; echo "exit=$?"
```

Expected: `SUCCESS`, `exit=0`; `PASS`, `exit=0`.

- [ ] **Step 6: Prove R6, the reason the expression is not the spec's**

```bash
cp observability/base/agent-platform/vmrule-agent-factory.yaml "$SCRATCH/vmrule-agent-factory.keep"
sed -i 's/expr: sum by (model) (clamp_min(.*$/expr: sum by (model) (increase(agent_factory_meter_input_excludes_cache_runs_total[1h])) > 0/' \
  observability/base/agent-platform/vmrule-agent-factory.yaml
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh 2>&1 | grep -A6 'time: 1h10m'
cp "$SCRATCH/vmrule-agent-factory.keep" observability/base/agent-platform/vmrule-agent-factory.yaml
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-cost-rules.sh; echo "exit=$?"
```

Expected: at `1h10m`, `exp` holds `model="claude-opus-5-5"` and `got:[]`: the spec's `increase()` form
misses a counter born at 1. After the copy back, `SUCCESS` and `exit=0`.

- [ ] **Step 7: The runbook row**

In `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md` (Part E), replace:

```markdown
| `AgentCacheMarkerMissing` | The harness could not patch the SDK | Roll the harness pin back; the patch in agent-platform's `sitecustomize.py` needs the SDK's new method |
```

with:

```markdown
| `AgentCacheMarkerMissing` | The harness could not patch the SDK | Roll the harness pin back; the patch in agent-platform's `sitecustomize.py` needs the SDK's new method |
| `AgentMeterInputExcludesCache` | The meter read a model's `input` below its cache tokens: a gateway or the provider stopped counting cache tokens inside `input`. The meter prices such a run right; the run's *Cost (USD)* panel and `AnthropicFleetNearCap` under-count it, down to a negative figure | Run `test-agent-gateway-cache-wire` against the deployed agentgateway digest: a failure on the streamed reply is the gateway. If it passes, read one reply's `usage` from the provider of the model the alert names. Until it is fixed, read money from `agent_factory_run_cost_usd` |
```

Then replace:

```markdown
Anthropic upstream and fails if the marker or the token series change.
```

with:

```markdown
Anthropic upstream and fails if the marker or the token series change.
`test-agent-cost-rules` fires `AgentMeterInputExcludesCache` on the counter's first increment.
```

- [ ] **Step 8: Commit**

```bash
git add scripts/ci/tests/test-agent-cost-rules.sh observability/base/agent-platform/vmrule-agent-factory.yaml \
  docs/runbooks/agent-factory/04-gateway-secrets-budgets.md
git commit -m "feat(observability): alert when a gateway counts input without its cache tokens"
```

---

### Task 4: A streamed reply in the wire test

**Files:**
- Modify: `scripts/ci/tests/test-agent-gateway-cache-wire.sh`, #95's version: the header, the fake
  upstream, `request()`, the requests, the checks
- Modify: `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md`: the Part E sentence Task 3
  edited

**Interfaces:**
- Consumes: Task 3's rebase. In #95's file: `request()` with modes `marked` and `control`, the
  scrape into `$tmp/metrics.txt`, and the checks' `n`, `usage` and `check`.
- Produces: the suite still named `test-agent-gateway-cache-wire`. It now also asserts that a
  streamed reply counts `input` 1050, reads 900, writes 50 and output 10.

- [ ] **Step 1: The header**

Replace:

```bash
# Standalone proves the conversion code, not the controller's translation of the CRDs.
```

with:

```bash
# Standalone proves the conversion code, not the controller's translation of the CRDs.
# A last request streams (truthful costs TC4): its reply must be counted as the others are, input
# including the cache reads and writes, which llm_gateway:charge_usd_per_mtoken's join rests on.
```

- [ ] **Step 2: The fake answers a stream with Messages events**

Replace:

```python
"""Stands in for api.anthropic.com: records each request, answers one Messages reply with cache usage."""
```

with:

```python
"""Stands in for api.anthropic.com: records each request, answers one Messages reply with cache usage,
as events when the request streams."""
```

Replace:

```python
}).encode()


class Handler(http.server.BaseHTTPRequestHandler):
```

with:

```python
}).encode()


def event(name, data):
    return ("event: %s\ndata: %s\n\n" % (name, json.dumps(data))).encode()


# The same usage as REPLY, split as Anthropic streams it: input and cache tokens in message_start,
# the output count in message_delta.
STREAM = b"".join([
    event("message_start", {"type": "message_start", "message": {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 1,
                  "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50}}}),
    event("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    event("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "ok"}}),
    event("content_block_stop", {"type": "content_block_stop", "index": 0}),
    event("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": 10}}),
    event("message_stop", {"type": "message_stop"}),
])


class Handler(http.server.BaseHTTPRequestHandler):
```

Replace:

```python
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "body": json.loads(body)}) + "\n")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(REPLY)))
        self.end_headers()
        self.wfile.write(REPLY)
```

with:

```python
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "body": body}) + "\n")
        reply, kind = (STREAM, "text/event-stream") if body.get("stream") else (REPLY, "application/json")
        self.send_response(200)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)
```

The fake's heredoc is quoted (`<<'PY'`), so `\n` reaches Python as written.

- [ ] **Step 3: A streamed request, then a second scrape**

Replace:

```bash
request() {  # $1: "marked" or "control"
  MODE="$1" python3 - <<'PY'
import json
import os

bp = {"prompt_cache_breakpoint": {"mode": "explicit"}} if os.environ["MODE"] == "marked" else {}
print(json.dumps({
    "model": "agent-default", "max_tokens": 64,
```

with:

```bash
request() {  # $1: "marked", "control" or "streamed" (marked, and streamed)
  MODE="$1" python3 - <<'PY'
import json
import os

bp = {"prompt_cache_breakpoint": {"mode": "explicit"}} if os.environ["MODE"] != "control" else {}
print(json.dumps({
    "model": "agent-default", "max_tokens": 64, **({"stream": True} if os.environ["MODE"] == "streamed" else {}),
```

Replace:

```bash
curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }
```

with:

```bash
curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }
request streamed | curl -fsS -N --max-time 10 "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- > "$tmp/stream.txt" \
  || { echo "the streamed request failed" >&2; exit 1; }
# The gateway records a stream's usage as it ends: scrape until the series move, at most 5 seconds.
for _ in $(seq 1 10); do
  curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics-stream.txt" || { echo "no metrics on $stats" >&2; exit 1; }
  grep '^agentgateway_gen_ai_client_token_usage_sum{' "$tmp/metrics.txt" > "$tmp/before.txt"
  grep '^agentgateway_gen_ai_client_token_usage_sum{' "$tmp/metrics-stream.txt" > "$tmp/after.txt"
  cmp -s "$tmp/before.txt" "$tmp/after.txt" || break
  sleep 0.5
done
```

- [ ] **Step 4: The checks**

Replace:

```bash
BODIES="$tmp/bodies.jsonl" METRICS="$tmp/metrics.txt" ROOT="$ROOT" python3 - <<'PY'
```

with:

```bash
BODIES="$tmp/bodies.jsonl" METRICS="$tmp/metrics.txt" STREAMED="$tmp/metrics-stream.txt" ROOT="$ROOT" python3 - <<'PY'
```

Replace:

```python
# The readiness loop resends the marked request until the gateway answers: the control is last.
check(len(bodies) >= 2, f"the fake upstream received {len(bodies)} requests, want at least 2 (marked, control)")
marked, control = bodies[-2], bodies[-1]
n = len(bodies)
```

with:

```python
# The readiness loop resends the marked request until the gateway answers: the control and the
# streamed request come last, and the first scrape counts every reply before the streamed one.
check(len(bodies) >= 3, f"the fake upstream received {len(bodies)} requests, want at least 3 (marked, control, streamed)")
marked, control, streamed = bodies[-3], bodies[-2], bodies[-1]
n = len(bodies) - 1
```

Replace:

```python
usage = {}
for line in open(os.environ["METRICS"]):
    if line.startswith("agentgateway_gen_ai_client_token_usage_sum{"):
        labels = dict(re.findall(r'(\w+)="([^"]*)"', line.split("}")[0]))
        usage[labels.get("gen_ai_token_type")] = usage.get(labels.get("gen_ai_token_type"), 0) + float(line.rsplit(" ", 1)[1])
        check(labels.get("gen_ai_system") == "anthropic",
              f"the token series name the provider gen_ai_system=anthropic, which the alerts select after the relabel, got {labels}")
```

with:

```python
def token_usage(path):
    """{gen_ai_token_type: tokens} summed over the gateway's token series in one scrape."""
    usage = {}
    for line in open(path):
        if line.startswith("agentgateway_gen_ai_client_token_usage_sum{"):
            labels = dict(re.findall(r'(\w+)="([^"]*)"', line.split("}")[0]))
            usage[labels.get("gen_ai_token_type")] = usage.get(labels.get("gen_ai_token_type"), 0) + float(line.rsplit(" ", 1)[1])
            check(labels.get("gen_ai_system") == "anthropic",
                  f"the token series name the provider gen_ai_system=anthropic, which the alerts select after the relabel, got {labels}")
    return usage


usage = token_usage(os.environ["METRICS"])
```

Then, after the check whose message begins `f"over {n} replies, input includes cache reads and
writes`, and before `if fails:`, insert:

```python
# Truthful costs TC4: the streamed reply is counted as the others, which the charge join and the
# meter's cost() both read as input including cache tokens.
check(streamed.get("stream") is True, f"the last request reached the upstream as a stream, got stream={streamed.get('stream')}")
after = token_usage(os.environ["STREAMED"])
delta = {t: after.get(t, 0) - usage.get(t, 0) for t in ("input", "input_cache_read", "input_cache_write", "output")}
check(delta == {"input": 1050, "input_cache_read": 900, "input_cache_write": 50, "output": 10},
      f"a streamed reply counts input 1050 (cache reads and writes included), reads 900, writes 50, output 10, got {delta}")
```

- [ ] **Step 5: Run it**

```bash
shellcheck scripts/ci/tests/test-agent-gateway-cache-wire.sh
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-gateway-cache-wire.sh; echo "exit=$?"
```

Expected: shellcheck prints nothing. With a Docker daemon: `PASS`, `exit=0`. Without one:
`SKIP: no docker daemon`, `exit=77`, and Task 6's CI run is where it must pass.

With Docker, prove the new check can fail. In `STREAM`'s `message_start`, change
`"input_tokens": 100, "output_tokens": 1` to `"input_tokens": 200, "output_tokens": 1`, run again and
expect
`FAIL  a streamed reply counts input 1050 (cache reads and writes included), reads 900, writes 50, output 10, got {'input': 1150.0, …}`.
Then set it back to 100 by hand: `git checkout` would also drop Steps 1–4.

- [ ] **Step 6: The runbook sentence**

In `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md`, replace:

```markdown
Anthropic upstream and fails if the marker or the token series change.
```

with:

```markdown
Anthropic upstream and fails if the marker or the token series change, on a plain or a streamed
reply.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/ci/tests/test-agent-gateway-cache-wire.sh docs/runbooks/agent-factory/04-gateway-secrets-budgets.md
git commit -m "test(agent-gateway): a streamed reply counts its cache tokens inside input"
```

---

### Task 5: The routing page, the cohort script's comment and the spec

**Files:**
- Modify: `website/content/docs/platform/ai-platform/routing.md`: "What a call costs" (lines 242–269),
  the meter's formula's second bullet (lines 289–292), the known-gaps row (line 517)
- Modify: `scripts/ops/github/cohort-row.py` (lines 24–25)
- Modify: `docs/superpowers/specs/2026-10-22-truthful-costs-design.md`: the status line and "Left to
  the builder"

**Interfaces:**
- Consumes: the names Tasks 1–4 produced: `scripts/ci/gen-prices.py`, `test-agent-prices`,
  `test-agent-gateway-cache-wire`, `llm_gateway:charge_usd_per_mtoken`,
  `AgentMeterInputExcludesCache`.
- Produces: nothing code reads.

- [ ] **Step 1: One price table**

In `website/content/docs/platform/ai-platform/routing.md`, replace:

```markdown
### Two price tables, and which one counts

| Table | Where | Cache-aware | Used by |
|---|---|---|---|
| `meter.prices` | `tooling/base/agent-factory/helm-values-configmap.yaml` | **yes**: `input`, `cacheRead`, `cacheWrite`, `output` | The run meter's USD caps, and the gateway budgets B1, B2, B6, whose CEL cost string gate AG8 regenerates from it. **This is the price that counts** |
| `llm_gateway:price_usd_per_mtoken` | `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml` | no: input and output only | The `agent-run` dashboard's *Cost (USD)* panel and the `AnthropicFleetNearCap` alert |
```

with:

```markdown
### One price table

`meter.prices`, in `tooling/base/agent-factory/helm-values-configmap.yaml`, is the only place a
price is edited. Every dollar figure on this page comes from it, and `task check` fails when a copy
drifts:

| Reader | Its copy of the table | Held by |
|---|---|---|
| The run meter: USD run and task caps, `agent_factory_run_cost_usd`, the `Task`'s `costMicroUSD` | The factory's config itself | — |
| Gateway budgets B1, B2, B6 | A CEL cost string in `infrastructure/base/agent-gateway/policy-budgets.yaml` | Gate AG8 regenerates it |
| The `agent-run` dashboard's *Cost (USD)* panel, `AnthropicFleetNearCap` | `llm_gateway:charge_usd_per_mtoken`, the `llm-gateway-prices` group of `infrastructure/base/llm-gateway/vmrule-llm-gateway.yaml` | `test-agent-prices`: the group is what `scripts/ci/gen-prices.py` renders |

A price change is the row's edit and `python3 scripts/ci/gen-prices.py --write`, in one commit.
```

- [ ] **Step 2: The charge series, in place of the warning**

Replace:

```markdown
{{< callout type="warning" >}}
**The dashboard's cost panel and `AnthropicFleetNearCap` overstate spend.** They multiply `input`,
cache reads included, by the full input price. At the measured mix that is about 4× the meter's
figure (see [caching](#caching)). The recording rule also lists `claude-haiku-5-5` at 0.10 / 0.50,
where `meter.prices` has 0.50 / 2.50. For money, read `agent_factory_run_cost_usd` or the `Task`'s
`costMicroUSD`.
{{< /callout >}}
```

with:

````markdown
### The charge series

The gateways count cache tokens inside `input` (see the meter's formula below), so the recording
rule holds a charge, not a price: what one counted token of each type adds to the cost.

| `gen_ai_token_type` | Charge | `claude-opus-5-5` |
|---|---|---|
| `input` | `input` | 4.00 |
| `output` | `output` | 20.00 |
| `cached_input` | `cacheRead` − `input` | −3.80 |
| `cache_creation_input` | `cacheWrite` − `input`; 0 where no write is billed (Z.ai) | 1.00 |

A cost over a window is one join, to which each reader adds its own selector:

```promql
sum(
  sum by (gen_ai_request_model, gen_ai_token_type) (
    increase(gen_ai_client_token_usage_sum{gen_ai_token_type=~"input|output|cached_input|cache_creation_input"}[24h])
  )
  * on (gen_ai_request_model, gen_ai_token_type) group_left() llm_gateway:charge_usd_per_mtoken
) / 1e6
```

The reply the wire test sends on Opus, 1,050 input of which 900 read and 50 written, and 10 output,
reads 1050 × 4.00 − 900 × 3.80 + 50 × 1.00 + 10 × 20.00 = 1,030 per million, **$0.00103**: the
meter's 100 × 4.00 + 900 × 0.20 + 50 × 5.00 + 10 × 20.00. The list-price rule it replaced read 4.3×
that. `reasoning` is inside `output` and has no charge. The join prices the whole window at today's
charges; what each run was charged stays in `agent_factory_run_cost_usd` and the `Task`'s
`costMicroUSD`.
````

- [ ] **Step 3: The counting, as measured**

Replace:

```markdown
- **The `input` series includes cache tokens** on Z.ai and on the non-streaming Chat Completions to
  Messages path, and excludes them on a streamed call or native Messages. The meter subtracts the
  cache tokens unless `input` is smaller than them, in which case it prices all of `input` as fresh
  (`inputExcludesCache`, agent-platform `internal/factory/meter/meter.go`).
```

with:

```markdown
- **The `input` series includes cache tokens** on every path this platform runs: Z.ai's OpenAI
  usage, and agentgateway's Chat Completions to Messages translation, streamed or not.
  `test-agent-gateway-cache-wire` asserts both at every agentgateway pin; the meter's comment that a
  stream leaves them out predates the measurement. The meter subtracts the cache tokens unless
  `input` is smaller than them, in which case it prices all of `input` as fresh
  (`inputExcludesCache`, agent-platform `internal/factory/meter/meter.go`) and counts the run in
  `agent_factory_meter_input_excludes_cache_runs_total`. `AgentMeterInputExcludesCache` fires on it:
  the charge series would under-count such a run, down to a negative cost.
```

Then delete this row of the "Known gaps" table:

```markdown
| Two price tables disagree | Dashboard cost and `AnthropicFleetNearCap` overstate; Haiku is mispriced in the recording rule | One table, from `meter.prices` |
```

Leave "Budgets: five layers, one exact" and its warning alone: they are PR 3's.

- [ ] **Step 4: The cohort script's comment**

In `scripts/ops/github/cohort-row.py`, replace:

```python
# USD per 1M. 1.40 in, 4.40 out: vmrule-llm-gateway.yaml. 0.26 cached: Z.ai list price; the gateway's
# VMRule prices input and output only.
```

with:

```python
# USD per 1M: glm-5.3's row in meter.prices (tooling/base/agent-factory/helm-values-configmap.yaml).
```

- [ ] **Step 5: The spec**

In `docs/superpowers/specs/2026-10-22-truthful-costs-design.md`, replace:

```markdown
decisions, and the details they left open are ruled where they appear, each with its reason ·
```

with:

```markdown
decisions, and the details they left open are ruled where they appear, each with its reason ·
**PR 1 built** ([plan](../plans/2026-10-22-truthful-costs-rule-plan.md)) ·
```

At the end of the file, after the paragraph that ends `becomes a suite.`, append:

```markdown

Ruled in PR 1 ([plan](../plans/2026-10-22-truthful-costs-rule-plan.md#this-plans-rulings)):

- **The generator** renders the whole `llm-gateway-prices` group and splices it in place: the comment
  above it and the other group stay hand-written. Charges are exact decimals with at least two places
  (`-1.14`, `0.125`, `0.00`), and the written file must parse back to the rendering.
- **The suites:** `test-gen-prices`, the generator's unit tests (offline proof 2); `test-agent-prices`,
  the drift check (offline proof 1); `test-agent-cost-rules`, promtool on the readers (offline proof 3).
- **`AgentMeterInputExcludesCache`** compares the counter with an hour ago, absence read as 0, as the
  `agent_router:budget_*` rules do. The counter is born at its first increment, which promtool's
  `increase()` reads as 0, so the expression in the table above could not be proven to fire.
```

- [ ] **Step 6: Check the links and the paths**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/validate-links.sh
git grep -n "price_usd_per_mtoken" -- ':!docs/superpowers'
```

Expected: `==> All relative Markdown links resolve`, and no `git grep` output: only the dated specs
and plans still name the old series. The site build and the doc-path check run in Task 6.

- [ ] **Step 7: Commit**

```bash
git add website/content/docs/platform/ai-platform/routing.md scripts/ops/github/cohort-row.py \
  docs/superpowers/specs/2026-10-22-truthful-costs-design.md
git commit -m "docs(ai-platform): one price table and the charge series"
```

---

### Task 6: Verify, push, open the pull request

- [ ] **Step 1: The whole check**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|PromQL expression|test-gen-prices|test-agent-prices|test-agent-cost-rules|cache-wire|passed,|resolve|docs site exists|exit=" \
  "$SCRATCH/check-$(basename "$PWD").log"
```

Expected:
- `assert-agent-gateway: 14 checks, 0 violations (clusters: aws-0, gcp-0)`
- `==> 114 PromQL expression(s) in 18 group(s) parse.`, or more if `main` has gained rules
- `PASS` for `test-gen-prices`, `test-agent-prices` and `test-agent-cost-rules`, and
  `SKIP  test-agent-gateway-cache-wire  SKIP: no docker daemon` without Docker
- `25 passed, 2 skipped, 0 failed`. With #95 merged the baseline was 22 passed and 2 skipped (the
  two Docker suites), and this plan adds three suites. Other merges may add more: what must hold is
  `0 failed` and the three `PASS` lines.
- `All relative Markdown links resolve`, `Every repository path named in the docs site exists`,
  `exit=0`

- [ ] **Step 2: Rebase and push**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/truthful-costs-rule
```

If the rebase touched any file this plan changes, run Step 1 again before pushing.

- [ ] **Step 3: Open the pull request**

Title: `feat(observability): truthful costs PR 1, the charge rule generated from meter.prices`.

The body is in English and covers:
- **The outcome:** one price table. The charge rule is generated, the fleet alert and the run's
  Cost panel read cache rates, the `glm-5.2` rows and `llm_gateway:price_usd_per_mtoken` are gone,
  and `AgentMeterInputExcludesCache` is new. Closes #75.
- **The numbers:** the measured reply at $0.00103 (4.3× lower), and the cache-heavy $5 day that
  today's rule reads as $20.
- **The rulings:** R1 to R11, R6 (the alert's expression) above all.
- **The suites,** each with its offline proof: `test-gen-prices` (2), `test-agent-prices` (1),
  `test-agent-cost-rules` (3), `test-agent-gateway-cache-wire` (4), and `task check` (5).
- **What waits:** PRs 2 to 4, and the live proofs in one gcp-0 session after PR 3.
- **The `task check` summary.**
- **A test plan:** a hand edit to a charge fails `test-agent-prices`, and the CI log shows
  `PASS  test-agent-gateway-cache-wire`.

No attribution line. The branch also carries the spec commit (`c7b4102`) and this plan.

- [ ] **Step 4: Wait for CI and read the wire test**

```bash
gh pr checks --watch
gh run view --log "$(gh run list --branch feat/truthful-costs-rule -L 1 --json databaseId -q '.[0].databaseId')" | grep -E "test-agent-gateway-cache-wire|passed,"
```

Expected: every check green, and `PASS  test-agent-gateway-cache-wire`: CI runs with `CI=true` and
Docker, so the streamed reply is proven on the pinned image there (offline proof 4).
