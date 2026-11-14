# Caching, performance and costs: Maku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure where a run's first minute and its dollars go, take the gains that cannot change a pull request (blobless clone, tuned condenser, search and summary on the light alias), then make effort and model per role trialable.

**Architecture:** Lot 1 adds two harness spans, two harness log lines, one factory histogram and two dashboard panels. Lot 2 has the run-controller hand every eligible run a light alias (URL, model, token), which the condenser and the search child then use. Lot 3 adds `effort` and `models` to a workflow definition and carries the effort to the pod. Lots 1 and 2 are additive (release N); lot 3 ships in release N+1 with the re-keyed `loops`.

**Tech Stack:** Python 3 (harness, `unittest`, OpenHands SDK at agent-server 1.56.0), Go (run-controller, factory, envtest), Helm charts, Grafana dashboard JSON, promtool.

**Spec:** `docs/superpowers/specs/2026-11-14-cache-costs-review-design.md` in ai-native-ref (decisions CP1 to CP14). Copy it beside this plan when the plan moves to Maku.

## Global Constraints

- Execute in the Maku repository, in a worktree branched from `origin/main`. Paths below are Maku's.
- `task check` exits 0 before every commit (`AGENTS.md`). Lint through `task lint` only.
- Harness suites run in the image: `docker build --target test images/maku-harness` (CI's `harness-test`).
- A type change is followed by `task crd:gen`; a chart value by `task chart:check` and `task install:schemas`.
- No metric or label is renamed. Series names are the code's `agent_factory_*`; `profile` keeps its name.
- No new setting a user must learn. The only new values are `runController.model.gateway.lightAlias` (default `tier-light`) and, in lot 3, the advanced `effort` and `models` fields.
- Public content never reaches Anthropic: a per-role model on an internal task is one of `tier-light`, `tier-standard`, `tier-frontier`.
- A run pod mounts only emptyDir, configMap, secret and projected volumes (`charts/maku/templates/run-pod-policy.yaml`). Nothing here adds a volume kind.
- Commits are conventional, in English, with no trailers.
- Lot order is fixed: lot 1, then lot 2, then lot 3. Lot 3 waits for release N+1 and for the workflows measurement.

## Review Focus

1. **A forge that refuses partial clones.** The run must still start, on a full clone, with `filter=none` on the span. Pinned in Task 7.
2. **A gateway listener that does not serve the light alias.** The run-controller refuses its config at load with the alias and the listener named; no pod is created with a dead `LIGHT_BASE_URL`. Pinned in Task 6.
3. **A provider that reports no cache fields** (Z.ai, a stub). The cache line prints zeros and the run never fails on logging. Pinned in Task 2.
4. **A resumed run.** Its first response is a miss by design: `miss=resume`, never `unexpected`. Pinned in Task 2.
5. **A task counted twice or never.** A task without a profile, and the parent of an approved split, each add exactly one count and their USD once. Pinned in Task 4.

---

## Lot 1: measure (release N)

### Task 1: `agent-run.boot` and `agent-run.clone` spans

**Files:**
- Modify: `images/maku-harness/agent_run.py` (`clone` at :1399, the server start and `wait_ready` call in `main`, span name constants beside `CHECKS_SPAN`)
- Test: `images/maku-harness/tests/test_agent_run.py`

**Interfaces:**
- Consumes: `child_spans(provider, parent)` and `_end(span, error)`, as `prefetch` uses them.
- Produces: `BOOT_SPAN = "agent-run.boot"`, `CLONE_SPAN = "agent-run.clone"`; `clone(env: dict, start_span=None) -> bool`. Task 7 sets the span's `filter` attribute.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_clone_span_carries_resumed_and_filter(self):
    spans = FakeSpans()
    with fake_git(branch_pushed=True):
        resumed = agent_run.clone(ENV, start_span=spans.start)
    self.assertTrue(resumed)
    self.assertEqual(spans.ended, [("agent-run.clone", {"resumed": True, "filter": "none"}, None)])

def test_a_failed_clone_ends_its_span_with_the_error(self):
    spans = FakeSpans()
    with fake_git(clone_fails=True), self.assertRaises(subprocess.CalledProcessError):
        agent_run.clone(ENV, start_span=spans.start)
    self.assertEqual(spans.ended[0][0], "agent-run.clone")
    self.assertIsNotNone(spans.ended[0][2])

def test_the_boot_span_ends_when_ready_answers(self):
    spans = FakeSpans()
    agent_run.boot(spans.start, wait=lambda: None)
    self.assertEqual([s[0] for s in spans.ended], ["agent-run.boot"])
```

`FakeSpans` records `(name, attributes, error)` on `end()`; `fake_git` patches `subprocess.run`. Reuse the file's existing fakes where they exist.

- [ ] **Step 2: Run them and see them fail**

Run: `docker build --target test images/maku-harness`
Expected: FAIL, `clone() got an unexpected keyword argument 'start_span'` and `module has no attribute 'boot'`.

- [ ] **Step 3: Implement**

`clone(env, start_span=None)` opens `CLONE_SPAN` before `git clone` and ends it after the checkout, with `resumed` and `filter` (`"none"` until Task 6). `boot(start_span, wait=wait_ready)` wraps the wait for `/ready`; `main` calls it right after starting `SERVER_CMD`. Both go through `_end`, so tracing off (`start_span is None`) is a no-op.

- [ ] **Step 4: Run the suite**

Run: `docker build --target test images/maku-harness`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add images/maku-harness/agent_run.py images/maku-harness/tests/test_agent_run.py
git commit -m "feat(harness): boot and clone spans under agent-run"
```

### Task 2: the cache line and the condensation line

**Files:**
- Modify: `images/maku-harness/agent_run.py` (the step log class whose `describe(event)` prints one line per event, at :1278 to :1390)
- Test: `images/maku-harness/tests/test_prompt_cache.py`

**Interfaces:**
- Produces: `cache_line(step: int, usage: dict, miss: str) -> str`, `miss_kind(step: int, cache_read: int, after_condensation: bool, resumed: bool) -> str`, `condensation_line(step: int, forgotten: int, summary_model: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_cache_line(self):
    usage = {"prompt_tokens": 182340, "cache_read_tokens": 176902, "cache_write_tokens": 5438}
    self.assertEqual(agent_run.cache_line(41, usage, "none"),
        "agent-run cache: step=41 input=182340 cache_read=176902 cache_write=5438 miss=none")

def test_a_provider_without_cache_fields_prints_zeros(self):
    self.assertEqual(agent_run.cache_line(3, {"prompt_tokens": 900}, "first"),
        "agent-run cache: step=3 input=900 cache_read=0 cache_write=0 miss=first")

def test_miss_kinds(self):
    k = agent_run.miss_kind
    self.assertEqual(k(1, 0, False, False), "first")
    self.assertEqual(k(1, 0, False, True), "resume")
    self.assertEqual(k(81, 0, True, False), "condensation")
    self.assertEqual(k(12, 0, False, False), "unexpected")
    self.assertEqual(k(12, 5000, False, False), "none")

def test_the_condensation_line(self):
    self.assertEqual(agent_run.condensation_line(80, 76, "tier-light"),
        "agent-run condensation: step=80 forgotten=76 summary_model=tier-light")

def test_a_usage_the_log_cannot_read_never_fails_the_run(self):
    log = step_log()
    log.describe({"kind": "MessageEvent", "llm_response": {"usage": "garbage"}})  # no raise
```

- [ ] **Step 2: Run and see them fail**

Run: `docker build --target test images/maku-harness`
Expected: FAIL, `module 'agent_run' has no attribute 'cache_line'`.

- [ ] **Step 3: Implement**

The three functions are pure. `describe` calls them when an event carries a model response's usage, and on a condensation event. How usage is read (the event's own usage, or a delta of the conversation's stats) is the implementer's choice; pick the one the SDK at 1.56.0 exposes per response and name it in the PR. `summary_model` is `LIGHT_MODEL` when set, else the run's `MODEL`.

- [ ] **Step 4: Run the suite**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): a cache line per response and a line per condensation (C1)"
```

### Task 3: the wait between two runs of a task

**Files:**
- Modify: `internal/factory/fmetrics/fmetrics.go` (register beside `humanWait`; method beside `HumanWait` at :868)
- Modify: `internal/factory/reconciler/reconciler.go` (the `Metrics` interface at :120), `internal/factory/reconciler/implement.go` (the two `Status.Runs = append(...)` sites at :139 and :312)
- Test: `internal/factory/fmetrics/fmetrics_test.go`, `internal/factory/reconciler/outcomes_test.go`

**Interfaces:**
- Produces: histogram `agent_factory_run_wait_seconds`, label `role` (bounded by `costRoles()`), buckets `30, 60, 120, 300, 600, 1800, 3600, 14400`; `func (s *Set) RunWait(ctx context.Context, role string, d time.Duration)`.

- [ ] **Step 1: Write the failing tests**

```go
func TestRunWaitIsLabelledByTheNextRunsRole(t *testing.T) {
	s, read := newSet(t)
	s.RunWait(ctx, "reviewer", 7*time.Minute)
	h := read.histogram(t, "agent_factory_run_wait_seconds", attribute.String("role", "reviewer"))
	if h.Count != 1 || h.Sum != 420 { t.Fatalf("got %+v", h) }
}

