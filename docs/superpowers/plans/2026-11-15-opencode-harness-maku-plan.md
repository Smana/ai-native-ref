# OpenCode Second Harness: Maku Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in OpenCode 2.3.0 inner loop for every AgentRun role while preserving OpenHands, room semantics, recovery, provider behavior, and truthful A/B and rescue accounting.

**Architecture:** A shared Python `agent-run` uses harness drivers, and the shared Go room bridge uses harness adapters. `AgentRun.spec.harness` selects the driver and image. Factory triage freezes one harness per task; `evaluation.treatmentHarness` varies only that dimension, and an explicit rescue starts a new `rescue` cohort after recording the failed arm.

**Tech Stack:** Python 3 and `unittest`, Go and `testing`, OpenCode 2.3.0 HTTP/SSE API, OpenHands agent-server 1.56.0, Docker, Kubernetes CRDs, Helm, OpenTelemetry, envtest, gVisor.

**Spec:** `docs/superpowers/specs/2026-11-15-opencode-harness-design.md` and its research companion in ai-native-ref. Copy both beside this plan when it moves to Maku.

## Global Constraints

- Execute in Maku, in a worktree branched from `origin/main`. Paths below are Maku's. Rebase before every push.
- Run `task check` before every commit. Run image tests with `docker build --target test images/maku-harness` and `docker build --target test -f images/maku-opencode/Dockerfile .` as applicable.
- Keep OpenHands as the default. Existing claims, pod goldens, and OpenHands behavior change only where a new optional field is present.
- Pin OpenCode to v2.3.0 (`a6b15d33`) and image digest `sha256:998e3e184c650e603d8bacb5cbeaeb090837078262c25521a7136b0375d2b652`. Server, generated client, config, and event schema move only together.
- No secret on argv or in `opencode.jsonc`; no personal config or unapproved plugin; no runtime provider download or auto-update.
- No automatic mid-task harness switch and no mixed-harness roles. `harness` labels are maintainer-only.
- Do not set OpenCode's native OTLP endpoint. Runner-generated spans are metadata only.
- Browser support and Go/Rust runner rewrites are outside this plan.
- Live work does not start here. The ANR plan owns infrastructure authorization, provider smoke tests, A/B tasks, cutover, and soak.
- Commits are conventional, in English, with no trailers.

## Prerequisites

1. Read the complete design. Re-read these interfaces on the implementation day's `origin/main` and reconcile renames without weakening the design's behavior.
2. The workflows N+1 migration and current cache/cost trials are complete, so no other experiment changes role, model, effort, or cohort during the harness comparison.
3. Record the implementation's target Maku minor in the PR. Do not call it Maku v5; v5.x is the ANR programme.
4. Use a fresh worktree and `mise trust`; Docker is running for testcontainers and image suites.

## File Map

- `internal/bridge/`: consumer interface, OpenCode API adapter, normalization, loop status, and tests.
- `images/maku-harness/`: shared runner, OpenHands driver, normalized event types, loop guard, search, and tracing.
- `images/maku-opencode/`: pinned production/test image, OpenCode driver, role config, MCP proxy, and real-server tests.
- `api/v1alpha1/` and `api/factory/v1alpha1/`: harness, provenance, intake, cohort, and outcome schemas.
- `internal/runctl/`: image/probe selection and `AGENT_HARNESS` wiring.
- `internal/factory/`: selection, intake, claims, evaluation, rescue, and metrics.
- `charts/`: CRD copies, image values, admission repository, release assets.
- `docs/` and `images/maku-opencode/README.md`: operator contract and offline evidence.

---

### Task 1: Put the room bridge behind a behavior-preserving `HarnessAPI`

**Files:**
- Modify: `internal/bridge/harness.go`, `internal/bridge/bridge.go`, `internal/app/bridge.go`
- Test: `internal/bridge/harness_test.go`, `internal/bridge/bridge_test.go`, `internal/app/bridge_test.go`

**Interfaces:**
- Produces: `type HarnessAPI interface`, implemented by existing `*Harness`; `Bridge.Harness HarnessAPI`; `func NewHarnessForKind(kind, base, conversationID string) (HarnessAPI, error)`. Only `openhands` is admitted in this task.

- [ ] **Step 1: Write failing compile-time and selection tests**

```go
var _ HarnessAPI = (*Harness)(nil)

func TestHarnessKindDefaultsToOpenHands(t *testing.T) {
    got, err := NewHarnessForKind("", "http://127.0.0.1:1", "c1")
    if err != nil || got == nil { t.Fatalf("got %T, %v", got, err) }
}
func TestHarnessKindRejectsUnknown(t *testing.T) {
    _, err := NewHarnessForKind("other", "http://127.0.0.1:1", "c1")
    if err == nil || !strings.Contains(err.Error(), `harness "other"`) { t.Fatalf("%v", err) }
}
```

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/bridge/ ./internal/app/ -run 'HarnessKind|HarnessAPI' -count=1`
Expected: FAIL, undefined `HarnessAPI` and `NewHarnessForKind`.

- [ ] **Step 3: Extract the interface without changing behavior**

Declare every method `Bridge` already calls: `Ready`, `Conversation`, `Next`, `Skip`, `Send`, `Message`, `Respond`, `Run`, `Interrupt`, and `AlwaysConfirm`. Keep `Harness.next`, used internally by `Bridge`, in the interface as `Next` and add an unexported `next` only if the concrete bridge still needs the end-of-log signal; do not weaken replay semantics to simplify the interface. `NewHarnessForKind` returns `NewHarness` for empty or `openhands`.

- [ ] **Step 4: Run regression suites and the full gate**

Run: `go test ./internal/bridge/ ./internal/app/ -count=1 && task check`
Expected: PASS; no golden or behavior diff.

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor(bridge): the harness client becomes an interface"
```

