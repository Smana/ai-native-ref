# Maku documentation review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maku's `README.md` and `docs/` the one home of the product's documentation: nothing false at v0.47.0, one first page per reader path, one page type per page, and guards that keep it so.

**Architecture:** Correctness first, then guards, then moves. Each guard is added to `hack/docs.sh` with its test in `hack/docs_test.sh`, seen failing on today's pages, then the pages are fixed until it passes. A page opts in to the word ceiling by declaring its type; a moved page leaves a short stub, because GitHub-rendered Markdown has no aliases.

**Tech Stack:** Markdown rendered by GitHub, `hack/docs.sh` (bash, awk, perl), `task docs`, mermaid.

**Spec:** [`docs/superpowers/specs/2026-11-14-docs-review-design.md`](../specs/2026-11-14-docs-review-design.md) in ai-native-ref (branch `docs/review-docs`). Copy it beside this plan when the plan is copied into Maku. This plan is rows 1 and 2 of its sequencing table; line numbers are Maku `origin/main` at `c9ee6f5`.

## Global Constraints

- Execute in the Maku repository, in a worktree from `origin/main`. `task docs` (`hack/docs_test.sh`, then `hack/docs.sh`) is the evidence for every task; `task check` before each pull request.
- The product is **Maku**. The factory, a room and the model gateway are its components. "Model gateway" is the reader's term; `agent-router` appears in manifests only.
- A page says what is true at v0.47.0. `merge-policies.md`, `cli.md` and `slack.md` get defect fixes only: they are rewritten with releases N+1 and the UX change (see "Waiting").
- Word ceilings by page type: tutorial and how-to 1,500; explanation 4,000; operations 4,000; reference none.
- No design id (`D1`–`D26`, `AM6`, `MP15`, `HR13`, "rollout step 7", "release N+1") and no cluster name (`aws-0`, `gcp-0`) in reader pages. Both are allowed under `docs/superpowers/` and `docs/contributing/`.
- No guard takes a list of pages or lines. Exemptions are by directory or by the page's own declared type.
- A split never drops a sentence silently: every task lists what it deletes, and its last content step checks the word account.
- Every anchor another file links to survives, on the page that now owns the text.
- Commits are conventional, in English, with no trailers.

## Review Focus

No guard catches these. Each is pinned to the task that owns the pages.

1. **A moved section breaks a link from outside `docs/`.** Go sources, chart READMEs, CLI help text, `web/` and ai-native-ref link `docs/<page>.md#<anchor>`. A reader expects every such link to land on the text. Pinned: Task 5 step 1 (the inbound-link inventory), reused by Tasks 6 to 9.
2. **A split loses content.** The destination pages together are shorter than the source for no listed reason. Pinned: the word-account step that ends Tasks 6 to 9.
3. **A generated page stops being generated.** `docs/install-secrets.md` carries a table written from `internal/install`; a test or generator names a docs path that moved. Pinned: Task 5 step 2 and Task 9 step 5.
4. **Host wording is replaced by vague wording.** "Your identity provider" with the ZITADEL steps deleted leaves an operator with less than before. Pinned: Task 2 step 3 (the labelled preset block).
5. **A page declares the wrong type to pass its ceiling.** An explanation marked `reference` has no limit. Pinned: Task 10 step 4 (the type review table).

---

## Pull request 1: correctness (spec defects 9 to 14)

### Task 1: False statements about the product

**Files:**
- Modify: `docs/integration.md:4`, `docs/operations.md:4`, `docs/security.md:337`, `docs/roadmap.md:7`, `docs/README.md` ("Reading paths", the page table), `docs/factory.md:8`, `docs/merge-policies.md:65`

**Interfaces:**
- Produces: `docs/README.md` with a "Reading paths" table of exactly four rows (Try it, Onboard a repository, Turn on auto-merge, Operate it). Task 5 rewrites its page table; later tasks only change link targets.

- [ ] **Step 1: List today's hits**

Run: `grep -n -E 'two CRDs|live in cloud-native-ref|As of v0\.|maku-factory/README' docs/*.md` and `grep -n -E '\b(aws|gcp)-0\b' README.md docs/*.md`
Expected: `integration.md:4`, `operations.md:4`, `security.md:337`, `roadmap.md:7`, the `docs/README.md` operator path, and 17 cluster-name hits.

