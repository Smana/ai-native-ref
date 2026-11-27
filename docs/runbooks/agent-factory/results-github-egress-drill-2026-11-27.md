# Results: GitHub egress install-window drill, gcp-0, 2026-11-27

[Runbook 31](31-github-egress-drill.md) on gcp-0 with Maku v0.57.0 (ANR v4.1.11, cloud-native-ref
#2935, ANR #620: no `installEgress` override). **Partial: step 0 passed; steps 1 to 5 were not run.**
Filing the step-1 drill issue (`factory/ready` on `Smana/ai-native-ref`) was refused by the
operator session's permission classifier, and every later step needs a run that issue starts. Step 4
never began: `room-broker` was not suspended and no fault was injected, so the Gemini comparison
running on the same cluster was not touched.

What the drill could still read, passively, from a check-enabled run already on the cluster
(`run-p57vdh4x`, task `xcz47mln`, `Smana/image-gallery#82`, harness
`maku-harness:v0.57.0@sha256:e053b183…`), is below. It covers most of steps 2 and 3 and found two
defects.

## Step 0: baseline (09:49 UTC) — pass

| Check | Read |
|---|---|
| Proxy image | `maku-run-controller:v0.57.0@sha256:97a6ef48…` |
| Proxy Role in `agents` | `get, list, watch, patch` |
| Run-pod policy | `maku-agent-system-run-pods` names `egress-install` 9 times |
| `installEgress` override | none: the built-in hosts |
| Logs rule | `MakuEgressInstallClosedRefusal` in `agent-platform-logs`, health `ok` |
| `room-broker` HelmRelease | Ready, not suspended (before and after) |

## Steps 2 and 3, read from `run-p57vdh4x` — pass

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

## Defect 1: LiteLLM's cost map is an `install_closed` refusal on every run

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

## Defect 2: the logs rule fires late, not never

The rule fired, one evaluation later than expected. vmalert aligns a group's evaluation time down to
its 5-minute interval: its 09:54:07 evaluation read the window ending 09:50:00 (0 lines), and the
09:59:07 one read the window ending 09:55:00, which holds the 09:51:39 line (1 line); the alert was
firing at 10:04:07. Three more `install_closed` refusals followed by 10:07 (`vqcajao2`, `akfymtwn`,
`7zx6iazm`), all LiteLLM's fetch (defect 1). A line can so wait up to about 10 minutes for its
alert. The fix is ANR config: `eval_alignment: false` on the `agent-platform-logs` group, which
`AgentCacheMarkerMissing` shares.

## Not run

| Step | Why |
|---|---|
| 1 (incident replay) | The drill issue could not be filed (permission classifier) |
| 2, 3 on ANR with its pinned tools and hook environments | Same: needs the step-1 run |
| 4a, 4b (fail closed) | Needs a run; no suspension and no fault injection happened |
| 5 (ordinary task) | Same |

To finish: fix defect 1 first (otherwise step 1's pass condition, the alert, is noise), then file the
step-1 issue as a maintainer and run steps 1 to 5.