### Task 2: Split the Python runner into shared lifecycle and an OpenHands driver

**Files:**
- Create: `images/maku-harness/harness_driver.py`, `images/maku-harness/openhands_driver.py`, `images/maku-harness/harness_types.py`, `images/maku-harness/tests/test_driver_selection.py`
- Modify: `images/maku-harness/agent_run.py`, `images/maku-harness/Dockerfile`
- Test: existing `images/maku-harness/tests/`

**Interfaces:**
- Produces: `ConversationRequest`, `EventPage`, and `HarnessDriver` exactly as specified in design §6.1; `driver_for(env) -> HarnessDriver`. `openhands` and empty select the existing driver.

- [ ] **Step 1: Write the selection and compatibility tests**

```python
class DriverSelectionTest(unittest.TestCase):
    def test_default_is_openhands(self):
        self.assertIsInstance(agent_run.driver_for({}), openhands_driver.OpenHandsDriver)
    def test_unknown_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'AGENT_HARNESS "other"'):
            agent_run.driver_for({"AGENT_HARNESS": "other"})
```

Add a golden assertion that `build_request` still produces the existing public and internal request JSON.

- [ ] **Step 2: Run and see the failure**

Run: `docker build --target test images/maku-harness`
Expected: FAIL, no `harness_driver` module.

- [ ] **Step 3: Move only OpenHands-specific code**

Move `SERVER_CMD`, agent-server start/wait/poll/event/message/interrupt/close operations, SDK request construction, and SDK-specific condenser handling into `openhands_driver.py`. `agent_run.main` obtains `driver = driver_for(env)` and calls it. Keep `ask_judge` outside the driver: the judge is Maku's stateless model call. Existing `sitecustomize.py` remains OpenHands-only and is not loaded by OpenCode.

- [ ] **Step 4: Run every existing harness test and the repository gate**

Run: `docker build --target test images/maku-harness && task check`
Expected: PASS, including request goldens, loop, search, checks, contract, resume, and tracing suites.

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor(harness): the OpenHands loop becomes a driver"
```

### Task 3: Build the pinned Maku OpenCode image and boot its real server

**Files:**
- Create: `images/maku-opencode/Dockerfile`, `images/maku-opencode/opencode_driver.py`, `images/maku-opencode/config.py`, `images/maku-opencode/requirements.in`, `images/maku-opencode/requirements.txt`, `images/maku-opencode/tests/test_boot.py`, `images/maku-opencode/README.md`
- Modify: `.github/workflows/ci.yaml`, `taskfile.yaml`, `hack/ci-changes.sh`, release image wiring

**Interfaces:**
- Consumes: Task 2's `HarnessDriver` and shared runner files.
- Produces: image `ghcr.io/smana/maku-opencode`; `OpenCodeDriver.start()` and `.wait_ready()` against `opencode serve --hostname 127.0.0.1 --port 8000`; `/global/health` readiness.

- [ ] **Step 1: Write the real boot test**

```python
class BootTest(unittest.TestCase):
    def test_real_server_becomes_ready_and_stops(self):
        d = opencode_driver.OpenCodeDriver(test_env())
        d.start()
        try:
            d.wait_ready()
            self.assertEqual(request_json("http://127.0.0.1:8000/global/health")["healthy"], True)
        finally:
            d.stop()
        self.assertRaises(OSError, request_json, "http://127.0.0.1:8000/global/health")
```

- [ ] **Step 2: Build and see the failure**

Run: `docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: FAIL, missing driver and server command.

- [ ] **Step 3: Implement the image and boot path**

Use `ghcr.io/anomalyco/opencode:2.3.0@sha256:998e…b652` (Alpine). Add only required packages with `apk`: Python, pip, git, rsync, ripgrep, CA certificates, and tini. Reuse the current checksum-pinned `gh` and `mise` versions and `fetch_release.py`. Copy shared runner modules from `images/maku-harness/` using repository-root build context. Install only the OpenCode driver's locked OTel/YAML requirements, not OpenHands packages. Verify those locked dependencies have both amd64 and arm64 musl-compatible wheels; if one is unavailable, use the checksum-pinned glibc OpenCode standalone binary on a Debian base instead of adding a compiler or weakening the lock. Create UID 10001, remove setuid/setgid bits and sudo, and use `ENTRYPOINT ["tini", "--", "/usr/local/bin/agent-run"]`.

Set `HOME=/workspace/.opencode/home`, `OPENCODE_CONFIG_DIR=/workspace/.opencode/config`, and `OPENCODE_DISABLE_CLAUDE_CODE=1`. `start()` launches the server with stdout/stderr inherited and no secret on argv. `wait_ready()` polls `/global/health` for 120 seconds and fails immediately if the process exits.

