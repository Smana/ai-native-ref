# Capability profiles, P2 and P4: per-role model allow-lists and the model pinned per run — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A role can call only the model aliases its profile names (P2), and a run reaches the alias
it was created with on every model path, and the judge's alias on `/judge/v1`, whatever the harness
or a command in the sandbox asks for (P4).

**Architecture:** Four pull requests in three repositories, in this order:

1. **PR A, ai-native-ref** (P2 and P4's gateway half). `scripts/ci/gen-capabilities.py` also renders
   `infrastructure/base/agent-gateway/policy-capabilities.yaml`: one route-level `authorization` per
   listener on its model routes, refusing 403 a model the caller's profile does not name. The three
   LLM backends' `model` transformation takes `x-ar-model` before the body's model. Gate AG12 pins
   the new transformation and refuses any object that removes `x-ar-model`; a new gate AG14 holds
   the rendered policy in the bundle. A wire test runs both on the pinned agentgateway.
2. **PR X, crossplane-configuration.** The `AgentRun` XRD gains `spec.loop.judgeModel`, and the
   composition gives the identity-proxy container `MODEL` and `JUDGE_MODEL` (`none` without a judge).
   Released, then pinned by the host.
3. **PR H, cloud-native-ref.** The host pins that release.
4. **PR B, ai-native-ref** (P4's sidecar half). The identity proxy's bootstrap sets `x-ar-model` from
   `MODEL` on `/v1/` and `/anthropic/`, and from `JUDGE_MODEL` on a new `/judge/v1/` prefix that it
   rewrites to `/v1/`. `HOST_REF` moves to a host commit that holds PR H. The wire test gains the proxy.

Nothing narrows a profile: every profile keeps the four aliases until the bake-off, deferred with
the eval bench (D6). The mechanism ships; narrowing a profile is its switch.

**Tech Stack:** Python 3 with PyYAML, Bash suites run by `scripts/ci/run-tests.sh` inside
`.composite/`, agentgateway 1.6.0 (route-level `authorization` CEL, AI `transformations`), Envoy
1.39.1 (`request_headers_to_add`, `%ENVIRONMENT()%`), KCL 0.11.3 and Crossplane 2.1.3 in
crossplane-configuration, Docker in CI.

**Spec:** [the capability profiles design](../specs/2026-10-21-capability-profiles-design.md),
decisions P2 and P4, the "What the generator emits" rows for models and the `model` transformation,
gate items 1 and 3, and the S0 result. The loop policy's judge
([loops L2, the policy's config](../specs/2026-10-21-loops-and-teams-design.md#the-policy-in-the-factory-config))
names the claim field and the sidecar variable.

**Out of P2 and P4:** narrowing any profile (the bake-off). P3's argument constraints. The
`agent-capability-profiles` ConfigMap and the bridge's read-only map (P5). The factory setting
`spec.loop.judgeModel` and the harness calling `/judge/v1` (the loop policy's later steps).
`roles.<dataClass>.<role>` and `loops.*.judge` in AG14's pinned set (the loop policy adds them with
those keys). The live halves of gate items 1 and 3, batched into the next gcp-0 session (Task 10).

### This plan's rulings

| # | Ruling | Why |
|---|---|---|
| R1 | **The rule reads the model itself: `("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model)`, not `llm.requestModel`.** The spec's `llm.requestModel in [...]` is replaced | Measured on the v1.6.0 binary: a route-level `authorization` runs in the route's policies, before the backend parses the body, and `llm` is set on the response only (`cel/types.rs` `set_request_extensions`, `llm/mod.rs` inserting `LLMContext` into the response's extensions). A Require on `llm.requestModel` refused every call, allowed models included; a backend-level `authorization` did the same. `json(request.body)` buffers and parses the body there and works |
| R2 | **One Require per listener, `.with(m, …)` binding the model once, one alternative per role OR-ed**: `EFFECTIVE.with(m, ("agent-router.implementer.internal" in jwt.aud && m in [...]) \|\| …)`. The policy's first expression repeats the listener's own Require (`jwt.sub.startsWith("system:serviceaccount:agents:")`), read from `policies-identity.yaml` | The spec's table wrote one `"<aud>" in jwt.aud && …` Require per role: Requires are AND-ed, so no single-audience token could pass two of them. `.with` works in an authorization rule (measured). Measured too: 1.6 adds a route's authorization rule sets to the listener's (`store/binds.rs` `route_policies`, a listener Require `jwt.sub == "nobody"` still refused with a route rule present), so the spec's "replaces the listener's" does not hold; the repetition stays, as the spec asks and AG14 asserts, because the standalone proof covers the data plane and not the controller's translation |
| R3 | **The policy targets each LLM route's rules by `sectionName`, never the `/v1/models` rule**, and is generated whole into `policy-capabilities.yaml`, one `AgentgatewayPolicy` per listener (`capabilities-public`, `capabilities-internal`, in `agent-system`, the routes' namespace) | Measured: the body read on a body-less `GET /v1/models` refuses it 403 before its 404 (AG7). A whole generated file has no hand-written part to splice around, unlike `mcp.yaml` (P1 R1) |
| R4 | **`models` is a non-empty, duplicate-free subset of the served aliases**, rendered in the profile's order; P1's "must equal the four aliases" is dropped. Every profile keeps the four | The mechanism ships now and narrowing must need only a profile edit (P2). The bake-off that would narrow is deferred (D6), so P2 binds nothing today |
| R5 | **A 403 on a model call is acceptable.** Unlike S0, it costs the refused call only | Measured with the harness's own stack (litellm 1.93.2, `map_provider_exception` of OpenHands SDK 1.49.6 and of 1.56.0): the gateway's 403 is a `litellm.APIError` 403 (`authorization failed`), not retried (the harness sets `num_retries=0` and its retry patch takes only 503 and connection errors), so the conversation ends `ERROR` with that text. A model call is one stateless HTTP request: there is no session to lose, which is what S0 measured on MCP. The harness's own calls never meet it: with P4 they carry `MODEL`, which AG14 holds to every profile. Today an unknown name already ends a run, with a 400. S0 itself is fixed in SDK ≥ 1.55 (measured 2026-10-22 by the SDK 1.56 plan, agent-platform `0280c09`): that changes P3's options, not this plan; the spec amendment records P3's dependency on a harness release with SDK ≥ 1.55 |
| R6 | **The gateway does not strip `x-ar-model`: the identity proxy overwrites it, and AG12 refuses any object that removes it.** The prompt's "strips a client-set copy as it strips `x-ar-agent`" is ruled out | A strip at the gateway would erase the proxy's value too: both arrive on the same connection, and `x-ar-agent` can be stripped only because the gateway sets it again from the JWT, which holds no model. Only the proxy holds a run token (a call from the harness straight to the gateway is a 401), and Envoy's `OVERWRITE_IF_EXISTS_OR_ADD` replaces the harness's value (measured). Measured too: a backend-level removal before the transformation reads the header made the rule judge the header while the backend took the body: a reviewer limited to `tier-frontier` reached `claude-haiku-5-5`. With the proxy off, a harness-set header can name only what its body could, under the same rule. The header reaches the provider, as `x-ar-agent` does |
| R7 | **The transformation and the rule make one choice: the header when present, else the body's model.** Three consequences, accepted: an unknown name is now refused 403 by the rule before the transformation's 400, a body above the frontend buffer (8Mi) 403 instead of 413, and a gzip request with no x-ar-model header, served before, is now refused 403 (the rule reads the raw body; measured, and with the header it is 200). Duplicate headers: both take the first (measured). AG14 also requires the Gateway's `frontend.http.maxBufferSize` | Measured at the cluster's 8Mi: 7.9 MiB passes with and without the rule; 8.1 MiB is 413 without it and 403 with it, so no call the backend could take is refused. Without a frontend buffer 1.6 reads 2 MiB for the rule and 32 MiB for the backend, and a 2.5 MiB call was refused 403 that passes today |
| R8 | **`JUDGE_MODEL` unset makes `/judge/v1` refuse, never default.** The composition always sets it: the claim's `spec.loop.judgeModel`, else `none`, an alias no profile can name, refused 403 | A defaulting judge path would let any command in the sandbox reach any profile model through `/judge/v1`, around the `/v1` pin. Measured: Envoy renders an unset `%ENVIRONMENT(X)%` as `-` and still overwrites the harness's value, which the rule refuses too, so a lost variable fails closed. `none` is also the loop design's own `judge: none` |
| R9 | **The judge's claim field is `spec.loop.judgeModel`**: optional, one of the four aliases, immutable with its presence (`spec.loop` as a whole, as for `branch` and `roomRef`). This plan adds only `judgeModel`; the loop policy's composition step adds `stallSteps`, `continuations` and the harness's environment to the same object | The loop design names `spec.loop: {stallSteps, continuations, judgeModel}`. The harness's judge variable is the loop policy plan's to name, so the composition gives `JUDGE_MODEL` to the proxy only |
| R10 | **No new switch (D4).** P2 binds nothing while every profile names the four aliases. The transformation's header branch is inert until a header arrives. The `/v1` pin changes nothing the platform sends: the harness asks for `MODEL` (`agent_run.py`, `model="openai/" + env["MODEL"]`) and its condenser copies that LLM (`get_default_agent`). `/judge/v1` refuses until a claim names a judge, which the factory does only for a class whose loop policy is switched on | D4 asks for a per-class switch, off by default, where behaviour changes. A security control that is a no-op for every platform call needs none; the judge path is off by default through the claim |
| R11 | **Order: PR A, then PR X released and pinned by PR H, then PR B, with `HOST_REF` moved to a host commit holding PR H.** PR B merges only once the host's Flux has applied PR H on gcp-0 and aws-0 | Measured: a proxy without `MODEL` sends `x-ar-model: -`, refused 403, so a bootstrap that reads `%ENVIRONMENT(MODEL)%` ahead of the composition that sets it would refuse every model call of every new run. The other order is safe: the composition's variables are inert until the bootstrap reads them |
| R12 | **AG14 is a new gate**, on the rendered bundle: each LLM rule of the agent router other than a directResponse one has exactly one route-level authorization, a Require with the listener's sub prefix and one model rule over `EFFECTIVE_MODEL` with an alternative per audience; no body read on a directResponse rule; every model the factory's `tiers.*.model` pin is in every alternative; a frontend buffer is set. The drift suite stays `test-agent-capabilities` | The suite holds the committed bytes; only a bundle gate sees what kustomize renders (a file left out of `kustomization.yaml` passes the suite). The tier check is what makes narrowing safe: a profile that drops `agent-default` would refuse every run of every tier at its first call. Equality between a role's models and what its pinned paths can name (P4's "exactly") waits for `roles` and `loops.*.judge`, the loop policy's keys |
| R13 | **The offline proof of gate items 1 and 3 is a Docker suite, `test-agent-capabilities-wire.sh`**, on the image `parameters.yaml` pins and, in PR B, on the identity proxy's image as crossplane-configuration pins it (`ENVOY_IMAGE`, bumped with the composition's `_IDENTITY_PROXY_IMAGE`). It renders the policy from a copy of the profiles where `reviewer.internal` names `tier-standard` and `tier-light` only. A static suite, `test-identity-proxy-model-pin`, holds every model path of the bootstrap to the pin | The pattern of `test-agent-gateway-cache-wire`; `--network host` lets two containers and the fake meet on loopback. The wire test probes three paths; the static suite reads them all, and runs without Docker |
| R14 | **Gate item 1's attribution holds in 1.6.0**: the 403's access log line carries `jwt.sub` (measured). The spec's #3996 caveat concerns the model router's own 403, not a route-level authorization | Recorded in the spec amendment |

**Measured 2026-10-22** on prototypes under `$SCRATCH/p2p4/` (the code below is theirs), with the
agentgateway v1.6.0 binary (`ea56086`, the pinned image's version) and the Envoy v1.39.1 binary
(`b579d07`, the pinned proxy image's version):

- **Route-level `authorization` on `llm.requestModel`:** every call refused 403, allowed models
  included (also as a backend-level `authorization`). Without the model rule the same config
  answers 200, and 400 `model not specified` for an unknown name.
- **On `json(request.body).model`:** 200 for an allowed alias, 403 for another; `.with` works.
  Body size at `maxBufferSize: 8Mi`: 7.9 MiB 200 with and without the rule, 8.1 MiB 413 without and
  403 with. With no frontend buffer: 2.5 MiB 200 without the rule, 403 with it.
- **Merge:** a listener-targeted Require `jwt.sub == "nobody"` still refused with a passing route
  rule: rule sets add up. `GET /v1/models` under the rule: 403 instead of 404.
- **The transformation:** `("x-ar-model" in request.headers ? request.headers["x-ar-model"] :
  llmRequest.model).with(m, m in [...] ? m : null)` sends the header's alias upstream (body
  `tier-light`, header `tier-frontier`: `claude-opus-5-5`). A backend-level removal of the header
  before it: the rule passed on the header and the backend took the body (`claude-haiku-5-5`, outside
  the caller's list). Two `x-ar-model` headers: rule and transformation both take the first.
- **The harness's 403:** `litellm.APIError` 403 `authorization failed`, SDK mapping `APIError`, on
  SDK 1.49.6 and 1.56.0 (litellm 1.93.2 in both).
- **The 403's access log:** `route=default/openai http.status=403 jwt.sub=system:serviceaccount:agents:…
  reason=Authorization`.
- **Envoy:** with `MODEL` and `JUDGE_MODEL` unset, every model path sends `x-ar-model: -` over the
  harness's `client-set`; `/judge/v1/chat/completions` reaches the upstream as `/v1/chat/completions`;
  `/mcp` passes the harness's value through.
- **The chain** (proxy from the changed ConfigMap, then the gateway, then a fake Anthropic):
  `MODEL=tier-frontier JUDGE_MODEL=agent-default`: `/v1` and `/anthropic` reach `x-ar-model:
  tier-frontier` though body and harness header say `tier-light`, `/judge/v1` reaches
  `agent-default`. `JUDGE_MODEL=none`: `/judge/v1` 403. Both unset: every path 403. `MODEL` outside
  the profile: `/v1` and `/anthropic` 403, `/judge/v1` 200.
- **The generator:** on today's tree `mcp.yaml` is still its profiles' rendering (P1 parity), and
  `--write` creates `policy-capabilities.yaml` as shown in Task 2. `test-gen-capabilities`: 41 `ok`
  lines; against the P1 generator it fails (`no attribute 'CAPABILITIES'`).
- **The gate:** `test-assert-agent-gateway` passes (all `ok`); against today's gate it fails on
  `EFFECTIVE_MODEL`.
- **The wire test,** through a `docker` shim running the two binaries: 10 `ok` (PR A) and 18 `ok`
  with the proxy (PR B), `PASS`. Controls: the rule on `llm.requestModel` never answers 200; today's
  transformation fails `x-ar-model wins over the body`; today's bootstrap fails six proxy cases.
- **`test-identity-proxy-model-pin`:** `PASS` on the changed bootstrap, six `FAIL` lines on today's.
- **crossplane-configuration** on `origin/main` `48d679c`, scratch copy: `task generate-sync`,
  `task test` (`agentrun` `PASS: 109/109`, the new test included; without the KCL change `FAIL:
  1/109`) and `task schema` (`25 example claim(s) valid`; a claim with `judgeModel:
  claude-opus-5-5` is refused) pass. `task render` needs Docker (CI runs it): instead each example
  went through `main.k` with `kcl run`, and its identity-proxy container equals the changed golden's
  (`MATCH` ×4; `DIFFER` against today's goldens).
- **`task check`** on a branch holding PR A's and PR B's ai-native-ref changes, docs included:
  `assert-agent-gateway: 15 checks, 0 violations (clusters: aws-0, gcp-0)`; `PASS` for
  `test-gen-capabilities`, `test-agent-capabilities`, `test-agent-mcp-scope`,
  `test-identity-proxy-model-pin`, `test-identity-proxy-upstreams` and
  `flux-schema/test-assert-agent-gateway`; `29 passed, 3 skipped, 0 failed` (the skips: the two
  Docker suites of before and the wire test); links, the site build and the doc paths pass;
  `exit=0`. Today's main gives `14 checks` and `28 passed, 2 skipped`.

## Global Constraints

- **Repositories and branches:**
  - ai-native-ref PR A: `feat/capability-profiles-p2-p4`, in the worktree
    `/home/smana/Sources/ai-native-ref/.claude/worktrees/agent-a980c5c4e8c61a123`, which carries this
    plan on `origin/main` `e2114bc`.
  - crossplane-configuration PR X: a new worktree the executor creates (Task 7),
    `/home/smana/Sources/crossplane-configuration-model-pin` on `feat/agentrun-model-pin` from
    `origin/main` (`48d679c` when planned). The checkout at `/home/smana/Sources/crossplane-configuration`
    is not at `origin/main`: never work in it.
  - cloud-native-ref PR H: a new worktree (Task 8).
  - ai-native-ref PR B: `feat/capability-profiles-p4-pin`, a new worktree from `origin/main` after
    PR A merged (Task 9).
  In a new ai-native-ref or crossplane-configuration worktree, run `mise trust mise.toml` once.
  Rebase onto a freshly fetched `origin/main` before every push.
- **`$SCRATCH`** is a scratch directory outside the repositories. It holds two helpers:
  - `check.sh <worktree>` runs `task check` with a `python3` that has PyYAML ahead of mise's. It
    logs to `$SCRATCH/check-<worktree directory name>.log` and ends the log with `exit=N`.
  - `run-suite.sh <command…>` runs one command with that `python3`.
  The `python3` on `PATH` lacks PyYAML, so every Python and suite command in ai-native-ref goes
  through one of the two helpers.
- **`task check` is the evidence** (AGENTS.md). Never claim done without its log.
- **Docker suites SKIP locally** when no daemon runs. CI sets `CI=true`, where
  `test-agent-capabilities-wire` fails without Docker instead of skipping, so CI is where it must
  pass. crossplane-configuration's `task render` needs Docker too.
- **Run the gate's unit test inside the composite.** It imports the host's `yamlcompat`:
  `bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh && bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`.
  `host-profile.sh` copies the working tree as it is on disk, untracked files included.
- **`__pycache__/` is ignored.** Still run `export PYTHONDONTWRITEBYTECODE=1` first, and `git add`
  named paths only, never `-A`.
- **The suite contract:** line 1 is the shebang and line 2 is `# requires: <tools>`. Exit 77 is a
  SKIP. Suites read the real tree. `run-tests.sh` finds them with `git ls-files`, so a new suite
  counts only once it is committed.
- **Host scripts are never vendored.** The generator, the gates and the suites are this
  repository's own.
- **No new workload.** The constitution's workload rules gain nothing new to apply to; the identity
  proxy's container gains two environment variables and keeps its shape.
- **Commits** are conventional, in English, with **no trailers**, in every repository.
- **Verbatim from the spec:**
  - P2: "a route-level `authorization` rule `jwt.aud` → `llm.requestModel in [...]`, answering 403"
    (R1 replaces `llm.requestModel`, measured unavailable there).
  - P4: "on `/v1` the sidecar sets `x-ar-model` from its `MODEL` environment (Envoy
    `%ENVIRONMENT(MODEL)%`, overwriting any client value); on a second prefix, `/judge/v1`, from
    `JUDGE_MODEL` … the gateway … sets the request's `model` from the header. A role's `models` are
    exactly the aliases its pinned paths can name" (R6, R12).
  - Gate 1: "A run whose test profile excludes an alias is refused 403 when it names it, and the
    refusal is attributed in the access log".
  - Gate 3: "A command in the sandbox posting to the identity proxy's `/v1` with another `model`
    reaches the model the run was created with, and one posting to `/judge/v1` reaches the judge's
    alias; the gateway log names the pinned alias in both cases."

## File structure

| Repository, file | Change | Responsibility |
|---|---|---|
| **PR A** ai-native-ref `infrastructure/base/agent-gateway/llm.yaml`, `anthropic.yaml` | modify: three transformations, two comments | The backend takes `x-ar-model` first (P4) |
| `scripts/ci/flux-schema/assert-agent-gateway.py` | modify: AG12, new AG14 | The transformation and the header kept; the rule held in the bundle |
| `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py` | modify | Both gates, both ways |
| `scripts/ci/gen-capabilities.py` | modify (whole file below) | Also renders `policy-capabilities.yaml` (P2) |
| `infrastructure/base/agent-gateway/policy-capabilities.yaml` | create, generated | `capabilities-public`, `capabilities-internal` |
| `infrastructure/base/agent-gateway/kustomization.yaml` | modify: one line | Ships the policy |
| `infrastructure/base/agent-gateway/profiles/*.yaml` | modify: one comment each | `models` is rendered |
| `scripts/ci/tests/test-gen-capabilities.py` | modify | The generator's P2 cases |
| `scripts/ci/tests/test-agent-capabilities.sh` | modify: header | The drift suite covers both files |
| `scripts/ci/tests/test-agent-capabilities-wire.sh` | create | Gate item 1 offline, on the pinned image |
| `website/content/docs/platform/ai-platform/gateways.md` | modify | The model rule |
| `docs/superpowers/specs/2026-10-21-capability-profiles-design.md` | modify | Status, and the rulings above |
| **PR X** crossplane-configuration `apis/agentrun/definition.yaml` | modify | `spec.loop.judgeModel` |
| `apis/agentrun/kcl/main.k`, `main_test.k` | modify | The proxy's `MODEL` and `JUDGE_MODEL`, and their test |
| `apis/agentrun/composition.yaml` | regenerate (`task generate`) | The inlined KCL |
| `examples/agentrun-complete.yaml`, `tests/golden/agentrun-*.yaml` | modify | The new field; the proxy's env in four goldens |
| **PR H** cloud-native-ref `infrastructure/base/crossplane/configuration-{core,aws,gcp}/*.yaml`, `apps/platform/app-wizard/app.yaml` | modify: the tag | The host runs the release |
| **PR B** ai-native-ref `HOST_REF` | modify | A host commit holding PR H |
| `infrastructure/base/agent-runtime/identity-proxy-configmap.yaml` | modify | The pin on `/v1/`, `/anthropic/`, `/judge/v1/` |
| `scripts/ci/tests/test-identity-proxy-model-pin.py` | create | Every model path of the bootstrap is pinned |
| `scripts/ci/tests/test-agent-capabilities-wire.sh` | modify: a proxy section | Gate item 3 offline |
| `website/content/docs/platform/ai-platform/gateways.md`, `agents/runtime.md` | modify | The pin |
| `docs/superpowers/specs/2026-10-21-capability-profiles-design.md` | modify: status | P4 built |

---

## PR A — ai-native-ref: the model rules and the gateway's half of the pin

### Task 1: The backends take `x-ar-model` first, and AG12 keeps it

**Files:**
- Modify: `infrastructure/base/agent-gateway/llm.yaml` (header comment, two transformations),
  `infrastructure/base/agent-gateway/anthropic.yaml` (header comment, one transformation)
- Modify: `scripts/ci/flux-schema/assert-agent-gateway.py` (AG12's docstring, `MODEL_ALLOWLIST`,
  `check_model_pinning`)
- Test: `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`

**Interfaces:**
- Produces (Tasks 3 and 4 rely on these): the gate's module constants `MODEL_HEADER = "x-ar-model"`,
  `MODEL_ALLOWLIST` (the transformation, byte for byte) and the function `removes(node, header) ->
  bool`.

- [ ] **Step 1: Write the failing test**

In `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`, replace:

```python
print("main")
```

with:

```python
print("AG12 the model header (capability profiles P4)")
expect("the strip removing x-ar-model fails", lambda o: spec_at(
    o, "AgentgatewayPolicy", "strip-identity-headers", "traffic", "transformation", "request", "remove")
    .append("X-AR-Model"), "AG12", "removes x-ar-model")
expect("a route filter removing x-ar-model fails", lambda o: spec_at(o, "HTTPRoute", "agent-models", "rules")[1]
       .update({"filters": [{"type": "RequestHeaderModifier", "requestHeaderModifier": {"remove": ["x-ar-model"]}}]}),
       "AG12", "removes x-ar-model")
expect("a transformation that ignores the header fails", lambda o: zai(o)["policies"]["ai"]["transformations"][0]
       .update({"expression": 'llmRequest.model in ["agent-default"] ? llmRequest.model : null'}), "AG12", "refuse")

print("main")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py | grep -v '^  ok'
```

Expected: `FAIL the strip removing x-ar-model fails` and `FAIL a route filter removing x-ar-model
fails`, then `2 failure(s)`.

- [ ] **Step 3: The gate**

In `scripts/ci/flux-schema/assert-agent-gateway.py`, replace AG12's docstring paragraph:

```
  AG12 An LLM backend has one provider. One the agent router routes to
       refuses every name outside AGENT_MODELS before any upstream call
       (design D8): modelAliases names exactly AGENT_MODELS, with no wildcard;
       a `model` transformation, MODEL_ALLOWLIST, nulls any other name, which
       1.6 answers 400 "model not specified" (finalize_request_model); and no
       fixed provider model, override or default supplies a model, since each
       maps every name to one. No policy carries aliases or a model mutation:
       names live on the backend. Any other backend (the PoC) keeps a fixed
       model or a `*` catch-all, so it serves only models we list.
```

with:

```
  AG12 An LLM backend has one provider. One the agent router routes to
       refuses every name outside AGENT_MODELS before any upstream call
       (design D8): modelAliases names exactly AGENT_MODELS, with no wildcard;
       a `model` transformation, MODEL_ALLOWLIST, takes x-ar-model when the
       identity proxy pinned it (capability profiles P4), else the body's
       model, and nulls any name outside AGENT_MODELS, which 1.6 answers 400
       "model not specified" (finalize_request_model); and no fixed provider
       model, override or default supplies a model, since each maps every name
       to one. No policy carries aliases or a model mutation: names live on
       the backend. No object removes x-ar-model: removed before the backend
       reads it, the model would follow the body while AG14's rule judged the
       header (measured on 1.6.0). Any other backend (the PoC) keeps a fixed
       model or a `*` catch-all, so it serves only models we list.
```

Replace:

```python
MODEL_ALLOWLIST = f"llmRequest.model in {json.dumps(list(AGENT_MODELS))} ? llmRequest.model : null"
```

with:

```python
MODEL_HEADER = "x-ar-model"
MODEL_ALLOWLIST = (f'("{MODEL_HEADER}" in request.headers ? request.headers["{MODEL_HEADER}"] : llmRequest.model)'
                   f".with(m, m in {json.dumps(list(AGENT_MODELS))} ? m : null)")
```

At the end of `check_model_pinning`, replace:

```python
            out.append(f"AG12: {ref(p)} maps model names; names live on the backend, where AG12 reads them")
    return out
```

with:

```python
            out.append(f"AG12: {ref(p)} maps model names; names live on the backend, where AG12 reads them")
    for o in objs:
        if (is_agentgateway(o) or o.get("kind") in ROUTE_KINDS) and removes(o, MODEL_HEADER):
            out.append(f"AG12: {ref(o)} removes {MODEL_HEADER}: the backend would then take the body's model "
                       "while AG14's rule judged the header")
    return out


def removes(node, header):
    """Whether any `remove` list under node names the header."""
    if isinstance(node, dict):
        return any((k == "remove" and isinstance(v, list) and header in [str(h).lower() for h in v])
                   or removes(v, header) for k, v in node.items())
    return isinstance(node, list) and any(removes(v, header) for v in node)
```

- [ ] **Step 4: Run the gate's test**

Same commands as Step 2. Expected: no `FAIL` line, then `all passed`. The fixture builds its
backends from `gate.MODEL_ALLOWLIST`, so they follow the new constant.

- [ ] **Step 5: The backends**

In `infrastructure/base/agent-gateway/llm.yaml` (twice) and `anthropic.yaml` (once), replace:

```yaml
          expression: 'llmRequest.model in ["agent-default", "tier-light", "tier-standard", "tier-frontier"] ? llmRequest.model : null'
```

with:

```yaml
          expression: '("x-ar-model" in request.headers ? request.headers["x-ar-model"] : llmRequest.model).with(m, m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"] ? m : null)'
```

In `llm.yaml`'s header comment, replace:

```yaml
# provider `model`: either would give an unlisted name a model. The map is the
# same on both Z.ai backends and mirrors the internal one (anthropic.yaml):
```

with:

```yaml
# provider `model`: either would give an unlisted name a model. The name is
# x-ar-model when the run's identity proxy pinned it (capability profiles P4),
# else the body's: policy-capabilities.yaml judges the same choice, so nothing
# may remove that header (AG12). The map is the
# same on both Z.ai backends and mirrors the internal one (anthropic.yaml):
```

In `anthropic.yaml`'s header comment, replace:

```yaml
# Names as on public (llm.yaml's table): four aliases, other names refused 400
# by the `model` transformation, no fixed model (gate AG12). Budgets charge
```

with:

```yaml
# Names as on public (llm.yaml's table): four aliases, other names refused 400
# by the `model` transformation, which takes x-ar-model first (P4), no fixed
# model (gate AG12). Budgets charge
```

- [ ] **Step 6: The gate on the bundle**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|passed,|exit=" "$SCRATCH/check-$(basename "$PWD").log"
```

Expected: `assert-agent-gateway: 14 checks, 0 violations (clusters: aws-0, gcp-0)`,
`… 0 failed`, `exit=0`. With the old expression left in one backend, AG12 names it.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/base/agent-gateway/llm.yaml infrastructure/base/agent-gateway/anthropic.yaml \
  scripts/ci/flux-schema/assert-agent-gateway.py scripts/ci/tests/flux-schema/test-assert-agent-gateway.py
git commit -m "feat(agent-gateway): the backends take the model from x-ar-model first"
```

---

### Task 2: The generator renders the model rules (P2)

**Files:**
- Modify: `scripts/ci/gen-capabilities.py` (the whole file below)
- Create (generated): `infrastructure/base/agent-gateway/policy-capabilities.yaml`
- Modify: `infrastructure/base/agent-gateway/kustomization.yaml`, the eight
  `infrastructure/base/agent-gateway/profiles/*.yaml` (one comment line each),
  `scripts/ci/tests/test-agent-capabilities.sh` (header)
- Test: `scripts/ci/tests/test-gen-capabilities.py`

**Interfaces:**
- Consumes: the backends' transformation from Task 1 (the rule must read the header it reads).
- Produces (Tasks 3 and 4 rely on these): the module constants `CAPABILITIES`
  (`infrastructure/base/agent-gateway/policy-capabilities.yaml`), `IDENTITY`, `EFFECTIVE_MODEL`
  (`'("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model)'`);
  `Profile(path, role, data_class, models, tools)`; `model_rule(cls, profiles) -> str`;
  `render(root) -> ({PurePosixPath: str} | None, list[str])`; the CLI
  `python3 scripts/ci/gen-capabilities.py [--write] [ROOT]`, printing
  `gen-capabilities: <path> is its profiles' rendering` once per file when in sync.
  Policy names `capabilities-<listener>` in namespace `agent-system`.

- [ ] **Step 1: Write the failing tests**

In `scripts/ci/tests/test-gen-capabilities.py`, make these replacements.

Replace the docstring's first paragraph:

```python
"""Tests for scripts/ci/gen-capabilities.py, which renders mcp.yaml's MCP Allow lists from the profiles.

Each case copies the real infrastructure/base/agent-gateway/ into a temporary root, changes one
thing and runs the generator there: the profiles rebuild every list byte for byte, a profile edit
moves its own expression only, and each malformed profile is refused, by name, without a write.
```

with:

```python
"""Tests for scripts/ci/gen-capabilities.py, which renders mcp.yaml's MCP Allow lists (P1) and
policy-capabilities.yaml's model rules (P2) from the profiles.

Each case copies the real infrastructure/base/agent-gateway/ into a temporary root, changes one
thing and runs the generator there: the profiles rebuild every list and the policy file byte for
byte, a profile edit moves its own expression only, and each malformed profile is refused, by name,
without a write.
```

Replace:

```python
def mcp(root):
    return root / gen.MCP
```

with:

```python
def mcp(root):
    return root / gen.MCP


def caps(root):
    return root / gen.CAPABILITIES


def rules(root):
    """{policy name: (its targetRefs' sectionNames, its expressions)} from policy-capabilities.yaml."""
    return {d["metadata"]["name"]: ([t["sectionName"] for t in d["spec"]["targetRefs"]],
                                    d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"])
            for d in yaml.safe_load_all(caps(root).read_text()) if d}
```

Replace `refused`:

```python
def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves mcp.yaml alone."""
    with tree() as t:
        before = mcp(t).read_text()
        change(t)
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and mcp(t).read_text() == before, out)
```

with:

```python
def refused(name, change, needle):
    """The changed tree fails the check, names the problem, and --write leaves both files alone."""
    with tree() as t:
        before = mcp(t).read_text(), caps(t).read_text()
        change(t)
        code, out = run(t, "--write")
        check(name, code == 1 and needle in out and (mcp(t).read_text(), caps(t).read_text()) == before, out)
```

Replace:

```python
def no_public(t):
    for p in (t / gen.PROFILES).glob("*.public.yaml"):
        p.unlink()
```

with:

```python
def no_public(t):
    for p in (t / gen.PROFILES).glob("*.public.yaml"):
        p.unlink()


def no_listener_require(t):
    path = t / gen.IDENTITY
    path.write_text(path.read_text().replace("    authorization:\n      action: Require\n", "    x-authorization:\n      action: Require\n", 1))
```

Replace the start of the parity section:

```python
print("parity")
with tree() as t:
    code, out = run(t)
    check("today's profiles render today's mcp.yaml", code == 0 and "is its profiles' rendering" in out, out)
```

with:

```python
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
```

Replace:

```python
print("drift (design gate 5)")
```

with:

```python
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
```

In the refused-profiles table, replace:

```python
    ("a narrower model list waits for P2", on("tester.public.yaml", lambda d: d.update(models=["agent-default"])),
     "until P2"),
    ("an alias no backend serves", on("tester.public.yaml", lambda d: d["models"].append("tier-huge")), "until P2"),
```

with:

```python
    ("an alias no backend serves", on("tester.public.yaml", lambda d: d["models"].append("tier-huge")),
     "models names tier-huge, which no LLM backend serves"),
    ("no model at all", on("tester.public.yaml", lambda d: d.update(models=[])), "at least one"),
    ("a model listed twice", on("tester.public.yaml", lambda d: d["models"].append("agent-default")),
     "models lists agent-default twice"),
    ("a listener with LLM routes and no Require to repeat", no_listener_require,
     "no Require authorization on the public listener to repeat"),
```

- [ ] **Step 2: Run them and watch them fail**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py
```

Expected: a traceback ending `AttributeError: module 'gen_capabilities' has no attribute
'CAPABILITIES'`.

- [ ] **Step 3: The generator**

Replace `scripts/ci/gen-capabilities.py` with:

```python
#!/usr/bin/env python3
"""Render the agent router's capability policies from the profiles (capability profiles design, P1 and P2).

One profile per role and data class, infrastructure/base/agent-gateway/profiles/<role>.<dataClass>.yaml:

    role: reviewer
    dataClass: internal
    models: [agent-default, tier-light, tier-standard, tier-frontier]
    tools:
      flux-operator-mcp:
        - search_flux_docs

`tools` (P1): this script owns the `matchExpressions` items of each MCP authorization policy in
infrastructure/base/agent-gateway/mcp.yaml and nothing else in that file. A policy's class is the
listener its HTTPRoute attaches to; its list holds one expression per profile of that class (roles
in name order) and target (in the agent-mcp backend's order) the profile names, with the tools in
the profile's order: the N7 grammar gate AG6 enforces. A tool no expression names is hidden from
tools/list and answers `Unknown tool`.

`models` (P2): this script owns infrastructure/base/agent-gateway/policy-capabilities.yaml, whole.
Each listener with an LLM route gets one route-level authorization on those routes' rules, except a
rule a directResponse answers (the /v1/models 404, which has no body to read): the listener's own
Require rules, repeated, and one Require that the caller's audience names the model the call
reaches. That model is the identity proxy's x-ar-model when present (P4), else the body's, the same
choice the backends' `model` transformation makes (AG12), so the rule and the model cannot disagree.
A profile's models are a non-empty subset of the aliases the LLM backends serve.

`egress`, `readOnly` and a tool's `when` are refused until the steps that render them: a field
nothing enforces must not read as a rule.

Usage: gen-capabilities.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed files are the rendering (or --write wrote it), 1 drift or a bad profile.
"""
import difflib
import json
import pathlib
import re
import sys
from typing import NamedTuple

import yaml

GATEWAY = pathlib.PurePosixPath("infrastructure/base/agent-gateway")
PROFILES = GATEWAY / "profiles"
MCP = GATEWAY / "mcp.yaml"
CAPABILITIES = GATEWAY / "policy-capabilities.yaml"
IDENTITY = GATEWAY / "policies-identity.yaml"
GATEWAY_NAME = "agent-router"
AUD_PREFIX = "agent-router"
KEYS = ("role", "dataClass", "models", "tools")
# Rendered from the agent-capability-profiles ConfigMap step on; refused until then.
CONFIGMAP_KEYS = ("egress", "readOnly")
FILE = re.compile(r"^(?P<role>[a-z]+)\.(?P<cls>[a-z]+)\.yaml$")
TOOL = re.compile(r"^[a-z0-9_]+$")
SEPARATOR = re.compile(r"^---\n", re.M)
LIST = re.compile(r"^(?P<indent> *)matchExpressions:\n(?:(?P=indent)  - .*\n)+", re.M)
# The model a call reaches: the identity proxy's pin when present (P4), else the body's. agentgateway
# 1.6 has no llm.requestModel in a route-level authorization (the backend parses the body later:
# measured, every call refused), so the rule reads the body itself. AG12 pins the backends' `model`
# transformation to the same header.
EFFECTIVE_MODEL = '("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model)'
HEADER = """\
# Generated by scripts/ci/gen-capabilities.py --write from profiles/*.yaml (capability profiles design,
# P2): edit the profiles, never this file. test-agent-capabilities fails on any difference.
#
# One route-level authorization per listener, on its LLM rules but not the /v1/models one, which has
# no body to read and must keep its 404. A role may call only the models its profile names; the model
# a call reaches is x-ar-model when the identity proxy pinned it (P4), else the body's, as in the
# backends' `model` transformation. A refusal answers 403 and the access log names the run's sub.
# 1.6 has no llm.requestModel before the backend parses the body, so the rule parses it: a body above
# the frontend's 8Mi buffer, which the backend could not take either, is refused 403 rather than 413.
# 1.6 adds route rules to the listener's; the listener's Require is repeated in case that changes.
"""


class Profile(NamedTuple):
    path: str
    role: str
    data_class: str
    models: list
    tools: dict


def expression(role, cls, target, tools):
    """One N7 alternative: one role's audience, one target, its tool names."""
    names = ", ".join(f'"{t}"' for t in tools)
    return f'"{AUD_PREFIX}.{role}.{cls}" in jwt.aud && mcp.tool.target == "{target}" && mcp.tool.name in [{names}]'


def model_rule(cls, profiles):
    """One Require for a listener: the caller's audience names the model the call reaches (P2)."""
    alternatives = " || ".join(f'("{AUD_PREFIX}.{p.role}.{cls}" in jwt.aud && m in {json.dumps(p.models)})'
                               for p in sorted(profiles, key=lambda p: p.role) if p.data_class == cls)
    return f"{EFFECTIVE_MODEL}.with(m, {alternatives})"


def documents(root):
    """(path, document) for every YAML document beside mcp.yaml."""
    return [(path, doc) for path in sorted((root / GATEWAY).glob("*.yaml"))
            for doc in yaml.safe_load_all(path.read_text()) if isinstance(doc, dict)]


def served_aliases(root):
    """Every model alias an LLM backend beside mcp.yaml serves (AG12 pins them to AGENT_MODELS)."""
    aliases = set()
    for _, doc in documents(root):
        if doc.get("kind") == "AgentgatewayBackend":
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
    if not isinstance(models, list) or not models or not all(isinstance(n, str) for n in models):
        errors.append(f"{rel}: models lists the aliases this role may call, at least one")
        models = []
    else:
        twice = sorted({n for n in models if models.count(n) > 1})
        if twice:
            errors.append(f"{rel}: models lists {', '.join(twice)} twice")
        unserved = [n for n in models if n not in aliases]
        if unserved:
            errors.append(f"{rel}: models names {', '.join(unserved)}, which no LLM backend serves {sorted(aliases)}")
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
    return Profile(rel, str(doc.get("role")), str(doc.get("dataClass")), models, tools)


def listener_requires(root, errors):
    """{listener: its authorization's Require expressions}, from the listener policies (AG2 pins them)."""
    out = {}
    for doc in yaml.safe_load_all((root / IDENTITY).read_text()):
        if not isinstance(doc, dict) or doc.get("kind") != "AgentgatewayPolicy":
            continue
        spec = doc.get("spec") or {}
        authz = (spec.get("traffic") or {}).get("authorization")
        for t in spec.get("targetRefs") or []:
            if t.get("kind") == "Gateway" and t.get("name") == GATEWAY_NAME and t.get("sectionName") and authz:
                if authz.get("action") != "Require":
                    errors.append(f"{IDENTITY}: {doc['metadata']['name']} authorization is not a Require")
                out[t["sectionName"]] = list((authz.get("policy") or {}).get("matchExpressions") or [])
    return out


def llm_rules(root, errors):
    """{listener: [(route, rule name)]} for every rule that sends to an LLM backend, in file order,
    except a rule a directResponse policy answers. The listener order is the Gateway's."""
    docs = [d for _, d in documents(root)]
    llm = {(d["metadata"].get("namespace"), d["metadata"]["name"]) for d in docs
           if d.get("kind") == "AgentgatewayBackend" and "ai" in (d.get("spec") or {})}
    answered = {(d["metadata"].get("namespace"), t.get("name"), t.get("sectionName")) for d in docs
                if d.get("kind") == "AgentgatewayPolicy" and "directResponse" in ((d.get("spec") or {}).get("traffic") or {})
                for t in d["spec"].get("targetRefs") or [] if t.get("kind") == "HTTPRoute"}
    gateway = next((d for d in docs if d.get("kind") == "Gateway" and d["metadata"]["name"] == GATEWAY_NAME), None)
    order = [lst["name"] for lst in (gateway or {}).get("spec", {}).get("listeners") or []]
    out = {}
    for d in docs:
        if d.get("kind") != "HTTPRoute":
            continue
        ns, name = d["metadata"].get("namespace"), d["metadata"]["name"]
        rules = [r for r in d["spec"].get("rules") or []
                 if any(b.get("kind") == "AgentgatewayBackend" and ((b.get("namespace") or ns), b.get("name")) in llm
                        for b in r.get("backendRefs") or [])]
        if not rules:
            continue
        sections = {p.get("sectionName") for p in d["spec"].get("parentRefs") or [] if p.get("name") == GATEWAY_NAME}
        if len(sections) != 1:
            errors.append(f"{GATEWAY}: HTTPRoute {name} must attach to one {GATEWAY_NAME} listener, got {sorted(map(str, sections))}")
            continue
        cls = sections.pop()
        for r in rules:
            if not r.get("name"):
                errors.append(f"{GATEWAY}: HTTPRoute {name} has an unnamed rule to an LLM backend; a policy targets it by name")
            elif (ns, name, r["name"]) not in answered:
                out.setdefault(cls, []).append((ns, name, r["name"]))
    return {cls: out[cls] for cls in sorted(out, key=lambda c: order.index(c) if c in order else len(order))}


def render_capabilities(root, profiles, errors):
    """policy-capabilities.yaml as the profiles render it (P2)."""
    requires = listener_requires(root, errors)
    rules = llm_rules(root, errors)
    for p in profiles:
        if p.data_class not in rules:
            errors.append(f"{p.path}: no LLM route on the {p.data_class} listener for its models to bind")
    docs = []
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
        exprs = "".join(f"          - '{e}'\n" for e in requires[cls] + [model_rule(cls, profiles)])
        docs.append(f"apiVersion: agentgateway.dev/v1alpha1\nkind: AgentgatewayPolicy\nmetadata:\n"
                    f"  name: capabilities-{cls}\n  namespace: {ns.pop()}\nspec:\n  targetRefs:\n{refs}"
                    f"  traffic:\n    authorization:\n      action: Require\n      policy:\n"
                    f"        matchExpressions:\n{exprs}")
    text = HEADER + "---\n".join(docs)
    if not errors:
        # Every expression is written between single quotes: one that held a quote would parse back
        # as something else, so the file must parse back to exactly what was rendered.
        parsed = [d for d in yaml.safe_load_all(text) if d]
        want = [requires[c] + [model_rule(c, profiles)] for c in rules]
        held = [d["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"] for d in parsed]
        if held != want:
            errors.append(f"{CAPABILITIES}: the rendering does not parse back to its expressions")
    return text


def render(root):
    """({path: text as the profiles render it}, []) or (None, the errors that prevent it)."""
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
    entries = sorted((root / PROFILES).iterdir()) if (root / PROFILES).is_dir() else []
    # Anything else in the directory (a .yml copy, a subdirectory) reads like a rule but grants nothing.
    for e in entries:
        if not (e.is_file() and FILE.match(e.name)):
            errors.append(f"{PROFILES}/{e.name}: only <role>.<dataClass>.yaml files are profiles; this one grants "
                          "nothing, so rename or remove it")
    files = [e for e in entries if e.is_file() and FILE.match(e.name)]
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
                 for t in targets if isinstance(p.tools.get(t), list)]
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
    capabilities = render_capabilities(root, profiles, errors)
    return (None, errors) if errors else ({MCP: "---\n".join(chunks), CAPABILITIES: capabilities}, [])


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
    drift = False
    for path, text in rendered.items():
        current = (root / path).read_text() if (root / path).exists() else ""
        if text == current:
            print(f"gen-capabilities: {path} is its profiles' rendering")
        elif write:
            (root / path).write_text(text)
            print(f"gen-capabilities: wrote {path}")
        else:
            drift = True
            sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                                       f"{path} (committed)", f"{path} (rendered from {PROFILES})"))
            print(f"FAIL {path} differs from its profiles' rendering: edit the profiles, run "
                  "python3 scripts/ci/gen-capabilities.py --write and commit both", file=sys.stderr)
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Render, and ship the file**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/gen-capabilities.py --write
```

Expected: `gen-capabilities: infrastructure/base/agent-gateway/mcp.yaml is its profiles' rendering`
(P1 parity: no list moves) and `gen-capabilities: wrote
infrastructure/base/agent-gateway/policy-capabilities.yaml`, holding exactly:

```yaml
# Generated by scripts/ci/gen-capabilities.py --write from profiles/*.yaml (capability profiles design,
# P2): edit the profiles, never this file. test-agent-capabilities fails on any difference.
#
# One route-level authorization per listener, on its LLM rules but not the /v1/models one, which has
# no body to read and must keep its 404. A role may call only the models its profile names; the model
# a call reaches is x-ar-model when the identity proxy pinned it (P4), else the body's, as in the
# backends' `model` transformation. A refusal answers 403 and the access log names the run's sub.
# 1.6 has no llm.requestModel before the backend parses the body, so the rule parses it: a body above
# the frontend's 8Mi buffer, which the backend could not take either, is refused 403 rather than 413.
# 1.6 adds route rules to the listener's; the listener's Require is repeated in case that changes.
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: capabilities-public
  namespace: agent-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agentgateway-models
      sectionName: openai
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agentgateway-models
      sectionName: anthropic
  traffic:
    authorization:
      action: Require
      policy:
        matchExpressions:
          - 'jwt.sub.startsWith("system:serviceaccount:agents:")'
          - '("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model).with(m, ("agent-router.implementer.public" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.reviewer.public" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.tester.public" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.triager.public" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]))'
---
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: capabilities-internal
  namespace: agent-system
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agentgateway-models-internal
      sectionName: openai
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agentgateway-models-internal
      sectionName: anthropic
  traffic:
    authorization:
      action: Require
      policy:
        matchExpressions:
          - 'jwt.sub.startsWith("system:serviceaccount:agents:")'
          - '("x-ar-model" in request.headers ? request.headers["x-ar-model"] : json(request.body).model).with(m, ("agent-router.implementer.internal" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.reviewer.internal" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.tester.internal" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]) || ("agent-router.triager.internal" in jwt.aud && m in ["agent-default", "tier-light", "tier-standard", "tier-frontier"]))'
```