func TestASecondRunRecordsTheWaitSinceTheFirstEnded(t *testing.T) {
	// a task whose implementer run finished at T; its reviewer launches at T+7m
	// want: exactly one RunWait("reviewer", 7m); the first run of a task records none
}
```

- [ ] **Step 2: Run and see them fail**

Run: `go test ./internal/factory/fmetrics/ ./internal/factory/reconciler/ -run 'RunWait|SecondRun' -count=1`
Expected: FAIL, `s.RunWait undefined`.

- [ ] **Step 3: Implement**

At each launch site, when the task already has a finished run, call `RunWait` with the new run's role and `now - latest Finished`. A run launched while another is unfinished records nothing.

- [ ] **Step 4: Run**

Run: `task test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(factory): agent_factory_run_wait_seconds, the wait between two runs of a task"
```

### Task 4: the task counters count every ended task

**Files:**
- Modify: `internal/factory/reconciler/outcome.go` (`count` and `counting`, around :198), `internal/factory/fmetrics/fmetrics.go` (`TaskOutcome` at :927 and the two descriptions at :499 to :503), `api/factory/v1alpha1/task_types.go` (one status field)
- Test: `internal/factory/reconciler/outcome_test.go`, `internal/factory/fmetrics/fmetrics_test.go`

**Interfaces:**
- Produces: `Task.Status.OutcomeCounted bool` (`json:"outcomeCounted,omitempty"`), the once-mark of a task with no profile. A profile-less task is counted with `profile="none"`, `cohort="none"`, `source="floor"`, `recommended="none"`. `TaskOutcome`'s signature is unchanged.

- [ ] **Step 1: Write the failing tests**

```go
func TestATaskWithoutAProfileIsCountedOnce(t *testing.T) {
	// a Done task, Status.Profile nil, Outcome "accepted", cost 1_650_000 micro USD; reconcile twice
	// want: one TaskOutcome(class, "none", "none", "floor", "none", "accepted", 1.65)
	// want: Status.OutcomeCounted == true
}