- [ ] **Step 2: Fix each statement**

| Where | Write |
|---|---|
| `integration.md:4` | Six CRDs and six charts, named by listing `charts/` and the `agent-factory-crds` chart's templates at the commit; no count the next chart falsifies ("the charts under `charts/`"). |
| `operations.md:4`, `security.md:337` | "in your GitOps repository"; ai-native-ref linked once as the example. |
| `roadmap.md:7` | Delete the "As of v0.42.0" stamp. |
| `factory.md:8`, `merge-policies.md:65`, the 15 other hits | Delete the host state. Where the sentence explained a behaviour, keep the behaviour with "for example, on the reference platform". Link the platform's status page once, from `docs/README.md`. |
| `docs/README.md` "Reading paths" | Four rows. Try it: `quickstart.md`. Onboard a repository: `install.md` → `github-apps.md` → `merge-policies.md#start-here` (until Task 11). Turn on auto-merge: `merge-policies.md`. Operate it: `install.md` → `operations.md` → `observability.md` → `security.md`. The contributor path moves under the table as one sentence. |

- [ ] **Step 3: Verify**

Run: the two greps of step 1, then `task docs`
Expected: no hit for the first grep; the second prints nothing outside fenced code; `task docs` exits 0.

- [ ] **Step 4: Commit**

`git commit -m "docs: correct the CRD and chart counts, the GitOps wording and the reading paths"`

### Task 2: Identity and network wording (defect 13)

**Files:**
- Modify: `docs/api.md` (21 hits), `docs/factory.md` (8), `docs/slack.md` (6), `docs/web-ui.md:12`, `docs/concepts.md`, `docs/github-link.md`

- [ ] **Step 1: List the hits**

Run: `grep -n -i -E 'zitadel|tailnet' docs/api.md docs/factory.md docs/slack.md docs/web-ui.md docs/concepts.md docs/github-link.md`

- [ ] **Step 2: Rewrite to the generic seam**

"ZITADEL ID token" becomes "ID token from your identity provider"; `human:<zitadel sub>` becomes `human:<sub>`; "Your browser needs the tailnet" becomes "Your browser must reach the broker's address (see Exposure (`exposure.md`))". `docs/identity.md` stays the one page that names presets.

- [ ] **Step 3: Keep the preset**

Where a page gave ZITADEL-specific steps (the reader PAT in `github-link.md`, the roles claim), keep them under one line reading "Preset: ZITADEL" that links `identity.md`, not deleted.

- [ ] **Step 4: Verify and commit**

Run: the grep of step 1. Expected: every remaining hit sits under a "Preset: ZITADEL" line or in `identity.md`. `task docs` exits 0.
`git commit -m "docs: any OIDC issuer in the reader pages, ZITADEL as a labelled preset"`

## Pull request 2: guards (DOC10, DOC13)

### Task 3: The design-id and cluster-name guard

**Files:**
- Modify: `hack/docs.sh`, `hack/docs_test.sh`
- Modify: `docs/install.md` (21 ids), `docs/factory.md` (53), `docs/operations.md` (25), `docs/upgrading.md` (13), `docs/slack.md:277`, `docs/concepts.md`, and whatever else the guard reports

**Interfaces:**
- Produces: two findings printed by `hack/docs.sh`, in the existing `FILE:LINE: <rule>: <match>` form: `design id` and `cluster name`. Skipped the same way the status rule skips: fenced code, inline code, and any path under `docs/superpowers/` or `docs/contributing/`.

- [ ] **Step 1: Write the failing test** in `hack/docs_test.sh`, after the status cases

```bash
printf '# G\n\nThe gate (D11) posts a status. See AM6, HR13, MP15, OD-8 and rollout step 7.\nRuns on aws-0. Release N+1 refuses it. The B1 budget and a `D4` flag stay.\n' > "$tmp/docs/g.md"
mkdir -p "$tmp/docs/contributing"; cp "$tmp/docs/g.md" "$tmp/docs/contributing/g.md"
out=$(hack/docs.sh "$tmp/docs/g.md" "$tmp/docs/contributing/g.md" 2>&1 || true)
for id in D11 AM6 HR13 MP15 OD-8 'rollout step 7' 'Release N+1'; do grep -q "g.md:3: design id: $id\|g.md:4: design id: $id" <<<"$out"; done
grep -q 'g.md:4: cluster name: aws-0' <<<"$out"
if grep -q 'B1\|D4\|contributing' <<<"$out"; then echo "unexpected match"; exit 1; fi
```