In `infrastructure/base/agent-gateway/kustomization.yaml`, replace:

```yaml
  - policy-budgets.yaml
```

with:

```yaml
  - policy-budgets.yaml
  - policy-capabilities.yaml
```

In each of the eight profiles, replace the line:

```yaml
# models is checked against the backends' aliases, not rendered, until P2.
```

with:

```yaml
# models is rendered into policy-capabilities.yaml (P2): the aliases this role may call.
```

In `scripts/ci/tests/test-agent-capabilities.sh`, replace:

```bash
# Capability profiles design, gate 5: the MCP Allow lists committed in
# infrastructure/base/agent-gateway/mcp.yaml are exactly what scripts/ci/gen-capabilities.py
# renders from infrastructure/base/agent-gateway/profiles/, as AG8 holds the budgets' cost string
# to meter.prices. A list edited by hand, or a profile changed without --write, fails here with
# the diff. The real tree.
```

with:

```bash
# Capability profiles design, gate 5: the MCP Allow lists committed in
# infrastructure/base/agent-gateway/mcp.yaml and the model rules in policy-capabilities.yaml are
# exactly what scripts/ci/gen-capabilities.py renders from infrastructure/base/agent-gateway/profiles/,
# as AG8 holds the budgets' cost string to meter.prices. A list or a rule edited by hand, or a profile
# changed without --write, fails here with the diff. The real tree.
```