func TestAnApprovedSplitIsCountedOnceWithItsPartsUSD(t *testing.T) {
	// existing family fixture: assert exactly one count for the parent, none for its parts
}

func TestTaskOutcomeAcceptsTheNoneCohort(t *testing.T) {
	s, read := newSet(t)
	s.TaskOutcome(ctx, "docs", "none", "none", "floor", "", "accepted", 1.65)
	read.counter(t, "agent_factory_task_outcomes_total", 1, attribute.String("cohort", "none"), attribute.String("profile", "none"))
}
```

- [ ] **Step 2: Run and see them fail**

Run: `go test ./internal/factory/reconciler/ ./internal/factory/fmetrics/ -run 'WithoutAProfile|NoneCohort|ApprovedSplit' -count=1`
Expected: FAIL (no count; cohort folded to `other`).

- [ ] **Step 3: Implement**

`counting` admits a profile-less ended task that is not yet `OutcomeCounted`; `count` sets the mark on the same status write. `TaskOutcome` admits `none` in its cohort set. Both descriptions drop "with a profile".

- [ ] **Step 4: Regenerate and run**

Run: `task crd:gen && task check`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(factory): the task outcome counters count every ended task"
```

### Task 5: the dashboard panels

**Files:**
- Modify: `charts/agent-factory/files/dashboards/agent-factory.json` (two panels after the per-role cost panel), `charts/agent-factory/files/dashboards/agent-run.json` (a start row)
- Test: `charts/agent-factory/tests/render.sh` (the dashboards block at :712)