Add `harness:opencode:test` and CI build/release entries for `maku-opencode`, including the new test stage.

- [ ] **Step 4: Run real boot tests and record the image evidence**

Run: `docker build --target test -f images/maku-opencode/Dockerfile . && docker image inspect "$(docker build -q -f images/maku-opencode/Dockerfile .)" --format '{{.Size}}'`
Expected: PASS and a recorded final-image byte count in the PR. Also run `task check`.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): a pinned non-root OpenCode runner image"
```

### Task 4: Normalize OpenCode events with replay and idempotent room mapping

**Files:**
- Create: `internal/bridge/opencode.go`, `internal/bridge/opencode_mapping.go`, `internal/bridge/opencode_test.go`, `internal/bridge/testdata/opencode-*.json`
- Modify: `internal/bridge/mapping.go`, `internal/app/bridge.go`, `internal/bridge/fakeserver_test.go`

**Interfaces:**
- Consumes: Task 1's `HarnessAPI`, Task 3's session-ID file.
- Produces: `NewOpenCodeHarness(base, sessionFile string) HarnessAPI`; normalized OpenCode `MessageEvent`, `ActionEvent`, `ObservationEvent`, and error events consumed by existing `Map`; replay from `/session/:id/message` with live `/event` reconciliation.

- [ ] **Step 1: Write fixtures for text, tools, errors, duplicates, unknowns, and replay**

```go
func TestOpenCodeToolMapsToTheExistingRoomShape(t *testing.T) {
    events := readFixture(t, "opencode-tool.json")
    got := Map(normalizeOpenCode(events[0]), "run-1")[0]
    var p envelope.ToolCallPayload
    _ = json.Unmarshal(got.Payload, &p)
    if p.CallID != "call-1" || p.Tool != "shell" || p.Class != "write" { t.Fatalf("%+v", p) }
}
func TestReplaySkipsExactlyTheAcknowledgedDurableEvent(t *testing.T) { /* cursor at evt-2: evt-3 and evt-4 only */ }
func TestUnknownAndMalformedEventsStayBounded(t *testing.T) { /* harness_event, no payload text */ }
```

Include tool input and output larger than `envelope.MaxPayload`, a missing `durable.seq`, and the same message observed on SSE and replay.

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/bridge/ -run 'OpenCode|Replay' -count=1`
Expected: FAIL, undefined normalization and adapter.

- [ ] **Step 3: Implement normalization and replay**

Generate the client from OpenCode 2.3.0's `/doc` and vendor only the generated operations used by the adapter. Translate events into the existing `RawEvent` shape so truncation, redaction, and `ItemsPerEvent` sequencing stay shared. Preserve provider call IDs, tool names, content, execution errors, token usage, and timestamps. Unknown events map to `harness_event` with the kind only.

The session-ID file is read with a bounded size and validated as `ses_[A-Za-z0-9_-]+`. A missing file means not ready. Replay starts at the last acknowledged durable event; SSE is reconciled against the message log before cursor advancement. Never acknowledge a page with a missing sequence.

- [ ] **Step 4: Run bridge regressions and full gates**

Run: `go test ./internal/bridge/ ./internal/app/ -count=1 && task check`
Expected: PASS, including OpenHands mapping and cursor tests.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(bridge): replayable OpenCode events in the room protocol"
```

### Task 5: Preserve status, steering, approvals, and final-read semantics

**Files:**
- Modify: `internal/bridge/opencode.go`, `internal/bridge/opencode_mapping.go`, `internal/app/bridge.go`
- Create: `images/maku-opencode/tests/test_control.py`
- Modify: `internal/bridge/opencode_test.go`

**Interfaces:**
- Produces: OpenCode `Conversation`, `Send`, `Message`, `Respond`, `Run`, `Interrupt`, and `AlwaysConfirm`; normalized statuses `idle`, `running`, `paused`, `waiting_for_confirmation`, `finished`, `error`, and `stuck`.

- [ ] **Step 1: Write the behavior tests**

```python
def test_permission_waits_for_maku_decision(self):
    run scripted_model(tool="shell", command="touch /workspace/repo/blocked")
    self.assertEqual(room.wait("waiting_for_confirmation"), True)
    self.assertFalse(os.path.exists("/workspace/repo/blocked"))
    room.decide("reject")
    self.assertEqual(run.status(), "finished")
    self.assertFalse(os.path.exists("/workspace/repo/blocked"))

def test_steering_and_final_read(self):
    run scripted_model(text="working", pause=True)
    driver.send(session_id, "continue with the second fixture")
    self.assertIn("second fixture", room.messages())
    run.finish()
    self.assertEqual(room.last_event_kind(), "harness_end")
```

Add Go tests for `stuck` taking precedence over interrupted, a 409 on resume, and an SSE disconnect during confirmation.

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/bridge/ -run 'OpenCode.*(Status|Permission|Steering|Final)' -count=1` and the new image test.
Expected: FAIL, unimplemented controls.

- [ ] **Step 3: Implement the controls**

`Send` and `Message` use the pinned asynchronous prompt operation; `Respond` answers the permission request once with Maku's decision and resumes only when required. `AlwaysConfirm` verifies the generated base policy asks on every action not explicitly allowed or denied; it does not grant anything. `Interrupt` calls session interrupt and stops every owned shell/subagent job. Status derives from active execution, stored idle outcomes, permission state, and the terminal marker.

