# RunLore knowledge base, live 4 — 2026-11-08

[Runbook 25 §5](25-runlore-kb-phase-1.md#5-live-4-the-replay-rk17), run on aws-0 with RunLore
`ghcr.io/smana/runlore:0.20.0` (`runlore-0`), against `Smana/runlore-kb`.

**Result: passed for the entry path.** Three fixes are recorded on their entries, the slashed entry branches
were read and written, and the first Knowledge queue issue lists the backlog. As the runbook states, the replay
writes no outcome event, so RK17's outcome join is not exercised (K13) and the entries stay `unverified`.

## The replay

`lore kb resolve --verdict resolved`, at 09:57 UTC:

| KB PR | Fix | Merge commit | Commit on the entry branch | Author / committer, signed |
|---|---|---|---|---|
| [#159](https://github.com/Smana/runlore-kb/pull/159) | [#2638](https://github.com/Smana/cloud-native-ref/pull/2638) | `eb562c16` | `aa91bcc4` | `runlore[bot]` / `web-flow`, `true` |
| [#162](https://github.com/Smana/runlore-kb/pull/162) | [#2659](https://github.com/Smana/cloud-native-ref/pull/2659) | `4230652d` | `5de9e8e4` | `runlore[bot]` / `web-flow`, `true` |
| [#163](https://github.com/Smana/runlore-kb/pull/163) | [#2659](https://github.com/Smana/cloud-native-ref/pull/2659) | `4230652d` | `70b078a3` | `runlore[bot]` / `web-flow`, `true` |

Each printed `PR #<n>: resolution appended`. Each entry gained a `resolution:` block (`fix_pr`, `merge_sha`,
`verdict: resolved`) and a `## Resolution` section linking the fix.

Every entry branch is slashed (`runlore/kb-…`), so these writes also prove §6 check 5: RunLore's escaped
branch reads reach GitHub.

#157, #158, #160 and #161 have no fix pull request and were not replayed. They stay in the queue for the stale
sweep.

## The queue issue

`lore curate queue-issue`, at 09:58 UTC, with the ledger at 101 events:

- [runlore-kb#165 "Knowledge queue"](https://github.com/Smana/runlore-kb/issues/165) was rewritten:
  `to_decide` 47, `merged` 1. Its sections are Decide, Audit and Measures.
- All 47 Decide rows are `conflict`. These are entries #110 to #163, drafted from 2026-09-10 on, whose
  branches no longer apply to the knowledge base.
- `refresh-entries` refused every one: "no label and no held evidence; refresh-entries --pr rebuilds it".
  Nothing was force-pushed. This is the automatic refresh's rule (KP19): it takes only a pull request
  labelled `ready-to-merge` or with held evidence.

## What follows

- **The backlog is the stale sweep's.**
  [cloud-native-ref#2715](https://github.com/Smana/cloud-native-ref/pull/2715) was held for this run. It
  closes entries nobody kept, and is now the owner's to review.
- **§6's rebuild checks are not run.** Checks 1–4 and 6 need one entry rebuilt by hand
  (`refresh-entries --pr <n>`) before the owner reviews it.