**Interfaces:**
- Consumes: Task 3's and Task 4's series; the spans of Task 1 (through the trace link the run dashboard already has).

- [ ] **Step 1: Write the failing assertions** in `tests/render.sh`, after the existing dashboard checks

```bash
has_panel agent-factory "Cost per merged pull request, by workflow" \
  'sum by (profile) (increase(agent_factory_task_usd_total[$__range])) / sum by (profile) (increase(agent_factory_task_outcomes_total{outcome=~"accepted|merged_human"}[$__range]))'
has_panel agent-factory "Cost per merged pull request, by role" \
  'sum by (role) (increase(agent_factory_run_cost_usd_sum[$__range])) / scalar(sum(increase(agent_factory_task_outcomes_total{outcome=~"accepted|merged_human"}[$__range])))'
has_panel agent-factory "Wait between runs over 5 minutes" \
  '1 - sum by (role) (increase(agent_factory_run_wait_seconds_bucket{le="300"}[$__range])) / sum by (role) (increase(agent_factory_run_wait_seconds_count[$__range]))'
has_panel agent-run "Start: pod, boot, clone" ''
```

`has_panel <dashboard> <title> <expr>` reads `files/dashboards/<dashboard>.json` with `jq`, fails when no panel has the title, and when `<expr>` is not empty fails unless one of that panel's targets is exactly it. Add the helper beside `dashboards()`.

- [ ] **Step 2: Run and see it fail**

Run: `task chart:check`
Expected: FAIL, `no panel "Cost per merged pull request, by workflow"`.

- [ ] **Step 3: Add the panels**

The three expressions are exactly those above. The start row shows pod created → Ready (the Kubernetes reading the dashboard already queries) beside the durations of `agent-run.boot` and `agent-run.clone`. Each panel's description states its denominator: merged pull requests, failed tasks' spend included.

- [ ] **Step 4: Run**

Run: `task chart:check`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(chart): cost per merged pull request, the wait between runs and the start row"
```

---

## Lot 2: gains with no setting (release N)

### Task 6: the light alias on the run (CP12)

**Files:**
- Modify: `internal/runctl/config.go` (`Gateway` struct near :196, `model()` at :232, `Model` at :597, `GatewayModel` at :620, `gatewayInvalid` at :641), `internal/runctl/pod.go` (env at :155 to :183, `modelVolumeSource` at :324)
- Modify: `charts/maku/values.yaml` (:286 to :300), `charts/maku/values.schema.json`, `charts/maku/templates/run-controller-config.yaml`
- Test: `internal/runctl/gateway_test.go`, `internal/runctl/config_test.go`, `internal/runctl/judge_test.go`, `internal/runctl/testdata/pod-gateway.golden.yaml`, `charts/maku/tests/render.sh`

**Interfaces:**
- Produces: config key `model.gateway.lightAlias` (default `tier-light`); `Model.Light`, `Model.LightBaseURL`; `func lightOn(r *v1alpha1.AgentRun) bool` (true for a run whose data class is `internal`, or whose `spec.loop.search` is on for an implementer); pod env `LIGHT_BASE_URL`, `LIGHT_MODEL`, `LIGHT_API_KEY_FILE`. Tasks 8 and 9 read those three.

| Mode | `LIGHT_BASE_URL` | `LIGHT_MODEL` | `LIGHT_API_KEY_FILE` |
|---|---|---|---|
| gateway, judge on the light alias | `<base>/m/<light>/v1` | `<light>` | `<modelDir>/judge-token` |
| gateway, no judge or a judge elsewhere | same | same | `<modelDir>/light-token`, projected with audience `<prefix>.<class>.<light>` |
| secret (portable) | the pod's `BaseURL` | the Secret's `judge_model`, else the run's model | unset: the harness falls back to `LLM_API_KEY_FILE` |

- [ ] **Step 1: Write the failing tests**

```go
func TestAnInternalRunGetsTheLightAlias(t *testing.T) {
	p := gatewayPod(t, gatewayRun(func(r *v1alpha1.AgentRun) { r.Spec.DataClass = "internal" }))
	env := harnessEnv(p)
	want := map[string]string{"LIGHT_BASE_URL": "http://gw.maku.svc.cluster.local:8081/m/tier-light/v1",
		"LIGHT_MODEL": "tier-light", "LIGHT_API_KEY_FILE": "/var/run/model/light-token"}
	// each key equals want; tokenSources(p, "model-token")["light-token"].Audience == "<prefix>.internal.tier-light"
}