- [ ] **Step 5: Run the tests**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-gen-capabilities.py | grep -v '^  ok'
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities.sh
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh && bash $SCRATCH/run-suite.sh bash .composite/scripts/ci/tests/test-agent-mcp-scope.sh
```

Expected: the section headers and `all passed` (41 `ok` lines in all); two `is its profiles'
rendering` lines; the scope suite passes (the tool lists did not move).

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/gen-capabilities.py scripts/ci/tests/test-gen-capabilities.py scripts/ci/tests/test-agent-capabilities.sh \
  infrastructure/base/agent-gateway/policy-capabilities.yaml infrastructure/base/agent-gateway/kustomization.yaml \
  infrastructure/base/agent-gateway/profiles/
git commit -m "feat(agent-gateway): capability profiles P2, the per-role model rules generated from the profiles"
```

---

### Task 3: AG14 holds the rule in the bundle

**Files:**
- Modify: `scripts/ci/flux-schema/assert-agent-gateway.py` (docstring, constants, a new check)
- Test: `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`

**Interfaces:**
- Consumes: `MODEL_HEADER` (Task 1); `policy-capabilities.yaml` in the bundle (Task 2).
- Produces: the module constant `EFFECTIVE_MODEL`, equal to the generator's; the check
  `check_model_authz(objs) -> list[str]`, the fifteenth in `CHECKS`.

- [ ] **Step 1: Write the failing test**

In `scripts/ci/tests/flux-schema/test-assert-agent-gateway.py`, replace:

```python
def agent_aliases(model):
    return {name: model for name in gate.AGENT_MODELS}
```

with:

```python
def agent_aliases(model):
    return {name: model for name in gate.AGENT_MODELS}


def model_rule(prof, listener, auds=None):
    """A P2 model rule as gen-capabilities.py renders it: one alternative per audience."""
    alts = " || ".join(f'("{a}" in jwt.aud && m in ["agent-default"])'
                       for a in (auds if auds is not None else sorted(gate.audiences(prof, listener))))
    return f"{gate.EFFECTIVE_MODEL}.with(m, {alts})"
```

In `compliant()`, replace:

```python
        obj("AgentgatewayPolicy", gw_ns, "strip-identity-headers", {
```

with:

```python
        obj("AgentgatewayPolicy", gw_ns, "frontend", {
            "targetRefs": [gw_ref], "frontend": {"http": {"maxBufferSize": "8Mi"}}}),
        obj("AgentgatewayPolicy", gw_ns, "strip-identity-headers", {
```

and replace:

```python
        obj("AgentgatewayBackend", rns, "agent-mcp", {"mcp": {"sessionRouting": "Stateless", "targets": [
```

with:

```python
        *[obj("AgentgatewayPolicy", rns, f"capabilities-{section}", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": route_name,
                            "sectionName": "openai"}],
            "traffic": {"authorization": {"action": "Require", "policy": {"matchExpressions": [
                gate.sub_prefix(prof), model_rule(prof, section)]}}}})
          for section, route_name in (("internal", "agent-models-internal"), ("public", "agent-models"))],
        obj("AgentgatewayBackend", rns, "agent-mcp", {"mcp": {"sessionRouting": "Stateless", "targets": [
```

Replace:

```python
check("fourteen checks", len(gate.CHECKS) == 14, f"got {len(gate.CHECKS)}")
```

with:

```python
check("fifteen checks", len(gate.CHECKS) == 15, f"got {len(gate.CHECKS)}")
```

and:

```python
    check("main prints 14 checks", "assert-agent-gateway: 14 checks, 0 violations" in out, out)
```

with:

```python
    check("main prints 15 checks", "assert-agent-gateway: 15 checks, 0 violations" in out, out)
```

Replace (Task 1 added this line):

```python
print("main")
```

with:

```python
def caps(o, listener):
    return spec_at(o, "AgentgatewayPolicy", f"capabilities-{listener}", "traffic", "authorization")


def second_policy(o):
    extra = copy.deepcopy(find(o, "AgentgatewayPolicy", "capabilities-public"))
    extra["metadata"]["name"] = "capabilities-public-copy"
    o.append(extra)


def tier_model(model):
    def change(o):
        cm = find(o, "ConfigMap", gate.FACTORY_VALUES)
        values = yaml.safe_load(cm["data"]["values.yaml"])
        values["config"]["tiers"]["frontier"]["model"] = model
        cm["data"]["values.yaml"] = yaml.safe_dump(values)
    return change


print("AG14 model authorization (capability profiles P2)")
expect("an LLM rule with no authorization fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "capabilities-internal")),
       "AG14", "has 0 route-level")
expect("two authorizations on one rule fail", second_policy, "AG14", "has 2 route-level")
expect("no repeated sub prefix fails", lambda o: caps(o, "internal")["policy"]["matchExpressions"].pop(0),
       "AG14", "must Require")
expect("Allow instead of Require fails", lambda o: caps(o, "public").update({"action": "Allow"}), "AG14", "must Require")
expect("a model rule missing an audience fails", lambda o: caps(o, "internal")["policy"]["matchExpressions"]
       .__setitem__(1, model_rule(None, "internal", ["agent-router.implementer.internal"])), "AG14", "an alternative")
expect("llm.requestModel, which 1.6 lacks there, fails", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1]
                    .replace(gate.EFFECTIVE_MODEL, "llm.requestModel")), "AG14", "one model Require")
expect("a body read on /v1/models fails", lambda o: spec_at(o, "AgentgatewayPolicy", "capabilities-internal",
                                                            "targetRefs").append(
    {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-models-internal",
     "sectionName": "models"}), "AG14", "403 before its 404")
expect("a tier pinning a model a role refuses fails", tier_model("tier-frontier"), "AG14", "which the factory's tiers pin")
expect("no frontend buffer fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "frontend")), "AG14", "maxBufferSize")
expect("a whole-route authorization reaches /v1/models and fails", lambda o: spec_at(
    o, "AgentgatewayPolicy", "capabilities-public", "targetRefs")[0].pop("sectionName"), "AG14", "403 before its 404")

print("main")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py | tail -3
```

Expected: a traceback ending `AttributeError: module 'assert_agent_gateway' has no attribute
'EFFECTIVE_MODEL'`.

- [ ] **Step 3: The gate**

In `scripts/ci/flux-schema/assert-agent-gateway.py`'s docstring, replace:

```
       Anything else, git-receive-pack included, matches no route: 404.
```

with:

```
       Anything else, git-receive-pack included, matches no route: 404.
  AG14 Every rule of the agent router that sends to an LLM backend, except
       one a directResponse answers, is targeted by exactly one route-level
       authorization (capability profiles P2): a Require holding the
       listener's sub prefix, repeated, and one model rule over
       EFFECTIVE_MODEL naming each of the listener's audiences. A rule a
       directResponse answers (/v1/models, AG7) carries no authorization that
       reads the body: its GET would be refused 403 before its 404. Every
       model the factory's tiers pin is in every alternative: a run of that
       tier would otherwise be refused at its first call. A Gateway-scoped
       policy sets frontend.http.maxBufferSize: the rule reads the body within
       it, and without it 1.6 buffers 2 MiB there and 32 MiB for the backend,
       so a long run's call would be refused that the backend could take.
```

After the `MODEL_ALLOWLIST` assignment (Task 1), add:

```python
# AG14: the model a call reaches, read where the route's authorization runs, before the backend parses
# the body (1.6 has no llm.requestModel there): the header MODEL_ALLOWLIST reads, else the body's.
EFFECTIVE_MODEL = (f'("{MODEL_HEADER}" in request.headers ? request.headers["{MODEL_HEADER}"] '
                   f": json(request.body).model)")
```

After `removes` (Task 1), add:

```python
ALTERNATIVE = re.compile(r'\("(?P<aud>[^"]+)" in jwt\.aud && m in (?P<models>\[[^\]]*\])\)')


def model_rule_ok(expr, auds):
    """One model Require: EFFECTIVE_MODEL bound to m, an alternative per audience."""
    return expr.startswith(f"{EFFECTIVE_MODEL}.with(m, ") and all(f'("{a}" in jwt.aud && m in [' in expr for a in auds)


def check_model_authz(objs):
    out = []
    llm = {key(b) for b in kind(objs, "AgentgatewayBackend") if providers(b)}
    tiers = ((factory_values(objs) or {}).get("tiers") or {}).values()
    pinned = sorted({t["model"] for t in tiers if isinstance(t, dict) and t.get("model")})
    for g, prof in profiled(objs):
        if not prof.required:
            continue
        if not any(None in gateway_targets(p, g) and ((spec_of(p).get("frontend") or {}).get("http") or {})
                   .get("maxBufferSize") for p in policies(objs)):
            out.append(f"AG14: no Gateway-scoped frontend policy on {ref(g)} sets http.maxBufferSize: the model rule "
                       "would read 2 MiB of a body the backend reads up to 32 MiB of")
        for r in routes_on(objs, g):
            covering = {}
            for p in policies(objs):
                authz = (spec_of(p).get("traffic") or {}).get("authorization")
                if authz is None or meta(p).get("namespace") != meta(r).get("namespace"):
                    continue
                for t in spec_of(p).get("targetRefs") or []:
                    if t.get("kind") == r.get("kind") and t.get("name") == meta(r).get("name"):
                        covering.setdefault(t.get("sectionName"), []).append((p, authz))
            answered = {t.get("sectionName") for p in policies(objs)
                        if "directResponse" in (spec_of(p).get("traffic") or {})
                        for t in spec_of(p).get("targetRefs") or []
                        if t.get("kind") == r.get("kind") and t.get("name") == meta(r).get("name")}
            for rule in spec_of(r).get("rules") or []:
                name = rule.get("name")
                if not backend_refs(r, {name}) & llm:
                    continue
                found = covering.get(name, []) + covering.get(None, [])
                if name in answered or None in answered:
                    for p, authz in found:
                        if "request.body" in json.dumps(authz):
                            out.append(f"AG14: {ref(p)} reads the body on {ref(r)} rule {name}, which a directResponse "
                                       "answers: its GET would be refused 403 before its 404")
                    continue
                for listener in sorted(listeners_of(r, g)):
                    if len(found) != 1:
                        out.append(f"AG14: {ref(r)} rule {name} on {listener} has {len(found)} route-level "
                                   "authorization policies, expected 1 (gen-capabilities.py renders it)")
                        continue
                    p, authz = found[0]
                    exprs = (authz.get("policy") or {}).get("matchExpressions") or []
                    if authz.get("action") != "Require" or sub_prefix(prof) not in exprs:
                        out.append(f"AG14: {ref(p)} must Require {sub_prefix(prof)}: the listener's rule, repeated")
                    rules = [e for e in exprs if e.startswith(EFFECTIVE_MODEL)]
                    if len(rules) != 1 or not model_rule_ok(rules[0], sorted(audiences(prof, listener))):
                        out.append(f"AG14: {ref(p)} needs one model Require over {EFFECTIVE_MODEL} with an alternative "
                                   f"for each of {sorted(audiences(prof, listener))}")
                        continue
                    for alt in ALTERNATIVE.finditer(rules[0]):
                        missing = [x for x in pinned if x not in json.loads(alt["models"])]
                        if missing:
                            out.append(f"AG14: {ref(p)} refuses {missing} to {alt['aud']}, which the factory's tiers "
                                       "pin: every such run would be refused at its first call")
    return out
```

and replace the end of `CHECKS`:

```python
          check_meter_prices, check_provider_paths, check_model_pinning, check_github_route)
```

with:

```python
          check_meter_prices, check_provider_paths, check_model_pinning, check_github_route, check_model_authz)
```

- [ ] **Step 4: Run the gate's test, then the gate on the bundle**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/host-profile.sh
bash $SCRATCH/run-suite.sh python3 .composite/scripts/ci/tests/flux-schema/test-assert-agent-gateway.py | grep -v '^  ok'
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|passed,|exit=" "$SCRATCH/check-$(basename "$PWD").log"
```

Expected: section headers and `all passed`; then
`assert-agent-gateway: 15 checks, 0 violations (clusters: aws-0, gcp-0)`, `… 0 failed`, `exit=0`.
With `policy-capabilities.yaml` dropped from `kustomization.yaml`, AG14 reports `has 0 route-level`
for the four LLM rules.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/flux-schema/assert-agent-gateway.py scripts/ci/tests/flux-schema/test-assert-agent-gateway.py
git commit -m "feat(ci): AG14, every model route of the agent router carries the profiles' rule"
```

---

### Task 4: The wire test on the pinned image (gate item 1, offline)

**Files:**
- Create: `scripts/ci/tests/test-agent-capabilities-wire.sh` (mode 755)

**Interfaces:**
- Consumes: `gen-capabilities.py --write ROOT` (Task 2); `policy-capabilities.yaml`'s
  `capabilities-internal` with `targetRefs[].sectionName`; `anthropic.yaml`'s backend and
  `agentgateway-models-internal` route; `policies-identity.yaml`'s `listener-internal`;
  `parameters.yaml`'s image.
- Produces (Task 9 extends it): the shell functions `call <port> <path> <aud-or-empty> <body model>
  [x-ar-model]` printing `<status> <upstream model or ->`, `expect <what> <want> <got>`, `free_port`;
  the variables `tmp`, `gw`, `gw_port`, `fake_pid`, `R` (`agent-router.reviewer.internal`); the
  trailing `[ "$fails" -eq 0 ] … PASS` block.

- [ ] **Step 1: Write the test**

`scripts/ci/tests/test-agent-capabilities-wire.sh`:

```bash
#!/usr/bin/env bash
# requires: docker python3 curl openssl
#
# The capability profiles' model rules on the pinned agentgateway (design P2, P4; gate items 1 and 3).
# The generator renders policy-capabilities.yaml from a copy of the profiles in which
# reviewer.internal may call tier-standard and tier-light only; the proxy image parameters.yaml pins
# then serves anthropic.yaml's backend policy and that rendering, standalone, against a fake
# Anthropic upstream that records the model it is asked for. agentgateway 1.6 has no
# llm.requestModel where a route's authorization runs, so a rule written on it refuses every call:
# a grammar gate cannot see that, a request can. Standalone proves the data plane, not the
# controller's translation of the CRDs; the live gate does.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
if ! docker info >/dev/null 2>&1; then
  if [ "${CI:-}" = "true" ]; then
    echo "FAIL  no docker daemon in CI: this is the capability profiles' offline proof and must run here"; exit 1
  fi
  echo "SKIP: no docker daemon"; exit 77
fi

tmp="$(mktemp -d)"
# The containers run as their images' own users and read this directory at the same path.
chmod 755 "$tmp"
gw="agent-capabilities-wire-gw-$$"
fake_pid=""
trap 'docker rm -f "$gw" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; rm -rf "$tmp"' EXIT
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'; }
up_port="$(free_port)"; gw_port="$(free_port)"; gw_admin="$(free_port)"; gw_ready="$(free_port)"; gw_stats="$(free_port)"

# --- The run tokens: an RSA key, its JWKS, one token per audience, signed with openssl. ---
openssl genrsa -out "$tmp/key.pem" 2048 2>/dev/null
openssl rsa -in "$tmp/key.pem" -noout -modulus > "$tmp/modulus" 2>/dev/null
TMP="$tmp" python3 - <<'PY'
import base64, json, os, subprocess, time
tmp = os.environ["TMP"]
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
n = int(open(f"{tmp}/modulus").read().strip().split("=", 1)[1], 16)
json.dump({"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256", "use": "sig",
                     "n": b64(n.to_bytes((n.bit_length() + 7) // 8, "big")), "e": "AQAB"}]}, open(f"{tmp}/jwks.json", "w"))
for aud in ("agent-router.reviewer.internal", "agent-router.implementer.internal"):
    head = b64(json.dumps({"alg": "RS256", "kid": "k1", "typ": "JWT"}).encode())
    body = b64(json.dumps({"iss": "https://issuer.test", "aud": [aud], "exp": int(time.time()) + 3600,
                           "sub": "system:serviceaccount:agents:xplane-run-wiretest"}).encode())
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", f"{tmp}/key.pem"], input=f"{head}.{body}".encode(),
                         capture_output=True, check=True).stdout
    open(f"{tmp}/{aud}.jwt", "w").write(f"{head}.{body}.{b64(sig)}")
PY
chmod 644 "$tmp"/*

# --- The rendering under test: reviewer.internal narrowed to two aliases, the rest as committed. ---
mkdir -p "$tmp/root/infrastructure/base" "$tmp/root/scripts/ci"
cp -a "$ROOT/infrastructure/base/agent-gateway" "$tmp/root/infrastructure/base/"
cp "$ROOT/scripts/ci/gen-capabilities.py" "$tmp/root/scripts/ci/"
prof="$tmp/root/infrastructure/base/agent-gateway/profiles/reviewer.internal.yaml"
sed -i 's/^models: .*/models: [tier-standard, tier-light]/' "$prof"
grep -q '^models: \[tier-standard, tier-light\]$' "$prof" || { echo "cannot narrow $prof" >&2; exit 1; }
python3 "$tmp/root/scripts/ci/gen-capabilities.py" --write "$tmp/root" >/dev/null || { echo "the generator refused the test profile" >&2; exit 1; }

cat > "$tmp/fake.py" <<'PY'
"""Stands in for api.anthropic.com: records the path, the model and x-ar-model of each request."""
import http.server, json, sys
PORT, OUT = int(sys.argv[1]), sys.argv[2]
class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "model": body.get("model"), "pin": self.headers.get("x-ar-model")}) + "\n")
        reply = json.dumps({"id": "msg_test", "type": "message", "role": "assistant", "model": body.get("model"),
                            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
                            "usage": {"input_tokens": 10, "output_tokens": 1}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
PY
python3 "$tmp/fake.py" "$up_port" "$tmp/upstream.jsonl" & fake_pid=$!

# --- The gateway: the internal listener's JWT, its model route's three rules, anthropic.yaml's backend
#     policy and the rendered capabilities-internal, as the controller would attach them. ---
image="$(ROOT="$ROOT" TMP="$tmp" PORTS="$gw_port $gw_admin $gw_ready $gw_stats $up_port" python3 - <<'PY'
import os
import yaml

root, tmp = os.environ["ROOT"], os.environ["TMP"]
port, admin, ready, stats, upstream = os.environ["PORTS"].split()
def docs(path):
    return [d for d in yaml.safe_load_all(open(path)) if d]
gw = f"{tmp}/root/infrastructure/base/agent-gateway"
params = next(d for d in docs(f"{root}/infrastructure/base/agent-gateway/parameters.yaml")
              if d["kind"] == "AgentgatewayParameters")["spec"]["image"]
anthropic = docs(f"{gw}/anthropic.yaml")
backend = next(d for d in anthropic if d["kind"] == "AgentgatewayBackend")["spec"]["policies"]["ai"]
route = next(d for d in anthropic if d["kind"] == "HTTPRoute" and d["metadata"]["name"] == "agentgateway-models-internal")
listener = next(d for d in docs(f"{gw}/policies-identity.yaml") if d["metadata"]["name"] == "listener-internal")
caps = next(d for d in docs(f"{gw}/policy-capabilities.yaml") if d["metadata"]["name"] == "capabilities-internal")
authz = {t["sectionName"]: caps["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]
         for t in caps["spec"]["targetRefs"]}
direct = {t["sectionName"]: d["spec"]["traffic"]["directResponse"] for d in anthropic
          if d["kind"] == "AgentgatewayPolicy" for t in d["spec"]["targetRefs"]}
ai = {"name": "anthropic", "provider": {"anthropic": {}}, "hostOverride": f"127.0.0.1:{upstream}",
      "policies": {"ai": {"routes": {p: k.lower() for p, k in backend["routes"].items()},
                          "modelAliases": backend["modelAliases"],
                          "transformations": {t["field"]: t["expression"] for t in backend["transformations"]}}}}
routes = []
for rule in route["spec"]["rules"]:
    match = rule["matches"][0]["path"]
    policies = {"backendAuth": {"key": "test-key"}}
    if rule["name"] in authz:
        policies["authorization"] = {"rules": [{"require": e} for e in authz[rule["name"]]]}
    if rule["name"] in direct:
        policies["directResponse"] = direct[rule["name"]]
    routes.append({"name": rule["name"],
                   "matches": [{"path": {"exact" if match["type"] == "Exact" else "pathPrefix": match["value"]}}],
                   "policies": policies, "backends": [{"ai": ai}]})
jwt = listener["spec"]["traffic"]["jwtAuthentication"]["providers"][0]
config = {
    "config": {"adminAddr": f"127.0.0.1:{admin}", "readinessAddr": f"127.0.0.1:{ready}", "statsAddr": f"127.0.0.1:{stats}"},
    "binds": [{"port": int(port), "listeners": [{"protocol": "HTTP", "policies": {"jwtAuth": {
        "mode": "strict", "providers": [{"issuer": "https://issuer.test", "audiences": jwt["audiences"],
                                         "jwks": {"file": f"{tmp}/jwks.json"}}]}},
        "routes": routes}]}],
}
yaml.safe_dump(config, open(f"{tmp}/gateway.yaml", "w"), sort_keys=False)
print("%s/%s:%s@%s" % (params["registry"], params["repository"], params["tag"], params["digest"]))
PY
)" || { echo "cannot render the gateway config" >&2; exit 1; }
chmod 644 "$tmp/gateway.yaml"
docker run -d --name "$gw" --network host -v "$tmp:$tmp:ro" "$image" -f "$tmp/gateway.yaml" >/dev/null \
  || { echo "cannot start $image" >&2; exit 1; }

fails=0
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }
# call <port> <path> <aud> <body model> [x-ar-model]: prints "<status> <upstream model or ->".
call() {
  : > "$tmp/upstream.jsonl"
  local pin=()
  [ -n "${5:-}" ] && pin=(-H "x-ar-model: $5")
  local tok=()
  [ -n "$3" ] && tok=(-H "authorization: Bearer $(cat "$tmp/$3.jwt")")
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$1$2" "${tok[@]}" "${pin[@]}" \
    -H 'content-type: application/json' -d "{\"model\": \"$4\", \"max_tokens\": 8, \"messages\": [{\"role\": \"user\", \"content\": \"hi\"}]}")"
  echo "$code $(python3 -c 'import json,sys; l=open(sys.argv[1]).read().splitlines(); print(json.loads(l[-1])["model"] if l else "-")' "$tmp/upstream.jsonl")"
}
expect() {  # expect <what> <want> <got>
  [ "$2" = "$3" ] && echo "ok    $1" || fail "$1: want '$2', got '$3'"
}

ready=""
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Running}}' "$gw" 2>/dev/null)" != "true" ]; then
    docker logs "$gw" 2>&1 | tail -30 >&2; echo "the gateway container exited before it answered" >&2; exit 1
  fi
  [ "$(call "$gw_port" /v1/chat/completions agent-router.reviewer.internal tier-standard | cut -d' ' -f1)" = 200 ] && { ready=1; break; }
  sleep 1
done
[ -n "$ready" ] || { docker logs "$gw" 2>&1 | tail -30 >&2; echo "the gateway never answered 200" >&2; exit 1; }

R=agent-router.reviewer.internal
echo "the gateway alone (P2, P4's gateway half)"
expect "a model the profile names reaches its alias" "200 claude-sonnet-5-5" "$(call "$gw_port" /v1/chat/completions $R tier-standard)"
expect "a model it does not name is refused 403, upstream untouched (gate 1)" "403 -" "$(call "$gw_port" /v1/chat/completions $R tier-frontier)"
expect "the Messages route holds the same rule" "403 -" "$(call "$gw_port" /anthropic/v1/messages $R tier-frontier)"
expect "x-ar-model wins over the body" "200 claude-haiku-5-5" "$(call "$gw_port" /v1/chat/completions $R tier-frontier tier-light)"
expect "a pinned model the profile does not name is refused" "403 -" "$(call "$gw_port" /v1/chat/completions $R tier-standard tier-frontier)"
expect "another role keeps its own list" "200 claude-opus-5-5" "$(call "$gw_port" /v1/chat/completions agent-router.implementer.internal tier-frontier)"
expect "an unknown name is refused before the transformation's 400" "403 -" "$(call "$gw_port" /v1/chat/completions $R gpt-9)"
expect "no token is still 401" "401 -" "$(call "$gw_port" /v1/chat/completions "" tier-standard)"
models="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$gw_port/v1/models" -H "authorization: Bearer $(cat "$tmp/$R.jwt")")"
expect "/v1/models keeps its 404: the rule does not target it" "404" "$models"
docker logs "$gw" 2>&1 | grep 'http.status=403' | grep -q 'jwt.sub=system:serviceaccount:agents:xplane-run-wiretest' \
  && echo "ok    a refusal's access log names the run (gate 1)" || fail "no 403 access log line names jwt.sub"

[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
```

