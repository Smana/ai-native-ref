---
title: FAQ
weight: 55
description: "The questions a new reader asks about the agent factory, answered: what it is for, what it costs, how to adopt it, what the loops are, what it can and cannot be trusted with, and what Maku is."
lastVerified: 2026-10-28
---

Start here if the other pages assume too much. Each answer is short on purpose: where the detail
matters it links the page that owns it, and that page wins if the two disagree.

{{< callout type="info" >}}
**This page never overrules the [status page]({{< relref "/docs/platform/ai-platform/status.md" >}}).**
The factory is a pilot: v1 shipped on 2026-10-08, v2.0 on 2026-10-18. A feature marked *built, off*
is merged behind a switch that is off everywhere; *planned* is designed and not built.
{{< /callout >}}

## What is live, built, or planned {#state}

The coarse state, as of 2026-10-28. The [status page]({{< relref "/docs/platform/ai-platform/status.md" >}})
carries each line's evidence, its live gate and the values that move.

| Area | State today |
|---|---|
| Issue → runs → pull request, narrated on the issue | {{< badge content="live" color="green" >}} |
| Rooms: watch, post, steer, approve; resume of a lost sandbox | {{< badge content="live" color="green" >}} |
| Merge gate | {{< badge content="live" color="green" >}} for `docs-links` and its revert, at most once a day |
| Gateway budgets, refusing over-budget calls | {{< badge content="live" color="green" >}} |
| Loop policy, scoper, splitter, test-first tester, Slack intake, starting from a coding agent | {{< badge content="built, off" color="yellow" >}} |
| Substrate runtime, eval bench, installing on any cluster, per-person caps that refuse | {{< badge content="planned" color="blue" >}} |

## Is this for me? {#fit}

### What is the agent factory? {#what}

A maintainer labels a GitHub issue; the factory turns it into a task, runs agents in isolated
sandboxes inside your own Kubernetes cluster, and the result is a pull request. Agents (an
implementer, then a reviewer) work on one `agent/<task>` branch while the factory narrates each step
on the issue; humans steer from GitHub or from the task's room, and a human merges. Only
policy-defined low-risk changes merge themselves. The [overview]({{< relref "/docs/platform/ai-platform/agents/_index.md" >}})
is the two-minute version, the [factory page]({{< relref "/docs/platform/ai-platform/agents/factory.md" >}})
the mechanics.

### What does it give me that a coding agent on my laptop does not? {#why}

Four things a session in your editor cannot give you: the work continues while nobody is watching,
on the repository's real branch and CI; each run has an identity, a token and a USD budget of its
own, so an action is attributable and a spend is bounded; the controls (network policy, branch
rulesets, the merge gate, the kill switch) are declared in Git and enforced outside the agent; and
several people can watch, discuss and approve the same task in one place. For one developer on one
private branch, a laptop agent is simpler and cheaper. Also worth saying plainly: it is not a better
agent. On 15 harder issues the gap followed the model, not the factory
([results]({{< relref "/docs/platform/ai-platform/status.md#landed" >}})).

### Who is it for, and who is not? {#who}

For platform teams who want coding agents on their own cluster, under their own rules, and for
maintainers of repositories where a human still reviews and merges. It suits an organisation that
already runs Kubernetes with the host services this platform expects, and that needs per-run
identity, per-run budgets and a reviewable merge policy — not a vendor's console. It is **not** for
a single developer's laptop work, for a team without a cluster and the [host contract](https://github.com/Smana/ai-native-ref/blob/main/HOST-CONTRACT.md)
services, or for anyone who cannot take on the operation of a pilot: there is no appliance and no
single binary, so it is a platform to run, not a product to switch on.

### What work suits it, and what should I keep away from it? {#tasks}

Suits: bounded, checkable changes — a dead link, a wrong chart version, a small refactor with a test,
a patch-level dependency bump, a read-only investigation that ends in a proposed issue. Unsuitable
today: open-ended tasks ("find out why this is slow") which burn a budget on reads and push nothing,
work that needs a credential or an internet host its profile does not name, changes spanning two
repositories (a run acts on one), parallel writers on a branch, and judgement calls — architecture,
product decisions, reviewing other people's code. The test to apply before labelling: can you state,
in one sentence, the check that proves the work done? If not, it is not ready.