func TestAPublicRunWithoutSearchGetsNone(t *testing.T) { /* no LIGHT_* env, no light-token source */ }

func TestAJudgeOnTheLightAliasSharesItsToken(t *testing.T) {
	// spec.loop.judgeModel "tier-light", internal: LIGHT_API_KEY_FILE ends in /judge-token; one judge-token source, no light-token
}

func TestAJudgeElsewhereKeepsBothTokens(t *testing.T) {
	// judgeModel "tier-standard": judge-token audience ...tier-standard and light-token audience ...tier-light
}

func TestConfigRefusesALightAliasItsListenerDoesNotServe(t *testing.T) {
	// aliases.internal: [agent-default]; want LoadConfig error containing
	// `model.gateway.lightAlias tier-light is not served on the internal listener (maku-gateway aliases.internal)`
}

func TestSecretModeLightFallsBackToThePodsModel(t *testing.T) { /* LIGHT_BASE_URL == BaseURL, LIGHT_MODEL == judge_model or model, no key file */ }
```

Use the real `modelDir` constant and the fixture's gateway host in `want`.

- [ ] **Step 2: Run and see them fail**

Run: `go test ./internal/runctl/ -run 'Light' -count=1`
Expected: FAIL, undefined `lightOn`.

- [ ] **Step 3: Implement**

`model()` validates the alias with `aliasRE` and requires it in every non-empty alias list. `GatewayModel` fills `Light` and `LightBaseURL` when `lightOn(r)`. `Pod` appends the env by the table. `modelVolumeSource` adds the `light-token` projection only in the second row of the table. The secret-mode branch mirrors the judge's.

- [ ] **Step 4: Update the golden files and the chart**

Run: `go test ./internal/runctl/ -run 'Golden' -update` (`render_test.go`'s flag), then add `lightAlias` to the chart's values, schema and config template, an assertion in `charts/maku/tests/render.sh` that the rendered config carries `lightAlias: tier-light`, and run `task install:schemas`.

- [ ] **Step 5: Run**

Run: `task check`
Expected: exit 0. Review the golden diff: only internal or search-on runs change.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(runctl): every run that can use it gets the light alias, on the judge's audience"
```

### Task 7: the blobless clone (CP5)

**Files:**
- Modify: `images/maku-harness/agent_run.py` (`clone`)
- Test: `images/maku-harness/tests/test_agent_run.py`

**Interfaces:**
- Consumes: Task 1's `clone(env, start_span=None)` and its `filter` attribute.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_clone_is_blobless(self):
    with fake_git() as git:
        agent_run.clone(ENV)
    self.assertEqual(git.calls[0][:4], ["git", "clone", "--no-tags", "--filter=blob:none"])

def test_a_forge_that_refuses_the_filter_gets_a_full_clone(self):
    spans = FakeSpans()
    with fake_git(filter_refused=True) as git:
        agent_run.clone(ENV, start_span=spans.start)
    self.assertEqual(git.calls[1][:3], ["git", "clone", "--no-tags"])
    self.assertNotIn("--filter=blob:none", git.calls[1])
    self.assertEqual(spans.ended[0][1]["filter"], "none")