- [ ] **Step 2: Run it to see it fail**

Run: `bash hack/docs_test.sh`. Expected: non-zero exit at the first `grep -q`.

- [ ] **Step 3: Add `ids FILE` to `hack/docs.sh`**, called in the main loop beside `status`

It prints `line<TAB>rule<TAB>match`. Patterns, whole words, case-sensitive:
- design id: `D[0-9]{1,2}`, `AM[0-9]+`, `MP[0-9]+`, `HR[0-9]+`, `FA[0-9]+`, `SI[0-9]+`, `GW[0-9]+`, `OD-[0-9]+`, `V1[0-9]`, `C[24]`, `R[0-9]{1,2}`, and the phrases `rollout step [0-9]`, `step [0-9] (PR|R)[ A-Z0-9]`, `[Rr]elease N(\+1)?`, `Live proof [0-9]`.
- cluster name: `(aws|gcp)-0`.

- [ ] **Step 4: Run the test, then the guard on the real pages**

Run: `bash hack/docs_test.sh && bash hack/docs.sh | grep -c -E 'design id|cluster name'`
Expected: the test passes; the count is above 100. This is the work list.

- [ ] **Step 5: Clear the work list**

For each hit: delete the id when the sentence stands without it; replace it with the thing it names when it does not ("D11" becomes "the `maku/merge-gate` status"). `upgrading.md` headings become version numbers ("v0.46.0", read from the release that carried the change with `git log --oneline -S'<heading text>' -- docs/upgrading.md` and `git tag --contains`). `slack.md` "Live proof 5" becomes "What a live run shows". `concepts.md` "C2 id" and "C4 envelope" become "the room id" and "the event envelope".

- [ ] **Step 6: Verify and commit**

Run: `task docs`. Expected: exit 0, no `design id` or `cluster name` line.
`git commit -m "docs: no design id or cluster name in the reader pages, held by hack/docs.sh"`

### Task 4: The page-type ceiling guard

**Files:**
- Modify: `hack/docs.sh`, `hack/docs_test.sh`

**Interfaces:**
- Produces: the marker `<!-- page-type: T -->` within a page's first five lines, `T` one of `tutorial`, `how-to`, `explanation`, `operations`, `reference`, `moved`. Findings: `FILE: over ceiling: <n> words, <T> allows <limit>`; `FILE: unknown page-type: <T>`; `FILE: moved stub over 40 words`. A page with no marker is not checked until Task 10 makes the marker required. Words are counted as `wc -w` counts them, on the whole file.

- [ ] **Step 1: Write the failing test**

```bash
{ printf '<!-- page-type: how-to -->\n# H\n\n'; yes word | head -1600 | tr '\n' ' '; } > "$tmp/docs/h.md"
{ printf '<!-- page-type: reference -->\n# R\n\n'; yes word | head -9000 | tr '\n' ' '; } > "$tmp/docs/r.md"
printf '<!-- page-type: essay -->\n# X\n' > "$tmp/docs/x.md"
out=$(hack/docs.sh "$tmp/docs/h.md" "$tmp/docs/r.md" "$tmp/docs/x.md" "$tmp/docs/b.md" 2>&1 || true)
grep -q 'h.md: over ceiling: 160[0-9] words, how-to allows 1500' <<<"$out"
grep -q 'x.md: unknown page-type: essay' <<<"$out"
if grep -q 'r.md\|b.md' <<<"$out"; then echo "unexpected match"; exit 1; fi
```

- [ ] **Step 2: Run it to see it fail**, then **Step 3: implement `ceiling FILE`** with limits `tutorial=1500 how-to=1500 explanation=4000 operations=4000 reference=0 moved=40` (0 means none).

- [ ] **Step 4: Verify and commit**

Run: `task docs`. Expected: exit 0 (no page carries a marker yet).
`git commit -m "docs: a page-type marker and its word ceiling in hack/docs.sh"`

## Pull request 3: moves and the try-it path (DOC8, DOC9)

### Task 5: Inventory, then the moves out of the reader docs