`final-read` uses the same shared bridge path and proves the last projected message is mapped before server stop.

- [ ] **Step 4: Run real-server and full regression tests**

Run: `docker build --target test -f images/maku-opencode/Dockerfile . && task check`
Expected: PASS; no approval is auto-accepted or auto-rejected by the adapter itself.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(bridge): OpenCode steering approvals and final reads"
```

### Task 6: Generate role configurations, provider variants, and a rotating-token MCP proxy

**Files:**
- Create: `images/maku-opencode/role_config.py`, `images/maku-opencode/mcp_proxy.py`, `images/maku-opencode/tests/test_role_config.py`, `images/maku-opencode/tests/test_mcp_proxy.py`, `images/maku-opencode/tests/test_provider_contract.py`
- Modify: `images/maku-opencode/config.py`, `images/maku-opencode/opencode_driver.py`, `images/maku-opencode/Dockerfile`

**Interfaces:**
- Produces: `role_config(env) -> dict`; provider `maku`, model variants `low|medium|high`; primary agents `implementer|reviewer|tester|triager|search`; `mcp_proxy` reading `MCP_TOKEN_FILE` on every request.

- [ ] **Step 1: Write role and provider contract tests**

```python
def test_reviewer_cannot_edit_or_launch_subagents(self):
    c = role_config.role_config({"ROLE": "reviewer", "MODEL": "agent-default"})
    perms = c["agents"]["reviewer"]["permissions"]
    self.assertIn({"action": "edit", "resource": "*", "effect": "deny"}, perms)
    self.assertIn({"action": "subagent", "resource": "*", "effect": "deny"}, perms)

def test_effort_is_a_model_variant_not_a_secret(self):
    c = role_config.role_config({"MODEL": "agent-default", "LLM_REASONING_EFFORT": "medium"})
    self.assertEqual(c["model"], "maku/agent-default#medium")
    self.assertNotIn("injected-by-identity-proxy", json.dumps(c))

def test_internal_cache_marker_and_public_omission(self):
    self.assertIn("cacheFormat", role_config.role_config(INTERNAL)["providers"]["maku"]["compatibility"])
    self.assertNotIn("cacheFormat", role_config.role_config(PUBLIC)["providers"]["maku"].get("compatibility", {}))
```

Provider fixtures assert request model, `reasoning_effort`, tool schema, terminal 429 with no retry, transient retry bounds, and usage/cache extraction for GLM, Anthropic, Kimi, and Mistral shapes. MCP tests rotate the token file between two calls and assert only the second bearer changes.

- [ ] **Step 2: Run and see the failure**

Run: `docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: FAIL, missing config and proxy.

- [ ] **Step 3: Implement configuration and proxy**

Generate V2 `providers`, `agents`, and `mcp.servers.platform` with `codemode: false` and `oauth: false`. Deny subagents, skills, web, and external directories by default. Limit each role's edit/shell/MCP rules to its current behavior; tester's edit exceptions come only from the pinned test-contract declaration. Do not load repository or personal plugins.

The runner reads `LLM_API_KEY_FILE` into the child environment only, using the existing placeholder behind identity-proxy. The MCP proxy listens on loopback, bounds requests/responses, forwards only to `MCP_URL`, strips credentials on redirects, and reads `MCP_TOKEN_FILE` for every call. It adds `traceparent` from the run.

- [ ] **Step 4: Run provider fixtures and full gates**

Run: `docker build --target test -f images/maku-opencode/Dockerfile . && task check`
Expected: PASS, including a no-network-at-start test proving no provider package download occurs.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): least-privilege OpenCode roles and provider contracts"
```

### Task 7: Add Maku-owned stuck-loop detection

**Files:**
- Create: `images/maku-harness/loop_guard.py`, `images/maku-harness/tests/test_loop_guard.py`, `images/maku-opencode/tests/test_loop_guard_integration.py`
- Modify: `images/maku-opencode/opencode_driver.py`, `internal/bridge/opencode.go`, `internal/bridge/opencode_test.go`

**Interfaces:**
- Produces: `loop_guard.detect(events) -> str | None` returning `repeated_action`, `repeated_error`, `monologue`, `alternating`, or `context_window`; `/workspace/.agent-opencode-terminal.json` with `{"reason":"stuck","pattern":name}`.

- [ ] **Step 1: Write threshold and integration tests**

```python
class LoopGuardTest(unittest.TestCase):
    def test_three_actions_are_not_a_loop_but_four_are(self):
        pair = {"tool": "shell", "input": {"command": "true"}, "output": "ok"}
        self.assertIsNone(loop_guard.detect([pair] * 3))
        self.assertEqual(loop_guard.detect([pair] * 4), "repeated_action")
    def test_different_file_reads_are_not_identical_actions(self):
        rows = [{"tool": "read", "input": {"path": str(n)}, "output": "ok"} for n in range(10)]
        self.assertIsNone(loop_guard.detect(rows))
```

Add tests for the other four patterns, events after the last user message only, and a real OpenCode session whose repeated calls produce `stuck` in both runner and bridge.

- [ ] **Step 2: Run and see the failure**

Run: `docker build --target test images/maku-harness && docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: FAIL, no detector or marker.

