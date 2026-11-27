# 30 — Gemini on Vertex AI: the live checks and the paired comparison

Gemini 4 Neon and Hydrogen behind the model gateway on gcp-0, checked live and then compared with
`agent-default` on the same issues. Steps L1 to L5 are the [Gemini design](https://github.com/Smana/ai-native-ref/pull/514)'s
live test. Write the ledger as you go, `results-gcp-0-gemini-<date>.md` beside this runbook: the
Maku version and digests, the window, every task name, and the query output behind each number. No
number is an estimate.

See [README.md](README.md) for the cluster prerequisites and the runbook table.

Each step names its **pass** line and its **stop** condition. A stop ends the step: record it, do
not work around it, and do not start the next step on a stop.

## Prerequisites

| Item | Check |
|---|---|
| The OpenCode harness trial is closed, with no treatment left on (design G12) | `kubectl -n agent-system get factory -o jsonpath='{.items[0].spec.evaluation}'` shows no `treatmentHarness` |
| Maku v0.55.0 or later runs on gcp-0, with the gateway's `vertex` provider | `kubectl -n agent-gateway get agentgatewaybackend vertex-gemini-standard vertex-gemini-light` |
| The proxy's Google identity is Ready | `kubectl -n agent-gateway get gcpworkloadidentity xplane-model-gateway` shows `SYNCED` and `READY` true |
| The `model:<alias>` label pin, `evaluation.treatmentModel` and `maku stages --by model` are released (Maku plan A-3), for L3 and L4 | `maku stages --help` lists `--by model` |
| The planner patch is ready to merge (ai-native-ref plan B5), for L2 | its pull request is green and unmerged |
| The owner's go on spend is recorded in the ledger | the ledger's first line |
| The Google AI Ultra credits are on `ogenki-435905`'s billing account | Cloud console → Billing → Credits |

## L1 · Wire, identity and metering (about 30 min)

1. The proxy holds no Google key:

   ```bash
   kubectl -n agent-gateway get deploy model-gateway -o json \
     | jq '[.spec.template.spec.volumes[]? | select(.secret)] | map(.secret.secretName)'
   kubectl -n agent-gateway get deploy model-gateway -o jsonpath='{.spec.template.spec.serviceAccountName}'
   ```

   Pass: no Secret names Google or Gemini, and the ServiceAccount is `model-gateway`.

2. File one scratch issue on `Smana/ai-native-ref` with the label `model:gemini-standard`: a one-line
   documentation fix with an exact acceptance list. Then read the gateway's access log for its runs:

   ```bash
   kubectl -n agent-gateway logs deploy/model-gateway --since=1h \
     | jq -c 'select(."gen_ai.provider.name" == "gcp.vertex_ai")
              | {status: ."http.status", model: ."gen_ai.request.model", in: ."gen_ai.usage.input_tokens",
                 out: ."gen_ai.usage.output_tokens", reasoning: ."gen_ai.usage.reasoning_tokens", cost: ."cost.total"}'
   ```

   Pass: every call is status 200 on `gemini-4-neon`, with tool calls among them.
   Stop: a 403 (the role lacks a permission: record the permission the error names, add it to the
   host's `xplane_vertex_predict` role, never `roles/aiplatform.user`), or a 400 naming a thought
   signature or a thinking budget.

3. Leave the gateway running for an hour, then count 401 and 403 answers from Vertex:

   ```bash
   kubectl -n agent-gateway logs deploy/model-gateway --since=70m \
     | jq -c 'select(."gen_ai.provider.name" == "gcp.vertex_ai" and (."http.status" == 401 or ."http.status" == 403))' | wc -l
   ```

   Pass: 0, so the token from the metadata server refreshes.

4. Metering, on five calls of step 2: the gateway's `cost.total`, the factory's run cost
   (`status.runs[].costMicroUSD` of the task) and Vertex's own count agree. Vertex's count is the
   response's `usage`, or the console's usage for the window. Then run the day's cross-check:

   ```bash
   python3 scripts/ops/cost-crosscheck.py --day "$(date -u +%Y%m%d)"
   ```

   Pass: within 2 %, with thinking tokens counted as output (`gen_ai.usage.output_tokens` includes
   `reasoning_tokens`) at the output rate of `meter.prices`.
   Stop: a mismatch above 2 %.

## L2 · The planner on Neon (about 30 min)

1. Merge the planner patch (plan B5). It routes the broker's planner to `gemini-4-neon` on gcp-0.
2. Run 20 `maku handoff` plans on fixed prompts: 10 before the merge, on Z.ai, and 10 after it, on
   Neon. Every plan sends `reasoning_effort: low`, which the `vertex` preset turns into
   `thinkingLevel: low`.
3. Read each plan's latency from the broker's log and the gateway's access log
   (`."duration"` on the `clients` listener).

Pass: p95 under 15 s across the 10 Neon plans, and no plan times out (the deadline is 20 s).
Then the owner ranks the 20 plans blind, on grounding, steps and questions: Neon is not worse on the
median.
Stop: a timeout, or p95 at 15 s or more. Revert the patch before anything else.

Revert the planner patch at the end of L2.

## L3 · Roles on both harnesses (about 2 h)

Three scratch issues per harness, each labelled `model:gemini-standard` and `harness:openhands` or
`harness:opencode`:

| Role | Issue |
|---|---|
| Implementer | a small script fix with an exact acceptance list |
| Reviewer | `factory/review` on an existing pull request; the verdict must arrive through `room_verdict` |
| Tester | an issue on a repository with `workflow.testFirst: true` |

Pass, for each of the six runs:

- tool calls succeed, with no 400 from a signature;
- the reviewer's verdict is recorded on the right commit;
- no stall in the stuck-loop detector or the run's timeline;
- the run ends within its tier's caps.

Stop: any signature 400. On `vertex` the gateway carries each signature inside the tool call id,
so a 400 there is a regression to report upstream.

## L4 · The paired comparison (one to two days)

The rule below is frozen before the first task runs. The owner may override it, and the ledger
records the override.

1. Pick 10 issues from the backlog that the factory has not touched. Each is mergeable on its own,
   and together they cover at least three classes.
2. File each one twice on `Smana/ai-native-ref`, with identical bodies. Suffix the titles
   `[gemini A]` and `[gemini B]`. Label both copies with the same `workflow:` label. Label the B copy
   `model:gemini-standard`.
3. Let both run. The harness (OpenHands), efforts, caps and checks are the factory's defaults for
   both. A maintainer reviews the two pull requests of a pair blind to the arm, and each one merges
   or closes on its own merits.
4. Read the result:

   ```bash
   python3 scripts/ops/model-comparison-report.py --context gke_ogenki-435905_europe-west4-a_gcp-0 \
     --arm-a '[gemini A]' --arm-b '[gemini B]' --out /tmp/gemini-l4.md
   maku stages --by model --json > /tmp/gemini-l4-stages.json
   ```

   The report refuses a pair whose arms differ in workflow, harness or caps. The classifier may
   rate the two copies at different tiers; `--drop-mismatched` leaves such pairs out and names
   them. Record every dropped pair.

**Directional rule:** B earns a 30+30 `evaluation.treatmentModel` trial only when all three hold:

- B's merged count is at least A's minus one;
- B's USD per merged task is at most 1.5 times A's;
- B has zero signature 400s.

Cross-check the zero signature 400s against the gateway's access log for the window. The report
reads run end reasons, and a provider error can end a run under another reason:

```bash
kubectl -n agent-gateway logs deploy/model-gateway --since=48h \
  | jq -c 'select(."gen_ai.provider.name" == "gcp.vertex_ai" and ."http.status" == 400)' | wc -l
```

Stop: a pair whose B arm hits a cap set for GLM. Caps stay the same for both arms: record the cap
hit as an outcome, and never raise a cap for one arm.

## L5 · A reviewer of another family (optional, about 1 h)

On five B-arm pull requests that were already reviewed, run the review again with `agent-default`
(`factory/review` with no `model:` label). Then run five A-arm reviews again with
`model:gemini-standard`. Record how often the two verdicts agree. This feeds the v5 roadmap's
second-family reviewer.

## After the session

Write the ledger. Then update the status page's "Gemini as a provider" row: Experimental, or a known
limitation if L3 stopped. Record the owner's decision on a 30+30 trial.