- [ ] **Step 2: Run it**

```bash
chmod +x scripts/ci/tests/test-agent-capabilities-wire.sh
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities-wire.sh; echo "exit=$?"
```

Expected without Docker: `SKIP: no docker daemon`, `exit=77`. With Docker (or the shim below):
ten `ok` lines, `PASS`, `exit=0`. It is a new behaviour test, so it passes on its first run; its
controls are below.

To run it without Docker, put a `docker` shim first on `PATH` that maps `run -d --name N --network
host [-e K=V]… -v … IMAGE ARGS` to the agentgateway v1.6.0 or Envoy v1.39.1 binary (by image name)
with that environment, and `info`, `inspect`, `logs`, `rm -f` to the process; the planning prototype's
is `$SCRATCH/p2p4/shim/docker`. Controls run that way: with `EFFECTIVE_MODEL` set to
`llm.requestModel` in the generator the test ends `the gateway never answered 200`; with today's
transformation in `anthropic.yaml` it fails `x-ar-model wins over the body`.

- [ ] **Step 3: Commit**

```bash
git add scripts/ci/tests/test-agent-capabilities-wire.sh
git commit -m "test(agent-gateway): the profiles' model rules on the pinned agentgateway"
```

---

### Task 5: The gateways page and the spec

**Files:**
- Modify: `website/content/docs/platform/ai-platform/gateways.md`
- Modify: `docs/superpowers/specs/2026-10-21-capability-profiles-design.md`

- [ ] **Step 1: The gateways page**

In the Identity table of `gateways.md`, replace:

```markdown
| `sub` starts with `system:serviceaccount:agents:` | the listener's `authorization` rule | 403 |
```

with:

```markdown
| `sub` starts with `system:serviceaccount:agents:` | the listener's `authorization` rule | 403 |
| The model the call reaches is one the caller's profile names | `capabilities-<listener>` on the model routes (`policy-capabilities.yaml`) | 403 |
```

After the paragraph that ends `profile and its expected set in \`test-agent-mcp-scope\` (then \`--write\`).`,
add:

```markdown

The models are generated the same way. A profile's `models` lists the aliases its role may call, and
the generator renders one route-level `authorization` per listener into `policy-capabilities.yaml`,
on the model routes but not `/v1/models`. A call whose model the caller's profile does not name is
refused 403 before any upstream call, and the access log names the run. The model is `x-ar-model`
when the run's identity proxy set it, else the body's, the same choice the backends' `model`
transformation makes. Every profile lists the four aliases today, so the rule binds nothing until a
role moves to its own size: narrowing a profile is the switch, and gate AG14 refuses one that would
refuse a model the factory's tiers pin.
```

- [ ] **Step 2: The spec**

In the status line, replace:

```markdown
2026-10-22**: the migration's first step, the profiles and a generator at parity, is built
([plan](../plans/2026-10-22-capability-profiles-p1-plan.md)) · **Part of:** the
```

with:

```markdown
2026-10-22**: the migration's first step, the profiles and a generator at parity, is built
([plan](../plans/2026-10-22-capability-profiles-p1-plan.md)); P2 and the gateway's half of P4 are
built ([plan](../plans/2026-10-22-capability-profiles-p2-p4-plan.md)) · **Part of:** the
```

At the end of the file, append:

```markdown

Ruled in P2 and P4 ([plan](../plans/2026-10-22-capability-profiles-p2-p4-plan.md#this-plans-rulings)):

- **The rule reads the model itself.** agentgateway 1.6 has no `llm.requestModel` where a route's
  `authorization` runs (the backend parses the body later): a Require on it refused every call. The
  rule binds `("x-ar-model" in request.headers ? request.headers["x-ar-model"] :
  json(request.body).model)` and requires, for the caller's audience, that it is in the profile's
  `models`: one Require per listener, the roles OR-ed. The backends' `model` transformation makes the
  same choice, header first, and gate AG12 refuses any object that removes the header, since the
  two would then disagree.
- **Authorization adds up in 1.6**: a route's rules join the listener's rather than replacing them.
  The listener's Require is repeated anyway, and gate AG14 asserts it with the rest of the rule.
- **The gateway does not strip `x-ar-model`.** It would strip the proxy's value too; the proxy
  overwrites the harness's, and only the proxy holds a run token.
- **A 403 on a model call is acceptable**: it is a single stateless request, which the harness does
  not retry, and it ends the conversation as today's 400 for an unknown name does. The refusal's
  access log names the run's `sub`, so gate item 1's attribution holds in 1.6.0; #3996 concerns the
  model router's own 403.
- **The judge path refuses until the claim names a judge**: the composition sets `JUDGE_MODEL` to
  `spec.loop.judgeModel`, else `none`, which no profile names.
- **P3 and S0:** OpenHands SDK 1.55 fixes the disconnect S0 measured (measured 2026-10-22 against
  1.56.0 by the SDK upgrade plan): a route-level 403 for P3's argument constraints becomes possible
  once the harness ships an SDK at 1.55 or later, which P3 then depends on.
```

- [ ] **Step 3: Check the links**

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/validate-links.sh
```

Expected: `==> All relative Markdown links resolve`. The site build and the doc-path check run in
Task 6.

- [ ] **Step 4: Commit**

```bash
git add website/content/docs/platform/ai-platform/gateways.md docs/superpowers/specs/2026-10-21-capability-profiles-design.md
git commit -m "docs(agent-gateway): the profiles' model rules"
```

---

### Task 6: Verify, push, open PR A

- [ ] **Step 1: The whole check**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|test-gen-capabilities|test-agent-capabilities|mcp-scope|test-assert-agent-gateway|passed,|resolve|docs site exists|exit=" \
  "$SCRATCH/check-$(basename "$PWD").log"
```

Expected:
- `assert-agent-gateway: 15 checks, 0 violations (clusters: aws-0, gcp-0)`
- `PASS` for `test-gen-capabilities`, `test-agent-capabilities`, `test-agent-mcp-scope` and
  `flux-schema/test-assert-agent-gateway`; `SKIP  test-agent-capabilities-wire  SKIP: no docker
  daemon` without Docker
- `28 passed, 3 skipped, 0 failed` on today's main (28 passed and 2 skipped before; this PR adds
  one suite, skipped without Docker). Other merges may change the counts: what must hold is
  `0 failed`.
- `All relative Markdown links resolve`, `Every repository path named in the docs site exists`,
  `exit=0`

- [ ] **Step 2: Rebase and push**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/capability-profiles-p2-p4
```

If the rebase touched a file this PR changes, run Step 1 again before pushing.

- [ ] **Step 3: Open the pull request**

Title: `feat(agent-gateway): capability profiles P2, per-role model rules, and the gateway's half of the model pin`.
The body, in English: the outcome (a role can call only its profile's aliases, 403, the access log
names the run; the backends take `x-ar-model` first; nothing narrows yet); the measurements behind
R1, R2, R6 and R7; rulings R1–R14; the suites and gates; what waits (PR X, PR H, PR B; the live
gate items in the next gcp-0 session); the `task check` summary; a test plan (a hand edit to
`policy-capabilities.yaml` fails `test-agent-capabilities`; CI shows
`PASS  test-agent-capabilities-wire`). No attribution line.

- [ ] **Step 4: Wait for CI and read the wire test**

```bash
gh pr checks --watch
gh run view --log "$(gh run list --branch feat/capability-profiles-p2-p4 -L 1 --json databaseId -q '.[0].databaseId')" | grep -E "test-agent-capabilities-wire|passed,"
```

Expected: every check green, and `PASS  test-agent-capabilities-wire` (CI runs with Docker).

---

## PR X — crossplane-configuration: the proxy's environment and the judge's claim field

### Task 7: `spec.loop.judgeModel`, `MODEL` and `JUDGE_MODEL`

**Files** (crossplane-configuration):
- Modify: `apis/agentrun/definition.yaml`, `apis/agentrun/kcl/main.k`
- Regenerate: `apis/agentrun/composition.yaml`
- Modify: `examples/agentrun-complete.yaml`, `tests/golden/agentrun-basic.yaml`,
  `agentrun-complete.yaml`, `agentrun-internal.yaml`, `agentrun-suspendable.yaml`
- Test: `apis/agentrun/kcl/main_test.k`