- [ ] **Step 3: Implement detection and terminal mapping**

Compare semantic action input and observation content, excluding IDs, timestamps, and token metrics. Keep only events after the last user message. Write the marker atomically with mode 0600, interrupt the session and all jobs, and make `Conversation` return `stuck` before interrupted or idle. The marker is a terminal reason, not a control: invalid JSON or an unknown pattern means no status change.

- [ ] **Step 4: Run detector and bridge suites plus the full gate**

Run: both image test builds and `task check`.
Expected: PASS; OpenHands loop tests are unchanged.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): Maku-owned stuck detection for OpenCode"
```

### Task 8: Reproduce bounded synchronous search

**Files:**
- Create: `images/maku-opencode/search.py`, `images/maku-opencode/tests/test_search.py`
- Modify: `images/maku-opencode/opencode_driver.py`, `images/maku-harness/agent_run.py`

**Interfaces:**
- Consumes: `LIGHT_BASE_URL`, `LIGHT_MODEL`, `LIGHT_API_KEY_FILE`, `AGENT_SEARCH`, and Task 6's `search` agent.
- Produces: `search(query, env, driver) -> SearchResult`, using an independent session and the existing `/workspace/.agent-search.jsonl` schema.

- [ ] **Step 1: Write search contract tests**

```python
def test_search_is_sync_light_and_bounded(self):
    result = search.search("where is validation?", ENV_WITH_LIGHT, FakeDriver(tokens=400, steps=3))
    self.assertEqual(result.model, "tier-light")
    self.assertEqual(result.effort, "low")
    self.assertEqual(result.tool_calls, 3)
    row = json.loads(pathlib.Path(ENV_WITH_LIGHT["SEARCH_LEDGER"]).read_text().splitlines()[-1])
    self.assertEqual(row["outcome"], "complete")

def test_sixth_call_is_the_last(self):
    driver = FakeDriver(completions=["answer"] * 6)
    for _ in range(6):
        self.assertEqual(search.search("where is validation?", ENV_WITH_LIGHT, driver).outcome, "complete")
    with self.assertRaisesRegex(search.BudgetExceeded, "six search calls"):
        search.search("one lookup too many", ENV_WITH_LIGHT, driver)
    self.assertEqual(driver.sessions_created, 6)

def test_token_ceiling_interrupts_the_child(self):
    driver = FakeDriver(tokens=300_001)
    with self.assertRaisesRegex(search.BudgetExceeded, "300000 tokens"):
        search.search("where is validation?", ENV_WITH_LIGHT, driver)
    self.assertEqual(driver.interrupts, 1)
    row = json.loads(pathlib.Path(ENV_WITH_LIGHT["SEARCH_LEDGER"]).read_text().splitlines()[-1])
    self.assertEqual(row["outcome"], "budget")
```

- [ ] **Step 2: Run and see the failure**

Run: `docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: FAIL, no search module.

- [ ] **Step 3: Implement the bounded child**

Create an independent session with no `parentID`, using `search` agent, light alias when present, low effort, 40 steps, and read-only tools. Wait synchronously for 300 seconds at most. Accumulate usage and interrupt at 300,000 tokens or the step/time/call limit. Truncate the answer to 8,000 characters and preserve `complete`, `budget`, `error`, `interrupted`, and `refused` outcomes in the ledger.

- [ ] **Step 4: Run real child-session tests and full gates**

Run: `docker build --target test -f images/maku-opencode/Dockerfile . && task check`
Expected: PASS; no background subagent remains active and existing search nudge/ledger tests pass.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): bounded synchronous OpenCode search"
```

### Task 9: Prove PVC restoration and the complete 15-second recovery sequence

**Files:**
- Modify: `images/maku-opencode/opencode_driver.py`, `images/maku-harness/agent_run.py`, `internal/bridge/opencode.go`
- Create: `images/maku-opencode/tests/test_recovery.py`, `images/maku-opencode/tests/recovery-runsc.sh`

**Interfaces:**
- Produces: persistent `/workspace/.opencode/` and session-ID restoration; `stop_owned_jobs(sessionID)` used before checkpoint and stop; recovery evidence under runsc.

- [ ] **Step 1: Write recovery tests**

```python
def test_resume_restores_session_and_pending_permission(self):
    first = start_run(suspendable=True, scripted=permission_required())
    session_id = first.session_id
    first.stop_without_decision()
    second = resume_run(suspendable=True, workspace=first.workspace)
    self.assertEqual(second.session_id, session_id)
    self.assertEqual(second.status(), "waiting_for_confirmation")
    second.decide("reject")
    self.assertEqual(second.status(), "finished")

def test_sigterm_checkpoints_stops_jobs_and_revokes_inside_budget(self):
    run = start_run(scripted=long_running_shell_and_uncommitted_edit())
    run.sigterm()
    self.assertTrue(run.checkpoint_commit_exists())
    self.assertTrue(run.final_room_event_exists())
    self.assertTrue(run.git_token_revoked())
    self.assertFalse(run.shell_process_alive())
    self.assertLess(run.shutdown_seconds(), 15)
```

- [ ] **Step 2: Run and see the failure**

Run: `docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: FAIL, lost session, live job, or incomplete final read.