def test_a_clone_that_fails_twice_fails_the_run(self):
    with fake_git(clone_fails=True), self.assertRaises(subprocess.CalledProcessError):
        agent_run.clone(ENV)
```

- [ ] **Step 2: Run and see them fail**

Expected: FAIL, the first call has no `--filter`.

- [ ] **Step 3: Implement**

Try the filtered clone; on a non-zero exit remove the partial `REPO_DIR` and clone in full. The span's `filter` is `blob:none` or `none`. No `--depth`: a shallow clone breaks `merge-base` on an old base.

- [ ] **Step 4: Run the suite, then the gVisor check**

Run: `docker build --target test images/maku-harness`, then let CI's `harness-checks` job run on the pull request.
Expected: PASS; `harness-checks` proves the declared checks still run on a blobless clone behind the egress proxy.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): blobless clone, with a full clone when the forge refuses the filter"
```

### Task 8: the condenser on internal runs (CP6)

**Files:**
- Modify: `images/maku-harness/agent_run.py` (`build_request` at :343, the redaction tuple at :178)
- Test: `images/maku-harness/tests/test_prompt_cache.py`, `images/maku-harness/tests/golden/start-request.json` (unchanged), new `images/maku-harness/tests/golden/start-request-internal.json`

**Interfaces:**
- Consumes: `LIGHT_BASE_URL`, `LIGHT_MODEL`, `LIGHT_API_KEY_FILE` (Task 6).
- Produces: `CONDENSER_MAX_SIZE = 240`, `CONDENSER_KEEP_FIRST = 8`, `CONDENSER_EFFORT = "low"`; `light_llm(env: dict, usage_id: str, effort: str)` returning an SDK `LLM` or `None` when `LIGHT_BASE_URL` is unset. Task 9 does not import it (the search module builds its own).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_public_request_is_todays(self):
    self.assertEqual(build(PUBLIC_ENV), golden("start-request.json"))

def test_an_internal_run_condenses_later_and_on_the_light_alias(self):
    c = build(INTERNAL_ENV | LIGHT_ENV)["agent"]["condenser"]
    self.assertEqual((c["max_size"], c["keep_first"]), (240, 8))
    self.assertEqual(c["llm"]["model"], "openai/tier-light")
    self.assertEqual(c["llm"]["base_url"], LIGHT_ENV["LIGHT_BASE_URL"])
    self.assertEqual(c["llm"]["litellm_extra_body"], {"reasoning_effort": "low"})

def test_an_internal_run_without_a_light_alias_keeps_the_summary_on_its_own_model(self):
    c = build(INTERNAL_ENV)["agent"]["condenser"]
    self.assertEqual((c["max_size"], c["keep_first"]), (240, 8))
    self.assertEqual(c["llm"]["model"], "openai/" + INTERNAL_ENV["MODEL"])

def test_the_light_key_is_redacted(self):
    self.assertNotIn(LIGHT_KEY, agent_run.redact("x " + LIGHT_KEY))
```

- [ ] **Step 2: Run and see them fail**

Expected: FAIL, `max_size` is 80.

- [ ] **Step 3: Implement**

For `DATA_CLASS == "internal"` only, replace the default agent's condenser fields. If the SDK's validator at 1.56.0 refuses 240 or 8, lower each to its bound, change the two constants and say so in the pull request; the tests read the constants. The summary LLM keeps `num_retries=0` and the run's prices are not applied to it (the meter prices by served model).

- [ ] **Step 4: Run, write the new golden file, run again**

Expected: PASS; `start-request.json` has no diff.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): internal runs condense later, and summarise on the light alias (C4)"
```

### Task 9: the search child on the light alias (CP7)

**Files:**
- Modify: `images/maku-harness/site/agent_search.py` (`child_agent` at :251)
- Test: `images/maku-harness/tests/test_agent_search.py` (replace `test_the_child_runs_at_low_effort_on_the_runs_model_and_base` at :146)