**Interfaces:**
- Consumes: nothing from PR A (the variables are inert until PR B's bootstrap reads them).
- Produces (PR B relies on it): the identity-proxy container's `env`, exactly
  `[{name: MODEL, value: <spec.model or agent-default>}, {name: JUDGE_MODEL, value:
  <spec.loop.judgeModel or none>}]`; the claim field `spec.loop.judgeModel`, an enum of the four
  aliases. The loop policy's composition step adds `stallSteps`, `continuations` and the harness's
  variables to `spec.loop`.

- [ ] **Step 1: The worktree**

```bash
git -C /home/smana/Sources/crossplane-configuration fetch origin
git -C /home/smana/Sources/crossplane-configuration worktree add /home/smana/Sources/crossplane-configuration-model-pin -b feat/agentrun-model-pin origin/main
cd /home/smana/Sources/crossplane-configuration-model-pin && mise trust mise.toml
```

- [ ] **Step 2: Write the failing test**

In `apis/agentrun/kcl/main_test.k`, replace:

```kcl
    assert _proxy.args == ["-c", "/etc/envoy/envoy.yaml", "--log-level", "warn", "--disable-hot-restart", "--concurrency", "1"]
}
```

with:

```kcl
    assert _proxy.args == ["-c", "/etc/envoy/envoy.yaml", "--log-level", "warn", "--disable-hot-restart", "--concurrency", "1"]
}

# ---- P4 (ai-native-ref capability profiles): the proxy pins the run's model and the judge's ----
_proxyEnv = lambda spec: any -> any {
    {e.name: e.value for e in _pod(_run(spec)).initContainers[0].env}
}

test_proxy_pins_the_run_model = lambda {
    assert _proxyEnv({}) == {MODEL = "agent-default", JUDGE_MODEL = "none"}, "the claim's default model, and no judge path until the claim names a judge"
    assert _proxyEnv({model = "tier-frontier", loop = {judgeModel = "tier-light"}}) == {MODEL = "tier-frontier", JUDGE_MODEL = "tier-light"}
    _harness = {e.name: e.value for e in _pod(_run({model = "tier-frontier"})).containers[0].env}
    assert _harness.MODEL == "tier-frontier", "the harness asks for the model the proxy pins"
    assert "JUDGE_MODEL" not in _harness, "the loop policy's composition step gives the harness its judge"
}
```

- [ ] **Step 3: Run it and watch it fail**

```bash
cd apis/agentrun/kcl && kcl test . -Y settings-example.yaml 2>&1 | grep -E 'test_proxy_pins|PASS:|FAIL:'; cd -
```

Expected: `test_proxy_pins_the_run_model: FAIL`, `FAIL: 1/109`.

- [ ] **Step 4: The composition**

In `apis/agentrun/kcl/main.k`, replace:

```kcl
    _model = _spec.model or "agent-default"
```

with:

```kcl
    _model = _spec.model or "agent-default"

    # P4 (ai-native-ref capability profiles design): the identity proxy sets x-ar-model from MODEL on
    # every model path and from JUDGE_MODEL on /judge/v1, over any value the harness sends. `none`
    # names no alias, so the gateway refuses the judge path until the claim names a judge.
    _judgeModel = _spec.loop?.judgeModel or "none"
```

and in the identity-proxy container, replace:

```kcl
                        args = ["-c", "/etc/envoy/envoy.yaml", "--log-level", "warn", "--disable-hot-restart", "--concurrency", "1"]
```

with:

```kcl
                        args = ["-c", "/etc/envoy/envoy.yaml", "--log-level", "warn", "--disable-hot-restart", "--concurrency", "1"]
                        # Read by the proxy's bootstrap as %ENVIRONMENT(MODEL)% and %ENVIRONMENT(JUDGE_MODEL)%
                        # (ai-native-ref agent-runtime/identity-proxy-configmap.yaml).
                        env = [
                            {name = "MODEL", value = _model}
                            {name = "JUDGE_MODEL", value = _judgeModel}
                        ]
```

- [ ] **Step 5: The XRD**

In `apis/agentrun/definition.yaml`, replace:

```yaml
                  message: "suspendable is immutable and cannot be added or removed after creation"
```

with:

```yaml
                  message: "suspendable is immutable and cannot be added or removed after creation"
                - rule: "has(self.loop) == has(oldSelf.loop) && (!has(self.loop) || self.loop == oldSelf.loop)"
                  message: "loop is immutable and cannot be added or removed after creation"
```

and replace:

```yaml
                dataClass:
                  description: |
```

with:

```yaml
                loop:
                  description: >-
                    The run's loop policy (ai-native-ref loops design L2). judgeModel is the alias the
                    completion judge calls through the identity proxy's /judge/v1 path, which the proxy pins to
                    it (capability profiles P4); unset, the gateway refuses that path.
                  type: object
                  properties:
                    judgeModel:
                      type: string
                      enum: [agent-default, tier-light, tier-standard, tier-frontier]
                dataClass:
                  description: |
```

- [ ] **Step 6: The example and the goldens**

In `examples/agentrun-complete.yaml` (every field), replace:

```yaml
  model: tier-standard
```

with:

```yaml
  model: tier-standard
  loop:
    judgeModel: tier-light
```

`crossplane render` writes keys sorted, so the proxy's `env` lands between `args` and `image`. In
each of the four goldens, replace:

```yaml
        - --concurrency
        - "1"
        image: docker.io/envoyproxy/envoy:
```

with the lines below, `MODEL` and `JUDGE_MODEL` being `agent-default`/`none` in
`agentrun-basic.yaml`, `agentrun-internal.yaml` and `agentrun-suspendable.yaml`, and
`tier-standard`/`tier-light` in `agentrun-complete.yaml`:

```yaml
        - --concurrency
        - "1"
        env:
        - name: MODEL
          value: agent-default
        - name: JUDGE_MODEL
          value: none
        image: docker.io/envoyproxy/envoy:
```

- [ ] **Step 7: Generate and run the checks**

```bash
(cd apis/agentrun/kcl && kcl fmt .) && task generate && git add apis/agentrun
task generate-sync test schema 2>&1 | grep -E 'test_proxy_pins|PASS:|FAIL|REJECTED|valid against' ; echo "exit=${PIPESTATUS[0]}"
```

`generate-sync` and the fmt check compare the tree with the index, hence the `git add` (`kcl fmt` must
change nothing in the text above: it was checked fmt-clean). Expected: `test_proxy_pins_the_run_model: PASS`, `PASS: 109/109` for agentrun,
`REJECTED settings-reject-internal-egress.yaml`, `25 example claim(s) valid`, `exit=0`.
`task render` needs Docker: if none runs here, prove the goldens with `kcl run` instead, which is
how they were proven when planning (the script below; it compares the identity-proxy container
only, the part this task changes):

```bash
cat > "$SCRATCH/golden_check.py" <<'PY'
"""golden_check.py <xpc-root>: renders each AgentRun example through main.k with `kcl run` (crossplane render needs
Docker here) and compares the identity-proxy container with the golden's, field for field."""
import pathlib, subprocess, sys, tempfile, yaml
root = pathlib.Path(sys.argv[1])
fails = 0
for ex in sorted((root / "examples").glob("agentrun-*.yaml")):
    claim = next(d for d in yaml.safe_load_all(ex.read_text()) if d)
    dxr = {"apiVersion": claim["apiVersion"], "kind": claim["kind"], "metadata": {"name": claim["metadata"]["name"], "namespace": "agents"}}
    settings = {"kcl_options": [{"key": "params", "value": {"oxr": claim, "ocds": {}, "dxr": dxr}}]}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(settings, f)
    out = subprocess.run(["kcl", "run", "main.k", "-Y", f.name], cwd=root / "apis/agentrun/kcl", capture_output=True, text=True)
    if out.returncode:
        print("ERROR", ex.name, out.stderr[-300:]); fails += 1; continue
    items = yaml.safe_load(out.stdout)["items"]
    got = next(c for i in items if i.get("kind") == "Sandbox" for c in i["spec"]["podTemplate"]["spec"]["initContainers"] if c["name"] == "identity-proxy")
    gold = next(c for d in yaml.safe_load_all((root / "tests/golden" / ex.name).read_text()) if d and d.get("kind") == "Sandbox"
                for c in d["spec"]["podTemplate"]["spec"]["initContainers"] if c["name"] == "identity-proxy")
    ok = got == gold
    fails += not ok
    print("MATCH " if ok else "DIFFER", ex.name, got.get("env"))
sys.exit(1 if fails else 0)
PY
python3 "$SCRATCH/golden_check.py" .
```

Expected: four `MATCH` lines. CI runs `task render` on every golden.

- [ ] **Step 8: Commit, push, open PR X**

```bash
git add apis/agentrun/definition.yaml apis/agentrun/kcl/main.k apis/agentrun/kcl/main_test.k apis/agentrun/composition.yaml \
  examples/agentrun-complete.yaml tests/golden/agentrun-basic.yaml tests/golden/agentrun-complete.yaml \
  tests/golden/agentrun-internal.yaml tests/golden/agentrun-suspendable.yaml
git commit -m "feat(agentrun): the identity proxy pins the run's model and the judge's (capability profiles P4)"
git fetch origin && git rebase origin/main && git push -u origin feat/agentrun-model-pin
```

Title: the commit's subject. Body: the outcome (the proxy gets `MODEL` and `JUDGE_MODEL`;
`spec.loop.judgeModel`, `none` without it), why `none` (R8), that the variables are inert until
ai-native-ref's bootstrap reads them (R11), the checks run, and that `spec.loop` will carry the loop
policy's other fields. No attribution line. Wait for CI: `task render` must `MATCH` all four
goldens.