- [ ] **Step 3: Implement restoration and shutdown**

Persist OpenCode config, data, state, and cache under `/workspace/.opencode/`; reuse only the validated session-ID file. Reconcile pending permission state before sending any new prompt. Enumerate session jobs through the pinned experimental job API and stop each shell/subagent before checkpointing. Dispose the session and terminate the process daemon before revocation, killing on the existing independent boxes.

The runsc script repeats both tests with `/workspace` as a mounted volume and records each shutdown step's duration.

- [ ] **Step 4: Run image and runsc recovery suites**

Run: both image builds, `images/maku-opencode/tests/recovery-runsc.sh`, and `task check`.
Expected: PASS; no child process survives, room tail is complete, and each box plus the total stays within the design's bounds.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): OpenCode suspend resume and disruption recovery"
```

### Task 10: Emit correlated metadata-only spans from normalized events

**Files:**
- Create: `images/maku-harness/event_tracing.py`, `images/maku-harness/tests/test_event_tracing.py`, `images/maku-opencode/tests/test_tracing.py`
- Modify: `images/maku-harness/agent_run.py`, `images/maku-opencode/mcp_proxy.py`, `images/maku-opencode/opencode_driver.py`

**Interfaces:**
- Produces: `EventTracer.consume(event)` generating model/tool spans from OpenCode events; no OpenCode native OTLP endpoint; provider/MCP `traceparent` propagation.

- [ ] **Step 1: Write content and correlation tests**

```python
def test_span_has_usage_but_no_content_or_command(self):
    tracer = EventTracer(root)
    tracer.consume(step_finish(tokens={"input": 10, "output": 4, "cache": {"read": 8, "write": 2}}))
    span = tracer.finished[-1]
    self.assertEqual(span.attributes["gen_ai.usage.input_tokens"], 10)
    self.assertEqual(span.attributes["gen_ai.usage.cache_read_input_tokens"], 8)
    for forbidden in ("gen_ai.prompt", "gen_ai.completion", "process.command", "shell.command", "tool.input", "tool.output"):
        self.assertNotIn(forbidden, span.attributes)
```

Also assert a secret planted in text/tool output never appears in span name, attributes, events, status, logs, or exported OTLP logs. Model and MCP fake servers must receive the run's W3C `traceparent`.

- [ ] **Step 2: Run and see the failure**

Run: both image test builds.
Expected: FAIL, missing normalized spans or leaked content.

- [ ] **Step 3: Implement tracing**

Map step start/end, tool start/end, errors, retries, and usage into OTel spans under the run root. Use only the collector's allowlisted attribute names. Do not set `OTEL_EXPORTER_OTLP_ENDPOINT` for the OpenCode server itself. Preserve the existing collector and its fail-closed filtering.

- [ ] **Step 4: Run tracing and full suites**

Run: both image builds and `task check`.
Expected: PASS; model/MCP trace context matches the run and no OTLP log pipeline is opened.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(harness): metadata-only OpenCode model and tool spans"
```

### Task 11: Select the OpenCode image and driver through `AgentRun.spec.harness`

**Files:**
- Modify: `api/v1alpha1/agentrun_types.go`, `internal/runctl/config.go`, `internal/runctl/pod.go`, `charts/maku/values.yaml`, `charts/maku/values.schema.json`, `charts/maku/templates/run-controller-config.yaml`, `charts/maku/templates/run-pod-policy.yaml`, `charts/agent-factory-crds/files/maku.ogenki.io_agentruns.yaml`
- Test: `internal/runctl/render_test.go`, `internal/runctl/config_test.go`, `internal/runctl/testdata/pod-opencode.golden.yaml`, `charts/maku/tests/render.sh`, `charts/maku/tests/admission/runpod_test.go`

**Interfaces:**
- Produces: enum `openhands;opencode`; `Images.Opencode string` (`runController.images.opencode`); `AGENT_HARNESS`; OpenCode `/global/health` probes and image/admission selection.

- [ ] **Step 1: Write render and admission tests**

```go
func TestOpenCodeRunUsesItsOwnImageAndDriver(t *testing.T) {
    r := run("run-abcdefgh", func(r *v1alpha1.AgentRun) { r.Spec.Harness = "opencode" })
    p := Pod(r, testConfig(t), testModel, "abcdefgh")
    if p.Spec.Containers[0].Image != testConfig(t).Images.Opencode { t.Fatal(p.Spec.Containers[0].Image) }
    if got := harnessEnv(p)["AGENT_HARNESS"]; got != "opencode" { t.Fatalf("%q", got) }
    if got := bridgeEnv(p)["AGENT_HARNESS"]; got != "opencode" { t.Fatalf("%q", got) }
}
func TestDefaultRunKeepsTheExistingGolden(t *testing.T) { /* pod.golden.yaml unchanged */ }
```