**Interfaces:**
- Consumes: the three `LIGHT_*` variables. Signature becomes `child_agent(parent_llm, env=os.environ) -> Agent`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_child_runs_at_low_effort_on_the_light_alias(self):
    llm = child_agent(PARENT, env=LIGHT_ENV).llm
    self.assertEqual((llm.model, llm.base_url), ("openai/tier-light", LIGHT_ENV["LIGHT_BASE_URL"]))
    self.assertEqual(llm.litellm_extra_body["reasoning_effort"], "low")
    self.assertEqual(llm.usage_id, "search")

def test_without_a_light_alias_the_child_keeps_the_parents_model(self):
    llm = child_agent(PARENT, env={}).llm
    self.assertEqual((llm.model, llm.base_url), (PARENT.model, PARENT.base_url))

def test_the_child_reads_the_light_token_not_the_parents(self):
    llm = child_agent(PARENT, env=LIGHT_ENV | {"LIGHT_API_KEY_FILE": token_file("light")}).llm
    self.assertEqual(llm.api_key.get_secret_value(), "light")
```

- [ ] **Step 2: Run and see them fail**

Expected: FAIL, the model is the parent's.

- [ ] **Step 3: Implement**

`model_copy` additionally updates `model`, `base_url` and `api_key` when `LIGHT_BASE_URL` is set. The ledger row's `model` field, if it has one, records the model the child used.

- [ ] **Step 4: Run**

Expected: PASS, `test_search_agent_server.py` included.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): the search child runs on the light alias"
```

### Task 10: the reader pages

**Files:**
- Modify: `docs/install.md` (section "Sandbox nodes", :181), `docs/observability.md`, `docs/gateway.md`, `images/maku-harness/README.md`
- Test: `task docs`

- [ ] **Step 1: Write the four changes**

| Page | Change |
|---|---|
| `docs/install.md` | One paragraph: a cold sandbox node costs 1.5 to 3.5 minutes at start; a low-priority placeholder pod with the run images keeps one warm; the nodes are yours, so the chart ships none. |
| `docs/observability.md` | The two spans, the two log lines with the five `miss` values (only `unexpected` is a defect), `agent_factory_run_wait_seconds`, the three panels. |
| `docs/gateway.md` | `lightAlias`: which runs hold a light-alias token and why. |
| `images/maku-harness/README.md` | `LIGHT_*`, the blobless clone and its fall back, the internal condenser. |

- [ ] **Step 2: Run**

Run: `task docs`
Expected: exit 0.

- [ ] **Step 3: Commit, then cut release N**

```bash
git commit -am "docs: the start row, the cache lines, the light alias and warm nodes"
```

---

## Lot 3: effort and model per role (release N+1)

**Gate:** start only when (a) the workflows plan has landed `Factory.spec.workflows` and re-keyed `loops` by workflow, and (b) the workflows measurement has kept the role a trial tunes. Until then these tasks stay unchecked.

### Task 11: `effort` and `models` on a workflow definition (CP9, CP10)

**Files:**
- Modify: `internal/factory/config/config.go` (the workflow type the workflows plan adds; `ModelFor` at :2384), `api/factory/v1alpha1/factoryconfig_types.go`
- Test: `internal/factory/config/config_test.go`, `api/factory/v1alpha1/factoryconfig_crd_test.go`

**Interfaces:**
- Consumes: the workflows plan's `Workflow` type and its lookup by name.
- Produces: `Workflow.Effort map[string]string` (role → `low|medium|high`), `Workflow.Models map[string]ModelAlias` (role → alias); `func (c *Config) EffortFor(workflow, role string) string` (`""` means the harness default, `high`); `func (c *Config) ModelFor(workflow, dataClass, role, tier string) string`.

- [ ] **Step 1: Write the failing tests**

```go
func TestEffortForDefaultsToEmpty(t *testing.T)            { /* no effort row: "" */ }
func TestEffortForReadsTheRole(t *testing.T)               { /* effort: {reviewer: medium}: "medium"; implementer: "" */ }
func TestEffortRefusesAnUnknownValueOrRole(t *testing.T)   { /* "max", role "merger": load error naming the workflow and the key */ }
func TestModelForOnAnInternalTaskHonoursTierAliasesOnly(t *testing.T) {
	// models: {reviewer: tier-standard}, internal: "tier-standard"
	// models: {reviewer: kimi-frontier}, internal: load error
	//   `workflows.standard.models.reviewer kimi-frontier: an internal task takes tier-light, tier-standard or tier-frontier`
	// models: {reviewer: kimi-frontier}, public: "kimi-frontier"
}
func TestTheImplementersEffortAndModelAreNotSettable(t *testing.T) { /* effort or models naming implementer: load error */ }
```