**Files:**
- Create: `docs/contributing/README.md`, `docs/contributing/one-run-quickstart.md`, `docs/contributing/intake-functional-test.md`
- Move: `docs/development.md` → `docs/contributing/development.md`; `docs/naming.md`, `docs/v4-readiness.md`, `docs/maku-group-migration.md` → `docs/superpowers/`
- Modify: `docs/quickstart.md`, `docs/README.md`, `README.md`, every file step 1 lists

**Interfaces:**
- Produces: `docs/superpowers/plans/2026-11-14-docs-inbound-links.txt`, one line per inbound link as `<source file>:<line>: docs/<page>.md[#anchor]`. Tasks 6 to 9 read it and tick each line they re-point.

- [ ] **Step 1: Write the inbound-link inventory**

Run: `git grep -n -o -E 'docs/[a-z0-9-]+\.md(#[a-z0-9_-]+)?' -- ':!docs/superpowers' ':!docs/*.md' > docs/superpowers/plans/2026-11-14-docs-inbound-links.txt`
Add by hand the anchors ai-native-ref links: `git -C <ai-native-ref> grep -o -E 'Smana/maku/blob/[^)" ]+' -- website README.md docs/runbooks`.

- [ ] **Step 2: Find what generates or tests a docs path**

Run: `git grep -n -E 'docs/[a-z-]+\.md' -- '*.go' 'hack/*' taskfile.yaml .github`
Expected: at least the `install-secrets.md` generator (`taskfile.yaml:128,143`) and the checker of `merge-policies.md`'s examples (its section "How this page's examples are checked"). Record each in the inventory file under a `# generated or tested` heading. No page in that list moves without its generator or test changing in the same commit.

- [ ] **Step 3: Move the contributor material**

| Source | Destination | Marker |
|---|---|---|
| `quickstart.md` "Stubbed spec-intake functional test" (l.183) | `contributing/intake-functional-test.md` | `reference` |
| `quickstart.md` "Without the script" (l.256), "The one-run quickstart" (l.273) and the CI job text | `contributing/one-run-quickstart.md` | `how-to` |
| `development.md` | `contributing/development.md` | `reference` |

`contributing/README.md` is an index of those three, under 150 words. `hack/quickstart/README.md` and the `quickstart-e2e` workflow keep working: only prose moves.

- [ ] **Step 4: Rewrite `docs/quickstart.md`**

Reader: a new user with Docker and a GitHub account. Type `tutorial`, ceiling 1,500, target 1,200. Sections, in order: Before you start; Run it; Watch the loop; What production adds (a table, linking `install.md`); Clean up; Troubleshooting. Built from the same-named sections today (l.13–72, 191–255). Deleted: "Team evaluation" (l.94–182) moves whole to `docs/team-evaluation.md` (type `how-to`; if over 1,500 words, its settings table moves to a `reference` page in Task 7); the `MAKU_VERSION` release-engineering row and the "Until a release ships" caveat move to Troubleshooting as one row each. `scoper`, `judge`, `class` and `shadow` each link `concepts.md#glossary` at first use.

- [ ] **Step 5: Move the owner documents and leave stubs**