Admission accepts `ghcr.io/smana/maku-opencode@sha256:…` and rejects a tag or another repository. CRD validation rejects `other` and any harness mutation.

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/runctl/ -run 'OpenCode|DefaultRun|Harness' -count=1`
Expected: FAIL, no enum/image selection.

- [ ] **Step 3: Implement the API and pod wiring**

Add `opencode` to the existing enum, `Images.Opencode`, strict config validation, chart values/schema/template, and admission repository. `Pod` selects image and probe paths by harness and passes `AGENT_HARNESS` to both containers. Empty remains OpenHands and produces no changed env or golden. Regenerate CRDs and chart copies.

- [ ] **Step 4: Run generation and full gates**

Run: `task crd:gen && task install:schemas && task chart:check && task check`
Expected: exit 0; only the new OpenCode golden differs from existing pod shapes.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(runctl): AgentRun selects OpenCode or OpenHands"
```

### Task 12: Freeze task selection, intake, claims, and run provenance

**Files:**
- Modify: `internal/factory/config/config.go`, `internal/factory/config/evaluation.go`, `internal/factory/triage/classify.go`, `internal/factory/triage/workflow.go`, `internal/factory/runs/runs.go`, `internal/factory/reconciler/implement.go`, `internal/factory/reconciler/profile.go`, `internal/factory/api/server.go`, `api/factory/v1alpha1/task_types.go`, `api/factory/v1alpha1/factoryconfig_types.go`
- Test: `internal/factory/config/*_test.go`, `internal/factory/triage/*_test.go`, `internal/factory/reconciler/pin_test.go`, `internal/factory/reconciler/profile_resolve_test.go`, `internal/factory/runs/runs_test.go`, `internal/factory/api/server_test.go`

**Interfaces:**
- Produces: `Defaults.Harness`, `Evaluation.TreatmentHarness`, `TaskIntake.Harness`, `RunRequest.Harness`, `ProfileStatus.Harness`, `.HarnessSource`, `.Cohort=rescue`, `runs.Spec.Harness`, and `RunProvenance.Harness`.

- [ ] **Step 1: Write selection and propagation tests**

```go
func TestHarnessSelectionPrecedence(t *testing.T) {
    // label > treatmentHarness > defaults.harness > openhands
}
func TestEveryRoleGetsTheFrozenHarness(t *testing.T) {
    // triage treatmentHarness=opencode, workflow standard; scoper, implementer and reviewer claims
    // all carry spec.harness=opencode and RunProvenance.Harness=opencode.
}
func TestHarnessLabelNeedsAMaintainer(t *testing.T) {
    // non-maintainer's harness:opencode is narrated/refused and the task uses the default
}
func TestTreatmentHarnessDoesNotChangeWorkflow(t *testing.T) {
    // treatment has same template, loop, checks, model, effort and tier as control
}
```

Add strict config tests for an invalid value, `TaskIntake` and `POST /v1/runs` accepted values, and a no-model integration run forced to OpenHands.

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/factory/... -run 'Harness|TreatmentHarness|EveryRole' -count=1`
Expected: FAIL, missing fields and resolver.

- [ ] **Step 3: Implement selection and provenance**

Validate both values everywhere. `HarnessFor` applies label → treatment harness → configured default → `openhands`; a label is `labeled`, treatment is `treatment`, rescue is assigned only by Task 13. `startRun` copies the frozen value into `runs.Spec.Harness` and each new `RunProvenance`. `Build` writes `spec.harness` only when non-empty, preserving old claim fixtures. `recordExisting` reads the harness from the claim rather than re-resolving it, and `RunProvenance.IsZero` includes `Harness`. Integration-only paths force OpenHands.

Extend the intake label reader with the same actor attribution and conflict rules as workflows. `RunRequest.Harness` remains a one-off selection and cannot change an existing task.

- [ ] **Step 4: Regenerate and run all factory tests**

Run: `task crd:gen && go test ./internal/factory/... -count=1 && task check`
Expected: PASS, including existing workflow and pin behavior.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(factory): a frozen harness per task and every run"
```

### Task 13: Record the failed arm before an explicit OpenHands rescue

**Files:**
- Modify: `api/factory/v1alpha1/task_types.go`, `internal/factory/reconciler/watch.go`, `internal/factory/reconciler/outcome.go`, `internal/factory/reconciler/profile.go`, `internal/factory/fmetrics/fmetrics.go`, `internal/factory/meter/meter.go`
- Test: `internal/factory/reconciler/watch_test.go`, `internal/factory/reconciler/outcome_test.go`, `internal/factory/fmetrics/fmetrics_test.go`, `internal/factory/meter/*_test.go`

**Interfaces:**
- Produces: `CohortRescue = "rescue"`; `OutcomeCountedCohorts []string`; strict `/factory retry harness=openhands`; `harness` on `TaskOutcome`, `TaskUSD`, and `RunCost`.

- [ ] **Step 1: Write rescue and metric tests**

```go
func TestRescueCountsFailureOnceAndKeepsRescueOutsideTheTrial(t *testing.T) {
    tk := escalatedTaskWithHarness("opencode", "treatment")
    retryWithHarness(tk, "smana", "openhands")
    got := reconcileOnce(tk)
    if got.Status.Profile.Cohort != "rescue" || got.Status.Profile.Harness != "openhands" || got.Status.Profile.HarnessSource != "rescue" {
        t.Fatalf("%+v", got.Status.Profile)
    }
    assertMetricOnce(t, "task_outcome", "cohort=treatment", "harness=opencode", "outcome=failed")
    got = finishRescue(got)
    assertMetricOnce(t, "task_outcome", "cohort=rescue", "harness=openhands", "outcome=accepted")
    assertNoMetric(t, "cohort=treatment", "outcome=accepted")
}

func TestCrashBetweenOriginalCountAndRescueCannotDoubleCount(t *testing.T) { /* OutcomeCountedCohorts contains treatment */ }
func TestPlainRetryKeepsItsCohortAndHarness(t *testing.T)                  { /* /factory retry unchanged */ }
```