### Should I build this, buy a hosted agent, or adopt a self-hosted runtime? {#buy-or-build}

Three families, three trade-offs. A **hosted agent** gets you the capability fastest, and puts the
agent loop, the model calls and your code in the vendor's cloud, with per-seat or per-day caps. A
**self-hosted agent runtime** keeps execution in your cluster but knows nothing about issues,
reviews or merges — you would write the factory yourself. **This project** is the third thing: five
layers plus governance, as one open reference. No candidate evaluated so far covers more than one or
two of those layers, which is why the factory, the rooms and the controls would stay yours whatever
you adopted ([alternatives]({{< relref "/docs/platform/ai-platform/agents/alternatives.md" >}}),
[comparison table](https://github.com/Smana/ai-native-ref#how-it-compares)). If you want the
capability and not the operation, buy; if the constraint is that code, prompts and identity stay in
your cluster, this is the open reference to start from.

### Is it a "dark factory"? {#dark-factory}

No, and deliberately not yet. At Dan Shapiro's levels, most work here is level 4 — a human writes the
issue and approves the merge, agents implement and review each other. One lane runs at level 5 with
no human at all: Markdown link fixes and their reverts, at most once a day. A class earns lights-out
with a live drill and keeps a revert breaker that sends it back to human review. The
[status page]({{< relref "/docs/platform/ai-platform/status.md#dark-factory" >}}) holds the levels
and where each class stands.

## Adopting it {#adopting}

### What do I need before the first task? {#prerequisites}

A Kubernetes cluster that provides what the [host contract](https://github.com/Smana/ai-native-ref/blob/main/HOST-CONTRACT.md)
lists — Flux, Cilium, the Gateway API, OpenBao, External Secrets, cert-manager, Crossplane, an OIDC
provider such as ZITADEL, and the Victoria observability stack — plus node pools that can run gVisor
sandboxes on spot. Outside the cluster: GitHub, where two Apps are installed (the agents' App and the
factory's narrative and merger App), a model provider — Z.ai for public work, the Anthropic API for
internal work — and a tailnet, because the room UI is private. That is the whole list: nothing hosts
a control plane for you, and the only third parties that see a run's traffic are the model providers
its data class names. The reference host is
[cloud-native-ref](https://github.com/Smana/cloud-native-ref) on GKE and EKS.

### Can I evaluate it locally, and cheaply? {#evaluate}

Not as one binary or a `kind` cluster today: installing on any Kubernetes cluster is designed and
scheduled after v3 ([roadmap]({{< relref "/docs/platform/ai-platform/status.md#later" >}})). The
cheap evaluation is the [interactive demo](https://blog.ogenki.io/agent-platform/) — a real room,
nothing to install — and then these pages. The smallest real evaluation is a cluster that meets the
host contract, one repository and one provider key: runbook 14 is the ordered checklist for bringing
a cluster up and running the factory on it, with every step's result recorded in it. Expect the first
task to cost cents, not dollars, and the platform to cost a node pool.

### How do I onboard a repository and get the first task through? {#onboard}

Four things live in the repository, because that is where they are reviewable: the agents' GitHub App
installed on it, the octo-sts trust policies for the roles it allows, the `agent/**` branch ruleset
and the tag ruleset, and the fence file `.github/agent-factory.yaml` naming the one factory that acts
on it. Two platform changes then make a second repository possible: its audiences at the gateway's
token-exchange listener, and an intake that polls more than one repository
([details]({{< relref "/docs/platform/ai-platform/agents/_index.md#more-than-one-repository" >}})).
The first task is then one label, `factory/ready`, applied by a maintainer — and a maintainer's
review at the end ([user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md" >}})).

### What makes an issue a good task? {#good-issue}

Name the files or the component, say what done looks like, give the check that proves it, and say
what to do if the thing is not there — an exit is what stops a run wandering. One defect per issue.
The factory reads the issue as it was labelled and never its comments, so to change a task you edit
the issue and a maintainer re-labels it. Class-level standing rules belong in a steering note
(`.github/agent-factory/steering/<class>.md`), not in each issue
([steering and questions]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#scoper-question" >}})).

### What does it cost, and what caps the spend? {#cost}

Three nested caps, priced in dollars since v2.0. A run's budget and deadline come from its tier —
`light` $0.51 and 20 min, `standard` $2.55 and 45 min, `frontier` $6.80 and 90 min — and its task's
cap is twice that; the platform also takes at most 20 tasks a day and works 3 at once. The gateway
refuses any call over its per-run, fleet or provider budget with `429 agent_budget_exhausted`, and
the run meter revokes a run at its exact cap. Most routine tasks finish in 10–40 steps for under
$0.20 ([measured runs]({{< relref "/docs/platform/ai-platform/agents/harness.md#examples" >}})).
Per-person caps count dollars today and do not yet refuse anything: that is [in progress]({{< relref "/docs/platform/ai-platform/status.md#in-progress" >}}).

### Is it production-ready? {#production}

No. It is a pilot, and the status page says so before it says anything else: three factory pull
requests have merged end to end, on one cloud, for two public repositories, and the reference cluster
is torn down between releases. What is left is tracked on the v1 hardening
milestones and the [status page]({{< relref "/docs/platform/ai-platform/status.md#landed" >}}). The
honest framing for an adopter: the controls are real and tested, the operation is a platform team's
job, and installing it on a cluster of your own is still ahead.

## Tasks, rooms and runs {#model}

### What is a room, and how do task, room, run, role, branch and pull request fit together? {#room}

A **task** is one issue's state machine, from `Received` to `Done`. A task has one **room**: the
append-only log of everything said and done about it, which outlives the runs. A **team** of
**roles** works the task as a sequence of **runs** — each run is one agent, one role, one sandbox,
with a deadline and a budget — and every run acts on the same `agent/<task>` **branch**, so the
**pull request** grows in place across revisions instead of spawning new ones. Only the implementer
writes; the others read and report into the room, and the broker posts a reviewer's verdict on the
pull request. The [rooms page]({{< relref "/docs/platform/ai-platform/agents/rooms.md" >}}) is the
detail.

### What is a team, and which roles exist? {#teams}

Four roles: an **implementer** (writes, pushes, opens the pull request), a **reviewer** (reads,
records a verdict), a **tester** (writes the failing test first when test-first is on) and a
**triager** (reads, and proposes an issue instead of writing). They are composed into templates —
`solo`, `pair` (implementer then reviewer), `trio` (with the tester) and `investigate` (triager
alone) — and triage picks one per task, once, with the tier.

### Which loops does it have? {#loops}

Four, and only the first is on everywhere:

1. **The agent loop**, inside the harness: a model call, the tools it asks for, the result, again —
   at most 500 iterations, 300 s per call, with history condensed as it grows.
2. **Continuations**, from the loop policy {{< badge content="built, off" color="yellow" >}}: a
   stall rule stops an implementer that commits nothing, and a fresh-context judge either accepts the
   run, continues the same conversation at most twice, or escalates to a human.
3. **Review, retry and resume**: a green-CI fix is a new run on the same branch, "Request changes" is
   a new run with the review in its brief, `/factory retry` tries a failed task again, and a sandbox
   lost to a spot reclaim or an eviction is resumed automatically — at most twice per task.
4. **Scheduled automation**: none. Intake is event-driven — a maintainer's label, a review, a Slack
   mention, a machine principal calling the API, Renovate's poller for dependency bumps — and a task
   that is waiting is a periodic re-check of state that already lives in Kubernetes and GitHub, not a
   timer.

### What happens when a run fails, stalls or loops? {#failure}

The end state tells you which it was. `stuck` or `maximum iterations` means the same action or error
repeated: fix what it trips on. Out of budget with hundreds of reads and no commit is a task with no
scope. `PodFailed` near the deadline is a deadline kill, which is never resumed: raise the minutes
*and* the dollars. A provider that failed three times is `/factory retry`. The
[debugging section]({{< relref "/docs/platform/ai-platform/agents/harness.md#debug" >}}) walks the
step log, the tool mix and the room in that order.

### How do I stop a task, or undo its work? {#stop}

One task: the label `factory/stop` on its issue or pull request — its runs are revoked, its branch
stays. Everything: the `agent-factory-stop` ConfigMap, or the label on the pinned control issue;
intake pauses, every run is revoked and new runs are refused, hand-launched ones included. Undoing
merged work: `factory/revert` within 7 days for an auto-merged link fix, and an ordinary revert pull
request for anything else — a revert is also what demotes a class back to human review.

## Working with it {#using}

### What can I do from the browser, and what from `roomctl`? {#interfaces}

The browser view is where the whole room lives: watch it live, post, queue a note for the next run,
steer or interrupt the running agent, take the driver token, decide an approval, fork a room, close
it. `roomctl` gives a terminal the same rooms and the same text — list, status, changes, watch, post,
queue, fork, checkout, token — and deliberately cannot steer, interrupt or approve, because a local
agent can drive a terminal ([ADR-0049]({{< relref "/docs/decisions/0049-room-client-and-human-auth.md" >}})).
Approvals stay on the room page in every client.

### Is there a Slack integration? {#slack}

Yes, and it is switched off {{< badge content="built, off" color="yellow" >}}. With the App on, a
mention of `@factory` in a served channel drafts an issue, a ✅ from a maintainer linked to the
platform files it and starts the work, and the thread receives short state lines with the room's
link — never what the agents wrote. Answering a question, approving or steering happens on the room
page: the thread only links it ([user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#from-slack" >}})).

### Does it work with Claude Code, OpenCode or another local agent? {#local-agents}

Yes: from Claude Code, OpenCode, Codex CLI, Gemini CLI, Cursor or Copilot CLI, one `roomctl setup
<client>` registers the broker as an MCP server and installs the `factory-handoff` skill, after
which you can draft and file an issue, follow a room, wait for it to need you, and check its branch
out into a worktree without leaving the session. Everything an agent wrote comes back as data, and
approvals still open on the room page. Starting work from the session is off until a repository is
listed in the broker's `human.mcp.sessionStart` — none is today
([per client]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#hand-off-from-your-coding-agent" >}})).
Separately, the platform's model gateway for people does not serve Claude Code yet
([coding clients]({{< relref "/docs/platform/ai-platform/coding-clients.md" >}})).

### Can it run fully unattended? {#unattended}

Only where a class has earned it. Today that is `docs-links` and its revert: green CI, the head
pinned to the commit the gate decided, at most once a day, with a revert breaker and a post-merge
monitor feeding it. Everything else waits for a human by design, and there is no switch that removes
review — widening a class is a change with its own live drill, and a human merging is still the
default for every other class.

## Tuning it {#tuning}

### How is the harness configured, and how do I know a change helped? {#harness}

The levers are mostly outside the harness: the **tier** (money, deadline, model), the **template**
(roles), the **data class** (provider, egress, tools, caching) and the **task text**. The harness
itself — iterations, condenser, timeouts, reasoning effort — is baked into the image, so changing it
is a release, not a per-run setting. To judge a change: change one lever, run the same kind of task,
and compare cost, steps, duration and outcome on the `agent-run` dashboard. The bench that would do
that systematically is parked until a sponsor funds its sessions
([harness tuning]({{< relref "/docs/platform/ai-platform/agents/harness.md" >}})).

### How are models chosen and routed? {#models}

Statically, on purpose. The data class picks the provider — `public` work goes to Z.ai's GLM-5.3,
`internal` work to Claude through a key only the gateway holds — and every alias maps to exactly one
model at weight 100, with no fallback and no canary, so nothing re-routes a run mid-trajectory. The
tier sets caps and team, not the model, and the reviewer keeps the implementer's model so public
work never reaches Anthropic. A triage classifier is designed but not deployed: every task is
`standard`, with 10% sent to `frontier` as a control group
([routing]({{< relref "/docs/platform/ai-platform/routing.md" >}})).

### Can I bring my own models, providers or harness? {#byo}

Models and providers, yes: add the model to the gateway's aliases with a price row, put the key in
the platform's secret store, and narrow the role profiles that may call it — agentgateway does the
rest, with no code. The harness is a real change: a different one is a new profile in the Crossplane
composition, and the `AgentRun` contract does not change, but nothing on this platform is tested
against it. Self-hosted models are the other path: vLLM on L4 GPUs behind an OpenAI-compatible
gateway, off by default on both clouds
([serving]({{< relref "/docs/platform/ai-platform/serving/_index.md" >}})).

### What do you measure beyond tokens? {#quality}

Acceptance, not activity: whether the pull request was merged, and what it cost per accepted pull
request; per class, the revert rate and the follow-up fixes merged inside its window; how long a
task waited for a human; refusals and escalations by reason; and the reviewer's verdict against the
human's. Runs are also graded for fit — under, fit or over their tier — because the point of v3 is
more accepted pull requests per dollar, not more steps per run.

## Trust and permissions {#trust}

### Which identities exist: human, run, machine? {#identities}

Three, and they are never interchangeable. A **human** is a ZITADEL user, and a room is only as
visible as their GitHub read permission on its repository, through the GitHub account linked to that
user. A **run** has a token minted for it alone, audience-scoped to its role and data class, which it
exchanges for a GitHub token confined to one repository and revoked when the run ends. A **machine
principal** is a ZITADEL machine user declared under `api.sponsored`, with a named maintainer as
sponsor, a daily dollar ceiling and a per-task cap; Slack is its first client, and it is not deployed
yet. The factory itself is a fourth: a system caller on the broker's allowlist.

### How fine-grained are the permissions? {#permissions}

Each layer answers a different question, and none of them consults the agent. The **gateway** decides
which model aliases a role may call and which tools it may use, per role and data class, generated
from profiles and drift-gated in CI; tool arguments can be constrained (today:
`get_kubernetes_resources` never with `kind: Secret`). **GitHub** decides what a token may do — one
repository, one role's permissions, `agent/**` branches and no tags, enforced by rulesets. **The
broker** decides who may read a room, post, steer or approve, from the credential rather than from a
claim in the request. **The merge gate** decides what may merge, from a policy file in the
repository.

### Can it read our secrets? {#secrets}

The sandbox holds no long-lived credential: its GitHub token is minted per run, scoped to one
repository and one role, and revoked when the run ends (at worst it expires within an hour); model
and tool calls carry a run token the gateway verifies; no Kubernetes Secret is mounted, and the
provider keys live only in the gateway. An `internal` run can read logs and pod specs through
read-only MCP tools, and those can contain secrets — that is the one path to weigh before allowing
internal work. Room events are redacted before they are stored, logged or counted, and the full
transcript stays in the room, which is as visible as the repository.

### Can it reach the internet? {#internet}

Only the hosts its network policy names: GitHub, the gateway and, with `--profiles`, package
registries. Everything else is dropped, and Hubble shows every dropped flow. Widening the egress is a
deliberate act — a fork of the room with that host named — not a flag the agent can set.

### Why gVisor? {#gvisor}

The agent runs arbitrary commands it wrote itself. gVisor answers their system calls in user space, so
a kernel exploit hits gVisor instead of the node; escaping takes a gVisor bug as well, and the node
pool is dedicated and tainted to limit what that would reach. Its system-call overhead does not show
because a step mostly waits on the model. Kata or Firecracker would need bare metal or nested
virtualisation, at a price this workload does not justify
([runtime]({{< relref "/docs/platform/ai-platform/agents/runtime.md" >}})).

### What about prompt injection and untrusted content? {#injection}

It is treated as certain, and answered outside the agent. Every text written outside the platform is
defused before an agent reads it — invisible and control characters, raw HTML and images, fence
look-alikes, repeatedly until the text stops changing — and text an agent receives from a peer is
fenced as data, never spliced into instructions. Approvals are human-only and render the raw action
rather than the agent's prose, and egress, budgets, the branch rulesets and the merge gate bound what
a persuaded agent can do. Be clear about the limit: the sanitiser is a filter, not a boundary; the
boundary is that the agent cannot merge, cannot reach a host its policy does not name, and cannot
raise its own budget. Repositories that accept issues from outside their maintainers get a harder
version of this, and that hardening is still ahead
([status]({{< relref "/docs/platform/ai-platform/status.md#later" >}})).

### Can an agent merge to `main`, or push anywhere else? {#merge}

No. Its GitHub App may push only `agent/**` branches and no tags, enforced by two repository
rulesets. Merging is the human's, except for the low-risk classes, which go through a separate
merger App that policy-bot authorises. That confinement is per repository, not per run: every run
pushes as the same App, so one run can push to another's `agent/**` branch. The footer is provenance,
never authorisation: the gate merges only the commit the task's own run reported in its room, with
every reviewer approval naming that commit.

### What is audited, and how is provenance kept? {#audit}

The room is the audit trail: append-only, enforced by the database role (insert and read, never
update or delete), each event stamped with an identity the broker verified rather than one the sender
claimed, and sealed when the task ends. On GitHub, the pull request footer names the task and its
room, and the merge gate binds the merge to the head it decided on and to push identity — every push
to the branch has to be the agents' App. Traces carry metadata only; the transcript lives in the
room, for the people who may read that repository.

### I logged in with SSO and the room UI still gives me a 403. Why? {#sso-403}

oauth2-proxy and the broker admit a token only when its `groups` claim names `agents-member` or
`agents-admin`. Two things put that claim there, and either can be missing: the `groupsFromRoles`
ZITADEL Action, which turns your project roles into the claim — a broken or edited Action drops it
from every token at once — and a grant of one of those roles to your user, which a fresh ZITADEL does
not have. Log in once so the user exists, then
`scripts/provision/zitadel-oidc-clients.sh --grant agents-member=<your email>`; check the Action
first (it fails for everyone), then your grant (it fails for you alone).

## Running it at scale {#scale}

### Several repositories, several teams, several tenants? {#multi-repo}

Two repositories today, served side by side and fenced: a repository's default branch names the one
factory that acts on it in `.github/agent-factory.yaml`, and a factory it does not name takes no
intake, schedules or API runs and merges nothing. A room, a resumed branch and a run's token never
cross between repositories. Teams are covered by roles and templates; **tenants are not built** — the
platform is single-tenant, one cluster per organisation, with isolation per person (identities,
per-person spend) and per repository (GitHub permissions, the fence), not per tenant.

### What can I observe? {#observability}

A run has a dashboard page, a step log (one line per action, no output, tokens redacted), a trace of
its model and tool calls with timings, and its room. The fleet has its own dashboards — runs, cost,
errors, spend per identity, tier fit — and alerts cover budget refusals and overruns, a cache-read
share that collapses, merge regressions and approvals pending too long. One known gap: MCP tool calls
are not yet joined to the run's trace
([observability]({{< relref "/docs/platform/ai-platform/observability.md#agents" >}})).

### How do upgrades and rollbacks work? {#upgrades}

Every release is a cosign-signed OCI artifact pinned by digest, and the cluster runs exactly what the
Git history says, so an upgrade is a version bump and a rollback is a revert commit that Flux
applies. The factory also has a kill switch that needs no deploy. The one thing a revert does not
undo: the room database's migrations are append-only and Atlas never runs a down migration, so after
a binary rollback the database keeps the newer schema
([rolling the broker back]({{< relref "/docs/platform/ai-platform/agents/rooms.md#changing-and-rolling-back-the-broker" >}})).

## Maku {#maku-name}

### What does the name mean? {#maku}

**Maku** (幕, *maku*) is Japanese for a curtain, and by extension a tent or a screen; 開幕 and 閉幕 are
the everyday words for a curtain opening and closing. The product story borrows the theatre, not the
translation: the curtain opens on a run, the run performs inside a deliberately bounded space, people
watch and can step in, and the curtain closes on a durable record. It is a metaphor, not a claim —
the word does not mean security, control or room, and the guarantees come from the sandbox, identity,
budgets, policy and the merge gate. The full record, with the guardrails (no franchise references,
theatrical wording never standing in for exact security documentation), is in
[agent-platform's naming page](https://github.com/Smana/agent-platform/blob/main/docs/naming.md).

### How do Maku, agent-platform and ai-native-ref relate? {#maku-layers}

**Maku** is the product name, chosen on 2026-10-27. **`agent-platform`** keeps being the engineering
name of the repository, module, binaries, images, charts, CRDs and APIs — nothing was renamed
technically, and that was a deliberate decision. **`ai-native-ref`** is the deployable reference
platform: the Flux manifests, policies, alerts, dashboards, runbooks and this site, which pin
agent-platform's releases by digest. The product name appears in prose and in the brand; the
identifiers you type stay as they were.

### Which parts are custom, and which are reused open source? {#maku-custom}

Custom (agent-platform): the factory controller, the room broker with its web UI, the room-bridge
sidecar, the harness entrypoint and `roomctl`, plus two CRDs and the log's migrations. Reused:
Kubernetes, [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox), gVisor, OpenHands (the
agent loop), agentgateway (identity, budgets, MCP federation), Kueue (admission), PostgreSQL through
CloudNativePG, policy-bot (the merge policy), Octo STS, Envoy, Cilium and Flux. The line is where a
mature project is strictly better than a small custom one; each is a layer boundary an alternative
could replace ([where each tool fits]({{< relref "/docs/platform/ai-platform/agents/alternatives.md#where-each-tool-fits" >}})).

### Why build the custom parts at all? {#maku-why}

Because no evaluated candidate covered the whole requirement: five layers — runtime, harness,
gateway, collaboration, factory — plus rooms with attributed human and agent participants, per-run
identity and budgets, controls that act from outside the sandbox, repository-aware workflow and merge
policy, and both EKS and GKE on spot nodes. Everything assessed covers one or two of those, and each
gap lands exactly where the factory, rooms or controls live, so they would have stayed ours whatever
we adopted. The [alternatives page]({{< relref "/docs/platform/ai-platform/agents/alternatives.md" >}})
carries the per-layer comparison, with a pinned commit and a code link per claim.

### What does the custom part cost to maintain? {#maku-cost}

Candidly, this is the real cost of the design: four binaries, a web UI, a CLI, a container image, two
CRDs and a Postgres schema, each with tests and a live gate, plus the design records and runbooks.
The mitigations are structural — the `AgentRun` and `Room` contracts keep each piece replaceable, a
release is signed and pinned so a rollback is a revert, and `task check` runs the same gates CI does
— but they lower the cost of *changing* a piece, not the cost of owning it. It is also why the
reused layers stay reused: every line of custom code is one the platform team answers for.

### What would make you drop a custom part? {#maku-reconsider}

Each layer names its own trigger, and they are written down rather than assumed: Temporal if the
factory's bugs cluster around timers and retries; Agent Substrate or a microVM runtime if concurrency
reaches about 20 sandboxes, or if gVisor blocks a class of task; otari if a gateway ships Kubernetes
packaging, per-run identity, MCP federation and OpenTelemetry export; NATS if room fan-out saturates
Postgres. Two dates
are pinned: a Substrate spike's reconsideration on 2026-12-15, and the kagent re-check with it. The
triggers and the evidence behind them are in
[what would make us reconsider]({{< relref "/docs/platform/ai-platform/agents/alternatives.md#what-would-make-us-reconsider" >}}).

## Open source and contributing {#oss}

### What licence, and what does it depend on? {#licence}

Apache-2.0 for this repository and for agent-platform; the reused projects keep their own licences.
At runtime the external dependencies are GitHub and the model providers — Z.ai, Anthropic, and
optionally Bedrock or Vertex AI — whose keys the platform holds and the sandboxes never see. The site
is built with Hugo and Hextra.

### Can I contribute? {#contributing}

Yes, and `task check` is the bar: it builds the platform's host profile, runs the host's own
validation on the composite tree, this repository's suites, the link check, the site build and the
doc-path check. Work in a branch or a worktree off `origin/main`, keep commits conventional and in
English, and expect a claim of "it works" to come with a live proof — on this project a feature is
landed only after one. For agent-platform itself, its `AGENTS.md` and its own `task check` apply.