- [ ] **Step 2: Run and see them fail**

Run: `go test ./internal/factory/config/ -run 'EffortFor|ModelFor|Implementers' -count=1`
Expected: FAIL, undefined `EffortFor`.

- [ ] **Step 3: Implement**

A workflow that serves both data classes and names a non-tier alias is valid for public tasks and returns `""` for internal ones only if the config says so explicitly; by default it is the load error above, so a misrouted internal call cannot be configured by accident.

- [ ] **Step 4: Regenerate and run**

Run: `task crd:gen && task check`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(factory): effort and models per role on a workflow definition"
```

### Task 12: the effort reaches the pod

**Files:**
- Modify: `api/v1alpha1` (the AgentRun spec type), `internal/factory/reconciler/implement.go` (the two launch sites), `internal/runctl/pod.go` (env at :120)
- Test: `internal/runctl/render_test.go`, `internal/factory/reconciler/outcomes_test.go`, `internal/runctl/testdata/*.golden.yaml`

**Interfaces:**
- Consumes: `EffortFor` (Task 11).
- Produces: `AgentRun.spec.effort` (enum `low|medium|high`, optional); pod env `LLM_REASONING_EFFORT` set only when the field is.

- [ ] **Step 1: Write the failing tests**

```go
func TestARunWithAnEffortSetsTheHarnessVariable(t *testing.T) { /* spec.effort "medium": LLM_REASONING_EFFORT=medium */ }
func TestARunWithoutAnEffortSetsNone(t *testing.T)           { /* variable absent: golden files unchanged */ }
func TestTheFactoryWritesTheWorkflowsEffortOnTheRun(t *testing.T) { /* workflow standard, effort {reviewer: medium}: the reviewer's AgentRun has spec.effort medium; the implementer's has none */ }
```

- [ ] **Step 2: Run and see them fail**, **Step 3: implement**, **Step 4:** `task crd:gen && task check`, exit 0.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: a workflow's effort reaches the run's harness"
```

### Task 13: ship a trial's winner

Repeated once per trial, in the spec's order (scoper effort, reviewer effort, reviewer model, triager effort, triager model). Each needs the workflows measurement's verdict, read on aws-0 by the adoption plan.

**Files:**
- Modify: the chart's shipped workflow definitions (the file the workflows plan names), `docs/observability.md` (the trial's result, one row)
- Test: the chart's render test for the shipped workflows

- [ ] **Step 1:** Read the verdict from ai-native-ref's results file for the trial. Indecisive, or fewer than 30 tasks an arm: stop, the default does not change.
- [ ] **Step 2:** Write the failing render assertion: the shipped workflow carries the winning field, for example `workflows.standard.effort.reviewer == "medium"`.
- [ ] **Step 3:** Change the shipped default; run `task chart:check`, exit 0.
- [ ] **Step 4:** Commit with the figures in the message body: `feat(chart): the reviewer runs at effort medium (trial 2: <cost per merged PR>, <merge rate>, n=<n> an arm)`.

---

## Self-review

| Spec item | Task |
|---|---|
| CP1 spans, wait between runs | 1, 3, 5 |
| CP2 cache and condensation lines | 2 |
| CP3 cost per merged pull request, counters widened | 4, 5 |
| CP4 warm node | 10 (one paragraph); the rest is the adoption plan |
| CP5 blobless clone | 7 |
| CP6 condenser | 8 |
| CP7 search on the light alias | 9 |
| CP12 light alias on the run | 6 |
| CP8 no toolchain cache | nothing built; Task 1 keeps `agent-run.checks.install` readable beside the start row |
| CP9, CP10 effort and model per role | 11, 12 |
| CP13 trials | 13, with the adoption plan |
| CP14 before v4.0.0 | lots 1 and 2 in N, lot 3 in N+1 |
| CP11 out of scope | not built |