Metric tests bound `harness` to two values, add it without renaming existing labels, and verify rescue spend never appears in control/treatment queries.

- [ ] **Step 2: Run and see the failure**

Run: `go test ./internal/factory/reconciler/ ./internal/factory/fmetrics/ ./internal/factory/meter/ -run 'Rescue|Harness|OutcomeCountedCohorts' -count=1`
Expected: FAIL, no rescue cohort or harness label.

- [ ] **Step 3: Implement the rescue transaction and metrics**

Accept only the exact maintainer command `/factory retry harness=openhands` on an escalated OpenCode task. Before queueing, count the original attempt as `failed` with its current cohort/harness/cost/duration and append its cohort to `OutcomeCountedCohorts`. Preserve workflow, branch, and room, then set harness/source/cohort to `openhands/rescue/rescue` and `Counted=false`. A replay checks the list before counting either cohort. `/factory retry` alone is unchanged and never changes harness.

Thread `harness` through outcome, USD, and run-cost calls with `oneOf(harness, []string{"openhands", "opencode"})`. Update dashboard queries in the same repository to group trial results by cohort and harness.

- [ ] **Step 4: Regenerate and run the full gate**

Run: `task crd:gen && task check`
Expected: exit 0; original failure and rescue each count once, only under their own cohorts.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(factory): explicit OpenHands rescue with truthful trial accounting"
```

### Task 14: Complete the offline evidence matrix and release the opt-in feature

**Files:**
- Create: `images/maku-opencode/tests/contract-matrix.py`, `images/maku-opencode/tests/runsc-contract.sh`, `docs/opencode-harness.md`
- Modify: `docs/integration.md`, `docs/factory.md`, `docs/api.md`, `docs/upgrading.md`, `docs/observability.md`, `AGENTS.md`, `images/maku-opencode/README.md`, `.github/workflows/ci.yaml`
- Test: all suites above, `task check`, both image test stages, runsc contract

**Interfaces:**
- Produces: repeatable offline parity evidence and an opt-in Maku release with `defaults.harness` absent (OpenHands).

- [ ] **Step 1: Encode the full matrix in one test entrypoint**

```python
ROLES = ["implementer", "reviewer", "tester", "triager"]
PROVIDERS = ["glm", "anthropic", "kimi", "mistral"]
REQUIRED = [
    "tools", "permissions", "steering", "replay", "stuck", "search",
    "cache", "retry", "resume", "checkpoint", "final_read", "tracing",
]
```

The matrix runs every role against scripted tools and every provider shape, plus a real no-model integration run. It fails on any skipped case; output lists each case and its real server/container evidence.

- [ ] **Step 2: Run the matrix and fix every missing case**

Run: `python3 images/maku-opencode/tests/contract-matrix.py`
Expected: FAIL until all required cases execute. Do not mark a case covered by mocks alone: tools, server lifecycle, event replay, and shutdown must use the real OpenCode binary.

- [ ] **Step 3: Run runsc and all repository gates, then document the contract**

Run: `images/maku-opencode/tests/runsc-contract.sh && task check && docker build --target test images/maku-harness && docker build --target test -f images/maku-opencode/Dockerfile .`
Expected: exit 0. Record final image sizes, ordinary-Docker and runsc readiness distributions, and any remaining limitation. A limitation affecting parity blocks release rather than being documented as accepted.

`docs/opencode-harness.md` documents opt-in only, task label, API field, cohort setting, rescue command, provider config, rollback, and evidence commands. Update `AGENTS.md`'s package map and seam description for the second adapter.

- [ ] **Step 4: Verify the release contains no default change and no live trial**

Assert rendered config has no `defaults.harness` and no `evaluation.treatmentHarness`; all existing OpenHands goldens remain semantically unchanged. Review the final diff against every requirement in design §§5–8.

- [ ] **Step 5: Commit and cut the selected Maku minor**

```bash
git commit -am "feat(harness): opt-in OpenCode with offline parity evidence"
```

After merge, follow the repository's normal release process. The ANR plan's live tasks start only after explicit aws-0 authorization.

---

## Self-review

| Design requirement | Tasks |
|---|---|
| Shared bridge and Python runner | 1, 2 |
| Pinned non-root production image | 3 |
| Server API, replay, mapping, steering, approvals | 4, 5 |
| Role permissions, providers, rotating MCP tokens | 6 |
| Maku-owned stuck detection | 7 |
| Bounded synchronous search | 8 |
| PVC restore, process cleanup, checkpoint, final read, revoke | 9 |
| Metadata-only correlated traces | 10 |
| Existing AgentRun seam and image selection | 11 |
| Task-level selection, intake, provenance | 12 |
| Rescue cohort and truthful outcome accounting | 13 |
| Real-binary/container/gVisor offline gate and release | 14 |
| Browser and language rewrite excluded | global constraints |
| Live providers, A/B, cutover, soak | ANR plan only |
