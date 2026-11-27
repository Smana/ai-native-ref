# Results: GitHub egress install-window drill, gcp-0, 2026-11-27

[Runbook 31](31-github-egress-drill.md) on gcp-0, in two sessions:

- **Session 1** (09:49 UTC): Maku v0.57.0. It found two defects (below).
- **Session 2** (14:26–14:58 UTC): Maku v0.57.2, which carries the fixes (Smana/maku#800, Smana/maku#805, ANR #637), on ANR v4.1.13 with cloud-native-ref #2938. No `installEgress` override.

**Verdict: pass, with steps 1 and 4b settled by the owner as below.** No Flux release was suspended and no fault was injected in either session, so the Gemini comparison on the same cluster was not touched.

| Step | Result |
|---|---|
| 0 Baseline | pass |
| 1 Incident replay | covered by steps 2–3. The agent declined an untrusted drill: injection layer, pass |
| 2 Pinned toolchain installs | pass |
| 3 The proxy's view of the phases | pass |
| 4a Window ends before the close | skipped (owner) |
| 4b The close fails | not run. Fail-closed is covered offline in CI: `internal/egressproxy/install_test.go` `TestInstallCloseWriteFails` and `TestInstallSetClosesAtTheDeadline` (Maku `check-test`); `images/maku-harness/tests/test_install_phase.py` `test_a_close_the_proxy_refuses_fails_closed`, `test_a_set_still_open_after_the_close_fails_closed`, `test_an_unreachable_proxy_fails_closed` and `test_an_install_set_left_open_starts_no_agent` (`harness-test`) |
| 5 No regression | pass |
| Alert noise on ordinary runs | stopped on v0.57.2 |

## Session 2 (v0.57.2)

### Step 1: replay — covered by steps 2–3

The step-1 issue Smana/ai-native-ref#649 (task `xi7ld37x`, run `rfscv6vx`) asked the agent to run the three downloads. The agent declined them as untrusted input. Its finish step reads "Declined untrusted drill commands; no changes, no PR", after 10 steps. That is the injection layer holding.

So no release, raw or codeload request reached the proxy from that run. The egress side is proved by steps 2 and 3:
- the install set closes before the agent starts;
- the closed set refuses (session 1 showed `install_closed` on a live refusal);
- `raw` and `codeload` are in no set, so they are refused `not_allowed`.

Replaying the downloads from inside a run with `kubectl exec` was refused by the operator sessions' permission classifier, and the owner chose not to run it.

### Steps 2 and 3: three concurrent ANR check runs — pass

The runs were `rfscv6vx` (#649), `i74n5rmu` (task `2oupm7ex`, #632) and `t3sjsov6` (task `6l6rt6dl`, #625), on harness `maku-harness:v0.57.2@sha256:8cf29388…`. Each pod carried `egress-install` and `egress-install-until` (create + 1,200 s) and the harness's `EGRESS_INSTALL_CLOSE_URL`.

| Time (UTC) | Proxy decisions, all three runs |
|---|---|
| 14:46:52–14:47:15 | `allow` with `"phase":"install"`: `github.com`, `api.github.com`, `dl.google.com`, `release-assets.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org` |
| 14:47:16 | `install-check run=i74n5rmu open` (a replica's watch trailing the close) |
| 14:47:16–17 | `close-install` for each run |
| 14:47:17 | `refuse … install-check.maku.invalid:443` with `"reason":"install_check"`: the harness's check, retried once for `i74n5rmu` |
| 14:47:53 on | only `github.com` and `api.github.com`, with `"phase":"agent"` |

Each harness logged `agent-run install phase: agent-checks: toolchain ready`, then `agent-run: install hosts closed: the egress proxy refuses them`, then its first step. The install phase took **about 25 s** from the first decision to the close, against M1's p50 of 15 s, well inside the 60 s budget. `t3sjsov6`'s own checks ended "6 pass (the agent's own run)", with no `toolchain incomplete`.

### Step 5: an ordinary task — pass

Task `6l6rt6dl` (#625, run `t3sjsov6`) opened Smana/ai-native-ref#650 at 14:52:06. That is about 9 minutes after its pod was created at 14:43:07, image pulls on a cold node included. #650's `validate`, `lint` and `prerelease` checks pass; `maku/merge-gate` was still pending when this was written, which is the gate, not CI. The other run, task `2oupm7ex` (#632), ended `NoOp`.

### Alert noise — stopped

- Since v0.57.2 rolled out (proxy at 14:24): zero `install_closed` refusals and zero `raw.githubusercontent.com` or `models.opencode.ai` requests.
- No `cost map` line in the harnesses' logs, and vmalert-victoria-logs has no active alert.
- On v0.57.0, every check run had made one such refusal, one second after its close; the last was 11:04:56 (`iyo3gggb`).

## Session 1 (v0.57.0)

### Step 0: baseline (09:49 UTC) — pass

| Check | Read |
|---|---|
| Proxy image | `maku-run-controller:v0.57.0@sha256:97a6ef48…` |
| Proxy Role in `agents` | `get, list, watch, patch` |
| Run-pod policy | `maku-agent-system-run-pods` names `egress-install` 9 times |
| `installEgress` override | none: the built-in hosts |
| Logs rule | `MakuEgressInstallClosedRefusal` in `agent-platform-logs`, health `ok` |
| `room-broker` HelmRelease | Ready, not suspended (before and after) |

### Steps 2 and 3, read from `run-p57vdh4x` — pass

Pod annotations: `egress-install` (release-assets first), `egress-install-until: 2026-11-27T10:10:13Z`
(create 09:50:13 + 1,200 s), `egress-install-closed: "true"`. The proxy's decisions for the run:

| Time (UTC) | Decision | Phase | Reason |
|---|---|---|---|
| 09:51:28 | allow `raw.githubusercontent.com:443` (see defect 1) | install | |
| 09:51:37 | allow `github.com:443` (twice: the clone) | install | |
| 09:51:38 | `close-install run=p57vdh4x` | | |
| 09:51:38 | refuse `install-check.maku.invalid:443` (the harness's check) | agent | `install_check` |
| 09:51:39 | refuse `raw.githubusercontent.com:443` | agent | `install_closed` |
| 09:52:37 | refuse `go.dev:443` (the agent fetching a Go toolchain) | agent | `not_allowed` |
| 09:52:41 | allow `dl.google.com:443`, `proxy.golang.org:443` | agent | (`golang` profile) |

The harness logged `agent-run: install hosts closed: the egress proxy refuses them` before its first
step. The repository declares no checks (`agent-run: no repository checks`), so there was no
toolchain to install: the install phase was the clone plus the close, 10 s from the first decision.

### Defect 1: LiteLLM's cost map is an `install_closed` refusal on every run

The 09:51:39 `install_closed` refusal is not the agent. The harness log at the same second:

```text
LiteLLM:WARNING: get_model_cost_map.py:454 - LiteLLM: Failed to fetch remote model cost map from
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json: 403 Forbidden. Fall…
```

LiteLLM fetches its model price map from `raw.githubusercontent.com` when the SDK loads, and falls
back to its bundled copy on failure. Two consequences:

- `MakuEgressInstallClosedRefusal` would fire on every run whose SDK loads after the close, so it
  cannot tell the incident apart.
- The M1 measurement's "`raw` is used before the agent's first step" (110 of 112 calls) is very
  likely this fetch at agent-server start (09:51:28 above, before the clone), not mise. `raw` may not
  need to be in the install set at all.

Fix (Maku): set `LITELLM_LOCAL_MODEL_COST_MAP=True` in the harness images or the run's harness env, so
the SDK never fetches; then re-measure `raw` and drop it from `defaultInstallHosts` if nothing else
uses it.

### Defect 2: the logs rule fires late, not never

The rule fired, one evaluation later than expected. vmalert aligns a group's evaluation time down to
its 5-minute interval: its 09:54:07 evaluation read the window ending 09:50:00 (0 lines), and the
09:59:07 one read the window ending 09:55:00, which holds the 09:51:39 line (1 line); the alert was
firing at 10:04:07. Three more `install_closed` refusals followed by 10:07 (`vqcajao2`, `akfymtwn`,
`7zx6iazm`), all LiteLLM's fetch (defect 1). A line can so wait up to about 10 minutes for its
alert. The fix is ANR config: `eval_alignment: false` on the `agent-platform-logs` group, which
`AgentCacheMarkerMissing` shares.

Both defects are fixed in v0.57.2: defect 1 by Smana/maku#800, which also drops `raw` from the install set, and defect 2 by ANR #637.
