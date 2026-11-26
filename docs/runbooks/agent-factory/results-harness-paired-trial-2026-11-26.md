# Harness paired trial, rounds 1 and 2 — OpenCode vs OpenHands on gcp-0 — 2026-11-26

A paired trial: the same small task given twice to the factory, once per harness, with the
`standard` workflow and the same model tier (`glm-5.3`). Round 1 ran on Maku v0.54.5,
[round 2](#round-2-opencode-on-v0547) on v0.54.7. Data read from the Task and AgentRun objects, the
room logs and the pull requests on 2026-11-26.

> **Round 1 measures OpenCode with a handicap.** The `maku-opencode` image of v0.54.5 shipped
> without `bash` and without the GNU userland. The repository's `agent-checks` needs `bash`, so
> every OpenCode run first had to diagnose the sandbox and work around it. The image is fixed in
> Maku #736, released in v0.54.7. Read the OpenCode numbers below as an upper bound on its cost and
> a lower bound on its quality; [round 2](#round-2-opencode-on-v0547) re-runs it on v0.54.7.

## Purpose

The [OpenCode harness design](../../superpowers/specs/2026-11-15-opencode-harness-design.md) adopts
OpenCode only if it holds the merge rate and improves cost or time against OpenHands. Its 50/50
cohort trial needs 30 ended tasks per arm. This paired trial is a faster, smaller read: identical
tasks, judged by hand on the quality of the pull request as well as its cost.

## Method

Each task was filed twice with identical bodies and acceptance criteria. The `[trial A]` issue
carried the label `harness:opencode`, the `[trial B]` issue `harness:openhands`. Every task is a
small script fix with an exact acceptance list, including "only these two files change".

```mermaid
flowchart LR
  I["Issue pair<br/>trial A / trial B"] --> F["Factory<br/>standard workflow"]
  F --> R["Implementer, then reviewer"]
  R --> P["PR, AwaitingHuman"]
  P --> J["Judged by hand:<br/>keep one, close the other"]
```

Each pull request was judged on:

1. Does it meet the acceptance list exactly?
2. Do the new checks test the change, or only that the code runs?
3. Scope: any file or behaviour beyond the task?
4. Is the description useful to a developer reviewing it?
5. Did the harness run the tests itself (room log)?

Then the better pull request of each pair was kept and the other closed with "trial duplicate:
kept #N, see the trial results". Quality decides; cost breaks a tie. Nothing was merged.

Time is reported two ways. **Active** runs from the first run's start to the hand-off to a human
(`pullRequest.handedOffAt`). **Wall** runs from the Task's creation and adds the wait for a free run
slot, which depends on the factory's load, not on the harness.

## Results per pair

| Task | OpenCode (`[trial A]`) | OpenHands (`[trial B]`) | Kept |
|---|---|---|---|
| t3 kb-measures: reject bad dates and an empty window | #557: $1.195, 3.65M tokens, 39 min active (58 wall); stepped up after `budget-run` | #543: $0.156, 421k tokens, 17 min active (18 wall) | #557 |
| t4 factory-journey: fractional seconds, no `tokens` key | #551: $0.398, 1.16M tokens, 19 min active (19 wall) | #542: $0.149, 366k tokens, 17 min active (18 wall) | #542 |
| t6 check-reader-first: `--format github` | #559: $1.124, 3.32M tokens, 25 min active (68 wall); stepped up after `budget-run` | #554: $0.235, 664k tokens, 17 min active (25 wall) | #554 |
| t5 cost-crosscheck: `--json` | #565, task `33eqjewz` | #564, task `anviim7b` | [see below](#t5-the-last-pair-on-v0545) |

t5 waited in `Queued` with the reason `waiting_review_wip`: the six pull requests above filled the
review queue (`awaitingHumanWIP: 5`). Closing the three duplicates frees it.

All six pull requests changed only the two allowed files, passed CI (`validate`, `lint`,
`prerelease`), and got an `approve` from the reviewer agent. The merge gate then handed each to a
human (`no_policy_matched`): no merge class covers `scripts/`.

### t3 — kept #557 (OpenCode)

The two code changes are the same: an argparse `type=` that round-trips the date, and
`ap.error("--until must be after --since")`. Both add the four usage-error checks the acceptance
asks for, asserting exit 2, the message, and no `Traceback`.

- #557 adds a fifth check that a valid call still prints its table, the only one of the pair that
  touches "a valid call prints exactly what it prints today". Its description is accurate and names
  the one suite that failed in the sandbox, with the cause.
- #543's description claims the round-trip catches dates "Python would silently roll over (e.g.
  `2026-02-31` → March 3rd)". `strptime` raises on that date; it does not roll over. The round-trip
  catches `2026-11-1`, which #557 says correctly.

Kept on quality, at 7.7 times the cost.

### t4 — kept #542 (OpenHands)

Both meet the acceptance and add the two required checks.

- #542 parses with a full-match regex and keeps the microseconds, so a malformed timestamp still
  fails loudly. Its test prints `PASS` once, after every check. It also rewrites the fixture's
  `comments` for the fractional case, which the task did not need. Its description has no
  provenance footer (`Agent-Room`, `Agent-Run`); the factory linked the pull request regardless.
- #551 strips the fraction with `re.sub` before the old `strptime`: simpler, equally correct for
  the acceptance. Its test keeps the old `PASS` line *before* the new checks, so a failure prints
  `PASS` then `FAIL` (the exit code is still 1).

Equal on the acceptance; kept #542 for the stricter parse and the clean test output, at 0.37 times
the cost.

### t6 — kept #554 (OpenHands)

Both add `--format {text,github}` with argparse, a `report()` helper and a docstring.

- #554 tests every rule as an annotation, the clean tree, `--format text`, `README.md`, both
  argument orders, and an invalid format (exit 2).
- #559 tests the acceptance's exact line-3 case and adds a no-arguments equivalence check against
  the real repository. Its docstring keeps the old "Exit 1: each finding is printed as file:line"
  next to the new text, and the `run()` docstring describes an argument list it does not take.

Kept #554: broader checks, cleaner docstring, 0.21 times the cost.

## Totals

| Measure | OpenCode | OpenHands |
|---|---|---|
| Pull requests opened and approved by the reviewer | 3 of 3 | 3 of 3 |
| Kept after judging | 1 | 2 |
| Implementer runs out of budget (`budget-run`) | 2 of 3 | 0 of 3 |
| Cost, total / per success | $2.717 / $0.906 | $0.540 / $0.180 |
| Tokens, total | 8.12M | 1.45M |
| Active time, median (range) | 25 min (19–39) | 17 min (17–17) |
| Wall time, median (range) | 58 min (19–68) | 18 min (18–25) |

OpenCode cost 5.0 times as much per success and used 5.6 times the tokens. Both used `glm-5.3`; the
two OpenCode step-up runs also called `glm-5.3-flash`.

## Failure modes

### OpenCode (on the handicapped image)

- **No `bash`.** `agent-checks` failed with `FileNotFoundError: 'bash'`. The implementer spent
  about ten tool calls finding out why, then downloaded a static `bash` 5.2 binary from
  `robxu9/bash-static` on GitHub and pointed `python3` at the sandbox's venv for PyYAML. The
  sandbox's egress allowed that download; a run fetching an unpinned binary from the internet is
  worth a look on its own.
- **Budget spent on the workaround.** In t3 and t6 the first implementer run hit `budget-run` on
  `standard`. The factory stepped the task up to `careful`, and the second run finished. t4 was
  simple enough to fit.
- **Chasing an unrelated failure.** In t3 the first run spent its last minutes on
  `test-room-broker-webhook-egress`, which fails in the sandbox because it runs `python3 -I` without
  a system PyYAML. The harness recorded "5 pass, 1 fail" for the head.
- **Waiting on CI.** In t3 the second run polled the pull request's CI for 12 minutes (07:56 to
  08:08) before handing off, adding wall time and tokens for nothing the reviewer needed.