`git mv` the three files to `docs/superpowers/`. `hack/docs.sh` skips that directory, so their ids stay. No stub: update the links step 1 found (`docs/README.md`'s lockup links `naming.md`; point it at `../README.md`). Run `task names`: expected exit 0.

- [ ] **Step 6: Verify and commit**

Run: `wc -w docs/quickstart.md` (expected at most 1,500) and `task docs` (exit 0).
`git commit -m "docs: the quickstart is the demo only; contributor and owner pages leave the reader docs"`

## Pull request 4: reference

### Task 6: `docs/reference/`

**Files:**
- Create: `docs/reference/README.md`, `room-crd.md`, `task-crd.md`, `config.md`, `sponsored-principals.md`
- Move: `docs/api.md`, `docs/event-envelope.md`, `docs/room-log.md` → `docs/reference/`, each leaving a `moved` stub at the old path
- Modify: `docs/concepts.md`, `docs/factory.md`, `docs/README.md`

**Interfaces:**
- Produces: `docs/reference/<name>.md`, each starting `<!-- page-type: reference -->`. A stub is exactly: the marker `<!-- page-type: moved -->`, the old title, and one line "Moved to [<title>](reference/<name>.md)." Stubs are deleted in "Waiting", step W4.

- [ ] **Step 1: Move and build**

| Destination | Built from |
|---|---|
| `reference/api.md`, `event-envelope.md`, `room-log.md` | The same-named pages, unchanged. |
| `reference/room-crd.md` | `concepts.md` "Reference: the Room CRD" (l.120 to end). The `repository` default is printed as the code has it; do not correct code behaviour in prose. |
| `reference/task-crd.md` | `factory.md` "The Task CRD" (l.2361–2425). |
| `reference/config.md` | `factory.md` "The config file", "Steering", "The scoper" (l.2426–2725). |
| `reference/sponsored-principals.md` | `factory.md` "Sponsored principals" (l.865–1049). |

Each `reference` page over 3,000 words opens with a table of contents.

- [ ] **Step 2: Rewrite `docs/concepts.md`**

Reader: a new user. Type `explanation`, target 1,200. Sections: In one picture (the existing diagram); Glossary (the one glossary: every term the quickstart and the README use, one line each, with the row "Run role" listing the roles the factory actually starts at v0.47.0); A room's phases; Who does what. Deleted: the Room CRD reference (moved).

- [ ] **Step 3: Re-point links, account for words**

Tick every line of the inventory that names a moved section. Run: `wc -w docs/reference/*.md docs/concepts.md` and compare with the sources; the difference must equal the deletions listed above plus the stubs.

- [ ] **Step 4: Verify and commit**

Run: `task docs`. Expected: exit 0, no dead anchor.
`git commit -m "docs: a reference directory for the CRDs, the config, the API and the log"`

## Pull request 5: the factory page (DOC6)

### Task 7: Split `docs/factory.md`

**Files:**
- Create: `docs/hardening.md`, `docs/multi-repository.md`, `docs/reference/narration.md`, `docs/reference/budgets.md`
- Modify: `docs/factory.md`, `docs/install.md` ("Private code")

**Interfaces:**
- Consumes: the inventory (Task 5), `docs/reference/` (Task 6).
- Produces: `docs/hardening.md` (`explanation`, target 3,000), `docs/multi-repository.md` (`explanation`, target 1,500). `factory.md` carries no marker yet: "The merge gate" and "Oracle classes" (l.1050–1805) stay in place until release N+1.

- [ ] **Step 1: Move by section**

| `factory.md` section | Destination |
|---|---|
| Triggers; A task's life; Triage; Escalation, reminders and stale tasks; The kill switch; Splits | Stay, as explanation. |
| Narration (l.482) | One paragraph stays; the line-by-line table goes to `reference/narration.md`. |
| Budgets (l.685) | The model stays (what a budget bounds, what happens at the limit); every key and default goes to `reference/budgets.md`. |
| The six "Hardening, …" sections (l.1844–2321) | `hardening.md`, under one heading each, with one diagram of what each stage closes. |
| Private code (l.2322) | Merged into `install.md#private-code`, which is its home; `factory.md` keeps one linking sentence. |
| Multi-repository coordination (l.2726) | `multi-repository.md`. |
| The merge gate; Oracle classes | Stay untouched. |

- [ ] **Step 2: Trim what stays**

Outside l.1050–1805, `factory.md` is at most 4,000 words. Check with `awk 'NR<START || NR>END' docs/factory.md | wc -w`, using the merge-gate section's new line range.

- [ ] **Step 3: Anchors and the word account**

Every inventory line naming `factory.md#…` resolves, on `factory.md` or on the page that took the section; fix the source file otherwise. Sum `wc -w` of `factory.md` and the four new pages against 36,455 minus Task 6's moves: a shortfall is explained line by line in the pull request body.

- [ ] **Step 4: Verify and commit**

Run: `task docs`. Expected: exit 0; `hardening.md` and `multi-repository.md` under their ceilings.
`git commit -m "docs: the factory page keeps the lifecycle; hardening and multi-repository get their own"`

## Pull request 6: operations

### Task 8: Split `docs/operations.md`

**Files:**
- Create: `docs/operations/rooms.md`, `docs/operations/factory.md`, `docs/operations/failures.md`
- Modify: `docs/operations.md` (becomes the index), `docs/drills.md` (marker `operations`)

**Interfaces:**
- Produces: three `operations` pages, each at most 4,000 words, and `docs/operations.md` as an index under 200 words with marker `how-to` that names the three and when to open each.

- [ ] **Step 1: Move by section**

| Destination | `operations.md` sections |
|---|---|
| `operations/rooms.md` | Health at a glance; Metrics; Reading the log with SQL; The system API from a terminal; Retention; Backups and rebuilds; Upgrades. |
| `operations/factory.md` | Under "The factory": Factory metrics; Outcome-overlap rollout and shadow evidence; Coordination; the three Hardening subsections; Merge policy bindings; Spend per identity; Sponsored principals; Internal principals and `factory/publish`; An adopted knowledge base repository; Webhooks; Intents in shadow; Finished rooms close. |
| `operations/failures.md` | Alerts; Common failures; The run controller's preflight; Factory alerts; Run path alerts; Slack alerts; Gateway alerts; Factory failures; Budget signals; Escalated tasks and the kill switch. One table at the top: symptom, alert, section. |

"Leaving the XR with an enforced repository" (l.527) is a migration step: it moves to `upgrading.md` under its version.

- [ ] **Step 2: Add one diagram per page**: what watches what (rooms), a task's signals in order (factory), alert to action (failures).

- [ ] **Step 3: If a page exceeds 4,000 words**, move its metric and alert tables to `docs/reference/metrics.md` and `docs/reference/alerts.md` and link them; do not raise the ceiling.

- [ ] **Step 4: Anchors, word account, verify, commit**

As Task 7 step 3, against 17,481. Run: `task docs` (exit 0).
`git commit -m "docs: operations in three pages: rooms, the factory, failures"`

## Pull request 7: security, install, the web UI

### Task 9: Split by page type

**Files:**
- Create: `docs/reference/security-controls.md`, `docs/reference/web-ui-settings.md`, `docs/reference/support.md`, `docs/sandbox-nodes.md`
- Modify: `docs/security.md`, `docs/install.md`, `docs/web-ui.md`, `docs/github-link.md`, the seam pages that receive install detail

**Interfaces:**
- Produces: `security.md` (`explanation`, ≤4,000), `install.md` (`how-to`, ≤1,500), `web-ui.md` (`how-to`, ≤1,500), `github-link.md` (`how-to`, ≤1,500); the seven seam pages and `upgrading.md` marked `reference`.

- [ ] **Step 1: `security.md`**

Reader: an evaluator or an operator deciding whether to run it. Stays: Threat model (with a new trust-boundary diagram), Identities, Authorization, Network, Untrusted-input hardening (the reasoning), Reporting a vulnerability. Moves to `reference/security-controls.md`: TLS on :8443, Redaction, Database roles, The run pod's admission, Webhooks, Supply chain, and every table of ports, policies or verbs. "Private code" becomes one sentence linking `install.md#private-code`.

- [ ] **Step 2: `install.md`**

Stays: What you bring (the seam table); a new "From zero" mermaid diagram of the install order (CRD chart, Secrets, the umbrella, preflight, first repository); Write the install; Apply it; Check it. Moves: "Sandbox nodes" to a new seam page `docs/sandbox-nodes.md` (`reference`); "Several installs in one cluster" and "The support floor" to `docs/reference/support.md`; "Private code" stays, as the home Task 7 points at; "Upgrading" becomes one link to `upgrading.md`.

- [ ] **Step 3: `web-ui.md`**

Stays: Signing in, The room list, The room page, Approvals, When something fails. Moves to `reference/web-ui-settings.md`: What each standing may do (the table), Settings, Theme, Forks.

- [ ] **Step 4: Mark the reference pages** (`upgrading.md`, `install-secrets.md`, `database.md`, `identity.md`, `exposure.md`, `github-apps.md`, `gateway.md`, `observability.md`) with `<!-- page-type: reference -->`.

- [ ] **Step 5: The generated table still generates**

Run: the task at `taskfile.yaml:128` (its name is in the inventory), then `git diff --exit-code -- docs/install-secrets.md`. Expected: no diff beyond the marker line; if the generator rewrites the file's head, teach it to keep the marker in the same commit.

- [ ] **Step 6: Anchors, word account, verify, commit**

Run: `task docs` (exit 0).
`git commit -m "docs: security, install and the web UI split by page type"`

## Pull request 8: the first pages

### Task 10: README, onboarding, and the pages left to type

**Files:**
- Create: `docs/onboard-a-repository.md`
- Modify: `README.md`, `docs/README.md`, `docs/architecture.md`, `docs/integration.md`, `docs/roadmap.md`

**Interfaces:**
- Produces: `docs/onboard-a-repository.md` (`how-to`, target 1,000) with the anchors `#before-you-start`, `#the-two-apps`, `#the-fence-file`, `#the-repository-object`, `#the-merge-gate-ruleset`, `#the-first-task`. ai-native-ref's plan links them.

- [ ] **Step 1: `docs/onboard-a-repository.md`**

Reader: a maintainer adding one repository to a running install. A checklist, each step one paragraph and a link, true at v0.47.0: install both Apps on the repository (`github-apps.md`); commit the fence file `.github/agent-factory.yaml`; add a `Repository` (the file `maku install --print` writes; `install.md#write-the-install`), with `privateCode.acknowledged` when the code is private; require the `maku/merge-gate` status with the ruleset the wizard writes (`factory.md#branch-protection-for-the-merge-gate`); run the preflight's per-repository checks; label one issue. policy-bot is named once, as optional. One sequence diagram. No field table.

- [ ] **Step 2: The rest**

| Page | Type | Target | Change |
|---|---|---|---|
| `README.md` | — | 700 | Features on one screen (one table); one glossary link; "Start here" = the four paths; a link to the platform's user guide. No marker: it is not under `docs/`. |
| `docs/README.md` | `how-to` | 500 | The four paths first; the page table grouped by type, one line each. |
| `architecture.md` | `explanation` | 4,000 | Tables of images and ports move to `reference/components.md`. |
| `integration.md` | `how-to` | 1,500 | What each release ships and what a consumer pins; the broker's config table moves to `reference/config.md`. |
| `roadmap.md` | `explanation` | 400 | What shipped, what is open, one screen. |

- [ ] **Step 3: Mark every remaining page that fits its ceiling**

Run: `grep -L 'page-type:' README.md docs/*.md docs/*/*.md`
Expected after this step: only `docs/factory.md`, `docs/merge-policies.md`, `docs/cli.md`, `docs/slack.md` (they wait; see below).

- [ ] **Step 4: The type review**

In the pull request body, one table: every page, its declared type, its word count. A reviewer rejects a `reference` page that explains why, or an `explanation` that lists fields.

- [ ] **Step 5: Verify and commit**

Run: `task docs && task check`. Expected: exit 0.
`git commit -m "docs: a page to onboard a repository, the README on one screen, every fitting page typed"`

---

## Waiting: not executed by this plan

Each row is a task for the sibling design's plan in the release it names; it is listed so the split above leaves room for it.

| # | With | Change |
|---|---|---|
| W1 | Release N (workflows) | The roles text in `concepts.md` and `factory.md` uses five roles and three workflows; `onboard-a-repository.md` is rewritten around `maku repo add` and `maku repo check`. |
| W2 | Release N+1 (merge policies) | `merge-policies.md` is dissolved: `auto-merge.md` (`how-to`, 1,200: bind, read shadow, promote, roll back, the three worked examples), `merge-gate.md` (`explanation`, 1,500, taking `factory.md` l.1050–1805), `reference/merge-policy-fields.md`, `reference/gate-reasons.md`. `factory.md` then gets its `explanation` marker. Modes read `live`, `shadow`, `disabled`. |
| W3 | The UX change | `cli.md` (`how-to`, 1,500) with `reference/cli.md`; `slack.md` (`how-to`, 1,500) with `reference/slack-settings.md`; the vocabulary of `2026-11-14-ux-review-design.md`. |
| W4 | After W2 and W3, and after ai-native-ref's links use its shortcode | `hack/docs.sh` refuses a page with no marker; the `moved` stubs are deleted. |

## Self-review notes

- Spec coverage: defects 9–15 (Tasks 1–3), DOC6 (Tasks 6–9), DOC7 (Task 10 now, W1 and W2 later), DOC8 and DOC9 (Task 5), DOC10 and DOC13 (Tasks 3, 4), the four reader paths (Tasks 1, 5, 10). Defect 16's Maku half is Task 6 step 2. Defect 18's Maku half needs no change at the pin.
- Not in the spec, added because GitHub has no aliases: the `moved` stub and its type.