- [ ] **Step 9: Release** (the owner's step)

After the merge, the owner tags the next release (`v0.9.17` if none came between; the tag the
release really gets is the one PR H pins):

```bash
git -C /home/smana/Sources/crossplane-configuration fetch origin
git -C /home/smana/Sources/crossplane-configuration tag v0.9.17 origin/main && git -C /home/smana/Sources/crossplane-configuration push origin v0.9.17
```

---

## PR H — cloud-native-ref: the host runs the release

### Task 8: Pin the release

**Files** (cloud-native-ref): `infrastructure/base/crossplane/configuration-core/configuration-core.yaml`,
`infrastructure/base/crossplane/configuration-aws/configuration-packages.yaml`,
`infrastructure/base/crossplane/configuration-gcp/configuration-packages.yaml`,
`apps/platform/app-wizard/app.yaml` (its `--branch=` clone tag; crossplane-configuration's CLAUDE.md
asks that both move together).

- [ ] **Step 1: The worktree and the bump**

```bash
git -C /home/smana/Sources/cloud-native-ref fetch origin
git -C /home/smana/Sources/cloud-native-ref worktree add /home/smana/Sources/cloud-native-ref-xpc-model-pin -b chore/crossplane-configuration-model-pin origin/main
cd /home/smana/Sources/cloud-native-ref-xpc-model-pin
grep -rn 'crossplane-configuration-.*:v0\.9\.\|--branch=v0\.9\.' infrastructure/base/crossplane apps/platform/app-wizard/app.yaml
```

Replace the version every line found names (`v0.9.15` when planned) with the release of Task 7
Step 9, in all four files. Run the host's own checks as its AGENTS.md says, then commit
`chore(deps): pin crossplane-configuration v0.9.17, the identity proxy's model pin`, push, open the PR
(body: it carries `spec.loop.judgeModel` and the proxy's `MODEL` and `JUDGE_MODEL`, inert until
ai-native-ref's next bootstrap). No attribution line.

- [ ] **Step 2: Applied on the clusters**

After the merge, on each running cluster (gcp-0 when up; aws-0 renders the same pin):

```bash
kubectl get configurations.pkg.crossplane.io -o custom-columns=NAME:.metadata.name,PACKAGE:.spec.package,HEALTHY:.status.conditions[?\(@.type==\"Healthy\"\)].status
```

Expected: the three packages at the new tag, `True`. With no cluster up, the pin applies at the
next creation, before any run: PR B may merge.

---

## PR B — ai-native-ref: the proxy pins the model

### Task 9: The bootstrap's pin, its suites and docs

**Files:**
- Modify: `HOST_REF` (cloud-native-ref `main`, holding PR H)
- Modify: `infrastructure/base/agent-runtime/identity-proxy-configmap.yaml`
- Create: `scripts/ci/tests/test-identity-proxy-model-pin.py`
- Modify: `scripts/ci/tests/test-agent-capabilities-wire.sh` (a proxy section)
- Modify: `website/content/docs/platform/ai-platform/gateways.md`, `agents/runtime.md`,
  `docs/superpowers/specs/2026-10-21-capability-profiles-design.md` (status)

**Interfaces:**
- Consumes: the proxy's `MODEL` and `JUDGE_MODEL` (Task 7, applied by PR H); Task 4's functions and
  variables.
- Produces: the bootstrap routes `/v1/`, `/anthropic/` (`x-ar-model` from `MODEL`) and `/judge/v1/`
  (from `JUDGE_MODEL`, rewritten to `/v1/`) on both model listeners.

- [ ] **Step 1: The worktree**

```bash
git -C /home/smana/Sources/ai-native-ref fetch origin
git -C /home/smana/Sources/ai-native-ref worktree add /home/smana/Sources/ai-native-ref/.claude/worktrees/p4-pin -b feat/capability-profiles-p4-pin origin/main
cd /home/smana/Sources/ai-native-ref/.claude/worktrees/p4-pin && mise trust mise.toml
git -C /home/smana/Sources/cloud-native-ref fetch origin
pin="$(git -C /home/smana/Sources/cloud-native-ref log -1 --format=%H origin/main -- infrastructure/base/crossplane/configuration-core/configuration-core.yaml)"
git -C /home/smana/Sources/cloud-native-ref log -1 --format=%s "$pin"
git -C /home/smana/Sources/cloud-native-ref rev-parse origin/main > HOST_REF
git -C /home/smana/Sources/cloud-native-ref merge-base --is-ancestor "$pin" "$(cat HOST_REF)" && echo "HOST_REF holds PR H"
```

Expected: PR H's subject (`chore(deps): pin crossplane-configuration …`), then `HOST_REF holds PR H`.
`HOST_REF` moves to the host's current `main`, never behind the commit it held.

- [ ] **Step 2: Write the failing static suite**

`scripts/ci/tests/test-identity-proxy-model-pin.py`:

```python
#!/usr/bin/env python3
# requires: python3
"""Every route of the identity proxy that reaches the agent router's model routes pins the model.

Capability profiles design, P4: the proxy sets x-ar-model on every path the gateway serves a model
on, over any value the harness sends, so a run calls the alias it was created with: from MODEL on
/v1/ and /anthropic/, from JUDGE_MODEL on /judge/v1/, which it rewrites to /v1/. A new prefix to the
router without the header would be a way around the pin, and the wire test only probes the three it
knows; this reads them all. /mcp and /github/ carry no model. The real tree."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIGMAP = ROOT / "infrastructure/base/agent-runtime/identity-proxy-configmap.yaml"
NO_MODEL = ("/mcp", "/github/")
WANT = {"/v1/": ("MODEL", None), "/anthropic/": ("MODEL", None), "/judge/v1/": ("JUDGE_MODEL", "/v1/")}

fails = []
cm = next(d for d in yaml.safe_load_all(CONFIGMAP.read_text()) if d and d.get("kind") == "ConfigMap")
envoy = yaml.safe_load(cm["data"]["envoy.yaml"])
for listener in envoy["static_resources"]["listeners"]:
    for chain in listener.get("filter_chains") or []:
        for f in chain.get("filters") or []:
            for vhost in ((f.get("typed_config") or {}).get("route_config") or {}).get("virtual_hosts") or []:
                prefixes = set()
                for r in vhost.get("routes") or []:
                    prefix = (r.get("match") or {}).get("prefix")
                    cluster = (r.get("route") or {}).get("cluster", "")
                    if not cluster.startswith("agent_router_") or cluster == "agent_router_sts" or prefix in NO_MODEL:
                        continue
                    prefixes.add(prefix)
                    want = WANT.get(prefix)
                    pins = [h for h in r.get("request_headers_to_add") or [] if (h.get("header") or {}).get("key") == "x-ar-model"]
                    where = f"{listener['name']} {prefix}"
                    if want is None:
                        fails.append(f"{where}: a route to {cluster} that is neither a model path nor /mcp or /github/")
                        continue
                    if len(pins) != 1 or pins[0]["header"].get("value") != f"%ENVIRONMENT({want[0]})%" \
                            or pins[0].get("append_action") != "OVERWRITE_IF_EXISTS_OR_ADD":
                        fails.append(f"{where}: must set x-ar-model to %ENVIRONMENT({want[0]})% with "
                                     f"OVERWRITE_IF_EXISTS_OR_ADD, got {pins}")
                    if (r.get("route") or {}).get("prefix_rewrite") != want[1]:
                        fails.append(f"{where}: prefix_rewrite must be {want[1]}, got {(r.get('route') or {}).get('prefix_rewrite')}")
                if prefixes and prefixes != set(WANT):
                    fails.append(f"{listener['name']}: model paths {sorted(prefixes)}, expected {sorted(WANT)}")

for fail in fails:
    print("FAIL", fail)
if fails:
    sys.exit(1)
print("PASS: every model path of the identity proxy pins x-ar-model")
```

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-identity-proxy-model-pin.py; echo "exit=$?"
```

Expected: six `FAIL` lines, three per listener (`/v1/` and `/anthropic/` set no `x-ar-model`, and
`model paths ['/anthropic/', '/v1/'], expected ['/anthropic/', '/judge/v1/', '/v1/']`), `exit=1`.

- [ ] **Step 3: The bootstrap**

In `infrastructure/base/agent-runtime/identity-proxy-configmap.yaml`, replace (public listener):

```yaml
                            - {match: {prefix: /v1/}, route: {cluster: agent_router_public, timeout: 0s}}
                            - {match: {prefix: /anthropic/}, route: {cluster: agent_router_public, timeout: 0s}}
```

with:

```yaml
                            - match: {prefix: /v1/}
                              route: {cluster: agent_router_public, timeout: 0s}
                              request_headers_to_add:
                                - header: {key: x-ar-model, value: "%ENVIRONMENT(MODEL)%"}
                                  append_action: OVERWRITE_IF_EXISTS_OR_ADD
                            - match: {prefix: /anthropic/}
                              route: {cluster: agent_router_public, timeout: 0s}
                              request_headers_to_add:
                                - header: {key: x-ar-model, value: "%ENVIRONMENT(MODEL)%"}
                                  append_action: OVERWRITE_IF_EXISTS_OR_ADD
                            - match: {prefix: /judge/v1/}
                              route: {cluster: agent_router_public, prefix_rewrite: /v1/, timeout: 0s}
                              request_headers_to_add:
                                - header: {key: x-ar-model, value: "%ENVIRONMENT(JUDGE_MODEL)%"}
                                  append_action: OVERWRITE_IF_EXISTS_OR_ADD
```

and the same two lines of the internal listener (`agent_router_internal`) with the same three
routes, `cluster: agent_router_internal`. In the file's header comment, replace:

```yaml
# A run's audience names its data class, so the other class's port earns a 403,
# and the run's CNP does not open it anyway.
```

with:

```yaml
# A run's audience names its data class, so the other class's port earns a 403,
# and the run's CNP does not open it anyway.
# Model pin (capability profiles P4): /v1 and /anthropic carry x-ar-model from
# MODEL, the run's alias, and /judge/v1 (sent on as /v1) from JUDGE_MODEL, the
# completion judge's, over any value the harness sends; the gateway takes the
# model from it. The AgentRun composition sets both, JUDGE_MODEL `none` when
# the claim names no judge, which the gateway refuses. Envoy sends `-` for an
# unset variable, refused too: this file must not reach a cluster before the
# composition that sets them (plan R11).
```

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-identity-proxy-model-pin.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-identity-proxy-upstreams.py
```

Expected: `PASS: every model path of the identity proxy pins x-ar-model`, and the upstreams suite's
`PASS`.

- [ ] **Step 4: The wire test's proxy section**

In `scripts/ci/tests/test-agent-capabilities-wire.sh`, replace the header's last comment line:

```bash
# controller's translation of the CRDs; the live gate does.
set -uo pipefail
```

with:

```bash
# controller's translation of the CRDs; the live gate does.
# The identity proxy (P4) then runs from agent-runtime/identity-proxy-configmap.yaml in front of the
# same gateway, with the environment the AgentRun composition gives it: each model path carries the
# run's alias and /judge/v1 the judge's, over whatever the harness asks for.
set -uo pipefail
```

and insert, before the final line pair `[ "$fails" -eq 0 ] || …` / `echo PASS`:

```bash
# --- P4's sidecar half: the identity proxy from the real ConfigMap, holding the reviewer's token, in front
#     of the same gateway. Its image is the one crossplane-configuration's AgentRun composition pins. ---
ENVOY_IMAGE="docker.io/envoyproxy/envoy:distroless-v1.39.1@sha256:eb2c01c13125d1629637cb4e4cce7207009fb7cc2c8027f9742758549d15b6f4"
px="agent-capabilities-wire-px-$$"
trap 'docker rm -f "$gw" "$px" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; rm -rf "$tmp"' EXIT
px_port="$(free_port)"; px_health="$(free_port)"
mkdir -p "$tmp/token" && cp "$tmp/$R.jwt" "$tmp/token/token" && chmod 755 "$tmp/token" && chmod 644 "$tmp/token/token"
ROOT="$ROOT" TMP="$tmp" PORTS="$px_port $px_health $gw_port" python3 - <<'PY' || { echo "cannot render the proxy config" >&2; exit 1; }
import os
import yaml

root, tmp = os.environ["ROOT"], os.environ["TMP"]
port, health, gateway = (int(p) for p in os.environ["PORTS"].split())
data = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-runtime/identity-proxy-configmap.yaml"))
            if d and d["kind"] == "ConfigMap")["data"]
open(f"{tmp}/sds-gateway.yaml", "w").write(data["sds-gateway.yaml"].replace("/var/run/secrets/agents/gateway", f"{tmp}/token"))
cfg = yaml.safe_load(data["envoy.yaml"].replace("/etc/envoy/sds-gateway.yaml", f"{tmp}/sds-gateway.yaml")
                     .replace("/var/run/secrets/agents/gateway", f"{tmp}/token"))
# The admin socket's path is the pod's; admin is not under test.
cfg["admin"] = {"address": {"socket_address": {"address": "127.0.0.1", "port_value": 0}}}
lst = {l["name"]: l for l in cfg["static_resources"]["listeners"]}
lst["internal"]["address"]["socket_address"]["port_value"] = port
lst["health"]["address"]["socket_address"].update(address="127.0.0.1", port_value=health)
cfg["static_resources"]["listeners"] = [lst["internal"], lst["health"]]
cluster = next(c for c in cfg["static_resources"]["clusters"] if c["name"] == "agent_router_internal")
cluster["type"] = "STATIC"
cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"].update(
    address="127.0.0.1", port_value=gateway)
cfg["static_resources"]["clusters"] = [cluster]
yaml.safe_dump(cfg, open(f"{tmp}/envoy.yaml", "w"), sort_keys=False)
PY
chmod 644 "$tmp/envoy.yaml" "$tmp/sds-gateway.yaml"
proxy() {  # proxy [NAME=VALUE ...]: (re)starts the identity proxy with that environment
  docker rm -f "$px" >/dev/null 2>&1
  local envs=()
  for e in "$@"; do envs+=(-e "$e"); done
  docker run -d --name "$px" --network host "${envs[@]}" -v "$tmp:$tmp:ro" "$ENVOY_IMAGE" \
    -c "$tmp/envoy.yaml" --log-level warn --disable-hot-restart --concurrency 1 >/dev/null || { echo "cannot start $ENVOY_IMAGE" >&2; exit 1; }
  for _ in $(seq 1 30); do
    curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:$px_health/ready" && return 0
    sleep 0.5
  done
  docker logs "$px" 2>&1 | tail -20 >&2; echo "the identity proxy never became ready" >&2; exit 1
}
# The harness's view: no token (the proxy adds it), and it asks for tier-frontier in the body and the header.
via() { call "$px_port" "$1" "" tier-frontier tier-frontier; }
upstream_path() { python3 -c 'import json,sys; l=open(sys.argv[1]).read().splitlines(); print(json.loads(l[-1])["path"] if l else "-")' "$tmp/upstream.jsonl"; }

echo "through the identity proxy (P4's sidecar half, gate 3)"
proxy MODEL=tier-standard JUDGE_MODEL=tier-light
expect "/v1 reaches the run's model, whatever the body and the harness's header say" "200 claude-sonnet-5-5" "$(via /v1/chat/completions)"
expect "/anthropic is pinned too" "200 claude-sonnet-5-5" "$(via /anthropic/v1/messages)"
expect "/judge/v1 reaches the judge's model" "200 claude-haiku-5-5" "$(via /judge/v1/chat/completions)"
expect "on the gateway's /v1" "/v1/chat/completions" "$(upstream_path)"
proxy MODEL=tier-standard JUDGE_MODEL=none
expect "no judge on the claim: /judge/v1 is refused" "403 -" "$(via /judge/v1/chat/completions)"
expect "and /v1 still answers" "200 claude-sonnet-5-5" "$(via /v1/chat/completions)"
proxy MODEL=tier-frontier JUDGE_MODEL=none
expect "a run created with a model its profile refuses fails at its first call" "403 -" "$(via /v1/chat/completions)"
proxy
expect "a proxy without MODEL (a ConfigMap ahead of the composition) refuses: the composition ships first" "403 -" "$(via /v1/chat/completions)"
```

```bash
bash $SCRATCH/run-suite.sh bash scripts/ci/tests/test-agent-capabilities-wire.sh; echo "exit=$?"
```

Expected: `SKIP: no docker daemon` (77) without Docker; with Docker or the shim, 18 `ok` lines and
`PASS`. With today's bootstrap in place, six proxy cases fail (the planning control).

- [ ] **Step 5: The docs and the spec**

In `gateways.md`, replace:

```markdown
transformation makes. Every profile lists the four aliases today, so the rule binds nothing until a
```

with:

```markdown
transformation makes. The identity proxy sets it on every model path, over any value the harness
sends: the run's alias (the claim's `spec.model`) on `/v1` and `/anthropic`, and the completion
judge's on `/judge/v1` (`spec.loop.judgeModel`, or `none`, which the rule refuses, when the claim
names no judge). Every profile lists the four aliases today, so the rule binds nothing until a
```

In `agents/runtime.md`, replace:

```markdown
| Identity proxy | [Envoy](https://www.envoyproxy.io) sidecar | Attaches the run's own short-lived token to every model, tool and token-exchange call. The harness never sees that token |
```

with:

```markdown
| Identity proxy | [Envoy](https://www.envoyproxy.io) sidecar | Attaches the run's own short-lived token to every model, tool and token-exchange call, and pins the model: every model call reaches the alias the run was created with, and `/judge/v1` the completion judge's. The harness never sees that token |
```

In the spec's status line, replace:

```markdown
P2 and the gateway's half of P4 are
built
```

with:

```markdown
P2 and P4 are
built
```

- [ ] **Step 6: Commit**

```bash
git add HOST_REF infrastructure/base/agent-runtime/identity-proxy-configmap.yaml scripts/ci/tests/test-identity-proxy-model-pin.py \
  scripts/ci/tests/test-agent-capabilities-wire.sh website/content/docs/platform/ai-platform/gateways.md \
  website/content/docs/platform/ai-platform/agents/runtime.md docs/superpowers/specs/2026-10-21-capability-profiles-design.md
git commit -m "feat(agent-runtime): capability profiles P4, the identity proxy pins the run's model and the judge's"
```

---

### Task 10: Verify, push, open PR B; the live proofs

- [ ] **Step 1: The whole check**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "assert-agent-gateway|model-pin|capabilities-wire|identity-proxy|passed,|resolve|docs site exists|exit=" \
  "$SCRATCH/check-$(basename "$PWD").log"
```

Expected: `assert-agent-gateway: 15 checks, 0 violations`; `PASS  test-identity-proxy-model-pin`,
`PASS  test-identity-proxy-upstreams`; `SKIP  test-agent-capabilities-wire` without Docker;
`29 passed, 3 skipped, 0 failed` (PR A's counts and the static suite); links and doc paths pass;
`exit=0`. The validation renders the claims against the XRDs
of the host at `HOST_REF`, which now carry `spec.loop`.

- [ ] **Step 2: Rebase, push, open PR B**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/capability-profiles-p4-pin
```

Title: `feat(agent-runtime): capability profiles P4, the identity proxy pins the run's model and the judge's`.
Body: the outcome; R6, R8, R10, R11 (and that PR H is applied); the suites; the `task check`
summary; a test plan (CI's `PASS  test-agent-capabilities-wire` with the proxy cases). No
attribution line. Merge only once Task 8 Step 2 holds.

- [ ] **Step 3: The live proofs, in the next gcp-0 session**

Gate item 1, on a test profile (`reviewer.internal` without `tier-frontier`, applied by hand in the
session and reverted after; Flux suspended on `agent-gateway` meanwhile): from a reviewer run's
sandbox, `curl -s -o /dev/null -w '%{http_code}' $LLM_BASE_URL/chat/completions -d
'{"model":"tier-frontier",…}'` through the proxy answers 200 (the pin wins) and, with the run created
with `model: tier-frontier`, 403; the gateway's access log line carries the run's `x_ar_agent` and
`http.status=403`. Gate item 3: from an implementer run's sandbox, a post to `/v1` naming another
model reaches the run's alias, and one to `/judge/v1` on a claim with `spec.loop.judgeModel:
tier-light` reaches `tier-light`; the gateway's `gen_ai_request_model` and access log name them. Each
result goes into the spec's Gate section.