- **Unreadable check result.** In t6 the harness logged "checks on c3202ada skipped: unreadable
  result".
- **Reviewer without checks.** The t4 reviewer could not run `agent-checks` either; it ran the
  suite directly and said so in its verdict, the only verdict of the six with any text.

### OpenHands

- No run out of budget, and the harness logged "6 pass" on each head.
- **Description accuracy.** #543 states a false fact about `strptime`.
- **Provenance.** #542's description has no `Agent-*` footer.
- **Reviewer text.** All three reviewer verdicts are empty: an `approve` with nothing for the human
  who reviews next.

## Finding: `harness-trial-report.py` reads fields real Tasks do not have

`scripts/ops/harness-trial-report.py`, the tool for the 50/50 trial's frozen gate, counts none of
these tasks. Run on a snapshot of all 33 ai-native-ref Tasks on gcp-0 it reports 0 ended tasks per
arm and excludes 26 as `not_ended`, including the six that are `Done` with outcome `accepted`.

| The script reads | Real Tasks (Maku v0.54.5) carry |
|---|---|
| `status.costMicroUSD` | `status.usage.costMicroUSD` |
| `status.tokens` as a map (`input`, `output`, `cacheRead`, `cacheWrite`) | `status.usage.tokens`, one integer |
| `status.finishedAt` or `completedAt` | `status.endedAt` |
| outcome `merged`, phase in a list without `done` | phase `Done`, outcome `accepted` or `merged_human` |
| the arm from `profile.cohort` only | `profile.harness` too: task `3qtjvnuh` is cohort `treatment` on harness `openhands` |

The script's own tests (`scripts/ci/tests/test-harness-trial-report.py`) build Tasks with the
invented fields, so they pass and prove nothing about real data. Fix the reader against a real Task
before the 50/50 trial produces a verdict.

## Round 2: OpenCode on v0.54.7

Round 2 gives both harnesses two new pairs on Maku v0.54.7, whose `maku-opencode` image carries
`bash` and the GNU userland. Every run of t1 and t2, implementer and reviewer, reports
`factoryVersion: v0.54.7` in its provenance. The t5 pair, queued during round 1, ran later on
v0.54.5 and is recorded [on its own](#t5-the-last-pair-on-v0545).

### Results per pair

| Task | OpenCode (`[trial A]`) | OpenHands (`[trial B]`) | Kept |
|---|---|---|---|
| t1 harness-trial-report: ended and merged from the real Task status | #579, task `3fwok2p2`: $0.196, 454k tokens, 18 min active (29 wall) | #580, task `davmfk3s`: $0.132, 315k tokens, 13 min active (23 wall) | #579 |
| t2 harness-trial-report: cost and tokens from `status.usage` | #578, task `q6isxrf5`: $0.278, 742k tokens, 14 min active (15 wall) | #577, task `yyzhww52`: $0.308, 871k tokens, 30 min active (30 wall) | #578 |

All four pull requests changed only the two allowed files and passed CI (`validate`, `lint`,
`prerelease`). The reviewer agent approved each, and the merge gate handed each to a human
(`no_policy_matched`). Each cost includes one reviewer run that the factory discarded; see
[Reviewer verdicts](#reviewer-verdicts). Without it, #579 cost $0.156 and #577 $0.263.

#### t1 — kept #579 (OpenCode)

The code changes are the same: `endedAt` joins the end-time fields, `done`, `noop` and `stopped`
join the ended phases, and `accepted`, `merged_human` and the reason `merged` count as merged. Both
add the four checks the acceptance lists, and every existing check is unchanged.

- #579 builds its fixture the way a real Task looks: no `startedAt`, no legacy cost or token
  fields. Its 30-minute check therefore exercises the fallback to `metadata.creationTimestamp`.
- #580's fixture sets `startedAt` to the creation time and carries `costMicroUSD` and a `tokens`
  map, so the start fallback is never exercised and the "real" Task is not a real shape.

Kept #579 for the test that checks what the acceptance describes, at 1.48 times the cost.

#### t2 — kept #578 (OpenCode)

Both add the `status.usage.costMicroUSD` fallback with today's fields first, a per-arm token total,
and the `Total tokens` row after `Cache-write tokens`.

- #578 keeps the total in its own `total_tokens` key. When VictoriaMetrics token readings replace
  the per-key counts, it takes their `total` or re-sums the keys, so the row matches the rows above
  it. Its report check asserts the thousands separator (`540,000`).
- #577 adds a fifth `total` key inside the four-key `tokens` map, which changes the map's shape for
  any reader of the summary. VictoriaMetrics readings replace the four keys but leave `total` from
  the Task, so the total can disagree with the rows above it. Its report check does not test the
  separator.

Kept #578, at 0.90 times the cost.

#### t1 and t2 together

Both tasks change the same two files, and a conflict was expected for whichever merged second. It
does not happen: the hunks do not overlap. `git merge-tree` of #578 and #579 is clean, and
`test-harness-trial-report.py` passes on the merged tree. The `main` ruleset does not require an
up-to-date branch, so neither pull request needs a rebase.

### Totals (t1 and t2, v0.54.7)

| Measure | OpenCode | OpenHands |
|---|---|---|
| Pull requests opened and approved by the reviewer | 2 of 2 | 2 of 2 |
| Kept after judging | 2 | 0 |
| Implementer runs out of budget (`budget-run`) | 0 of 2 | 0 of 2 |
| Cost, total / per success | $0.474 / $0.237 | $0.440 / $0.220 |
| Tokens, total | 1.20M | 1.19M |
| Active time, median (range) | 16 min (14–18) | 22 min (13–30) |
| Wall time, median (range) | 22 min (15–29) | 27 min (23–30) |

### Against round 1

| OpenCode ÷ OpenHands | Round 1 (v0.54.5) | Round 2 (v0.54.7) |
|---|---|---|
| Cost per success | 5.0× | 1.08× |
| Tokens | 5.6× | 1.01× |
| Implementer runs out of budget | 2 of 3 against 0 of 3 | 0 of 2 against 0 of 2 |
| Pull requests kept | 1 of 3 | 2 of 2 |

The image fix closes the gap. On v0.54.7 OpenCode cost and used tokens within 10 % of OpenHands,
no run ran out of budget, and both kept pull requests are OpenCode's. Two pairs are a small sample:
read this as "the round-1 gap was the image", not as a verdict for the 50/50 trial.

Neither OpenCode implementer worked around the sandbox. #578's harness logged "checks on
60b0e6d3b2dc: 6 pass (the agent's own run)". #579's agent noted "agent-checks all pass"; its
harness recorded no check result for that head. The two OpenHands heads logged "6 pass".

### t5: the last pair on v0.54.5

Both t5 runs started at 08:45 UTC, before the upgrade: every run of the pair reports
`factoryVersion: v0.54.5`. It completes round 1 and is kept out of the round-2 totals.

| Task | OpenCode (`[trial A]`) | OpenHands (`[trial B]`) | Kept |
|---|---|---|---|
| t5 cost-crosscheck: `--json` | #565, task `33eqjewz`: $1.672, 5.03M tokens, 41 min active (121 wall); stepped up after `budget-run` | #564, task `anviim7b`: $0.513, 1.30M tokens, 19 min active (99 wall) | #565 |

The OpenCode run repeated round 1's failure modes. The first implementer made 64 tool calls and no
model turn on the missing `bash` before it ran out of budget. The second fetched the static `bash`
from GitHub again, then waited nine minutes for CI's `prerelease`. Its harness logged "checks on
254950091051 skipped: unreadable result". The OpenHands head logged "6 pass".

Both pull requests meet the acceptance, and both check that the exit code is the same with and
without `--json`.

- #565 adds a module-level `usd()` helper and a `render_json()` beside `render()`, and leaves every
  existing check untouched. It asserts the table output byte for byte, and that the docstring's
  usage line mentions `[--json]`.
- #564 has more checks (empty day, a bad `--day` with `--json`), but it changes the existing
  `main_with()` helper and its three call sites, which the acceptance keeps untouched. Its
  `collect()` keeps an unused `ok` from `compare()` and re-derives it in a new `verdict()`.

Kept #565 on the acceptance and the smaller change, at 3.3 times the cost. With t5, round 1 reads:
OpenCode $4.389 for 4 successes ($1.097 each), 3 of 4 out of budget; OpenHands $1.053 ($0.263
each), 0 of 4.

### Reviewer verdicts

**Empty verdicts.** In round 1, 5 of the 6 reviewer approvals had no text. In round 2 all 10
reviewer verdict comments, on t1, t2, t5 and t8 and across both harnesses, are empty: a heading
"Agent review: approved" over an empty code block. That makes 15 of 16 over the trial. The next
human reviewer learns nothing from the agent review except that it approved.

**Invented commit hashes.** Three of the 10 verdicts name a commit that shares the head's first 12
hex digits but not the rest. For #579, `6b47574ccb0d22306548…` against the head
`6b47574ccb0d880e0a41…`. The factory recorded those runs as verdict `none` (stage effect
`approve_overruled`) and started another reviewer run: one extra on #579 (OpenCode, $0.040) and on
#577 (OpenHands, $0.045). The reviewer seems to extend the 12-digit short hash it was given into a
full one by guessing; the factory's check caught it each time.

### To come

| Task | OpenCode (`[trial A]`) | OpenHands (`[trial B]`) |
|---|---|---|
| t7 cohort-results refactor | #566, task `h4w45inn`: queued | #567, task `acui76um`: queued |
| t8 cheat-sheet docs rows | #568, task `2b374w2q`: queued | #581, task `vpunyqq2`: $0.090, 247k tokens, 17 min active (32 wall); open, merge gate `shadow_would_arm` |

The first t7 and t8 tasks were rejected by the daily task cap and re-filed. The new ones wait in
`Queued` with `waiting_review_wip` until the review queue has room. #581 stays open until its pair
finishes.
