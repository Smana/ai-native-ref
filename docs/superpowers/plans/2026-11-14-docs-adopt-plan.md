# ai-native-ref documentation review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make this repository document only this deployment: nothing false at the Maku pin, versions and clusters on `status.md` alone, every product fact linked to Maku by the pinned tag, and guards in `task docs` that keep it so.

**Architecture:** Three pull requests now (correctness; rule 18 and the guards; the day-2 page), then one group after a Maku release carries the split pages and the pin is bumped here. Each guard is a check in one new script, `scripts/ci/check-site-contract.py`, written test-first, seen failing on today's pages, then the pages are fixed until it passes.

**Tech Stack:** Hugo (Hextra theme) under `website/`, Python 3 guards under `scripts/ci/`, `task docs`, `task links`, mermaid.

**Spec:** [`docs/superpowers/specs/2026-11-14-docs-review-design.md`](../specs/2026-11-14-docs-review-design.md). This plan is rows 1 and 3 of its sequencing table. The Maku half is [`2026-11-14-docs-maku-plan.md`](2026-11-14-docs-maku-plan.md).

## Global Constraints

- Work in a git worktree from `origin/main`; rebase onto a freshly fetched `origin/main` before every push. Commits are conventional, in English, with no trailers.
- `task check` is the evidence. On a machine where its known environment-bound suites fail at `test`, run `task links docs sources` and say so, with both outputs.
- Every site page follows [`docs/docs-style.md`](../../docs-style.md). A moved or deleted page keeps its URL through `aliases:` and keeps each `{#id}` another page or the host links (rule 14).
- The product is **Maku**; the factory, a room and the model gateway are its components. "Model gateway" is the reader's term; `agent-router` appears in manifests and paths only. "Agent Factory" survives only in the release names `Agent Factory v1` to `v3`.
- A Maku version, or which cluster is active, appears on `status.md` and nowhere else, `README.md` included.
- aws-0 and gcp-0 alternate; one runs the factory at a time. gcp-0 is active now. The sibling designs' changes, and the pin bump Task 9 waits for, are validated on aws-0; they go in base plus the aws-0 overlay.
- A page says what is true at the pin (v0.47.0): policy modes are `live`, `shadow`, `"off"`; `class_unarmed` appears only as the reason code.
- A site page never restates a Maku table (fields, reason codes, commands, config keys). It gives this platform's values and one link.
- Links to the host stay absolute (`https://cnref.ogenki.io/…`) and few.
- No guard takes a list of pages or lines: exemptions are `status.md`, `decisions/`, or the page's own front matter.

## Review Focus

No guard catches these. Each is pinned to the task that owns the pages.

1. **A sentence true at this pin turns false at the next, with no version in it.** "policy-bot's approval is the gate here" stays after the platform flips to `maku/merge-gate`. A reader expects a values page to match the manifests. Pinned: Task 8 step 2 (the upgrade-pin checklist names the three values pages to re-read) and Task 11 step 4 (each value cites its manifest path, which `verify-doc-paths.sh` checks exists).
2. **A values page restates a Maku table in under 500 words.** The ceiling is only a proxy. Pinned: Task 11 step 3 (the side-by-side diff against the Maku page).
3. **An alias covers the page but not its anchors.** A host link to `…/agent-factory/#the-parts` lands at the top of another page. Pinned: Task 10 step 1 (the anchor inventory, host included).
4. **A shortcode link resolves to a page or anchor that does not exist at the pinned tag.** The build cannot know. Pinned: Task 9 step 5 (fetch every generated URL once).
5. **"Example (the reference host)" hides a stale value.** The reader-first gate skips labelled examples, so a stale cluster name or mode inside one passes. Pinned: Task 3 step 4 and Task 11 step 4 (every labelled example re-read against the manifests).

---

## Pull request A: correctness, at the v0.47.0 pin (spec defects 1 to 8, 16 to 18)

### Task 1: The pin and the active cluster have one home

**Files:**
- Create: `scripts/ci/check-site-contract.py`, `scripts/ci/tests/test-check-site-contract.py`, `website/layouts/_shortcodes/maku-version.html`
- Modify: `website/hugo.yaml` (`params.makuVersion`), `website/content/docs/status.md`, `taskfile.yaml` (the `docs` task), `docs/docs-style.md` ("The gate")

**Interfaces:**
- Produces: `python3 scripts/ci/check-site-contract.py [ROOT]`, exit 0 or 1, findings as `file:line: <rule>: <match>` like the reader-first gate. Rules added here: `pin` and `active cluster`. Later tasks add rules to the same script and cases to the same test.
- Produces: `params.makuVersion: v0.47.0` in `website/hugo.yaml`; the shortcode `{{< maku-version >}}`, which prints it; `activeCluster: gcp-0` in `status.md`'s front matter.

- [ ] **Step 1: Write the failing tests** in `scripts/ci/tests/test-check-site-contract.py`, in the style of `test-check-reader-first.py` (a temporary tree, `check(name, condition)`)

```python
def test_pin_must_equal_chart_tag():
    tree(hugo="params:\n  makuVersion: v0.46.0\n", values='tag: "v0.47.0@sha256:abc"\n')
    assert "pin: v0.46.0 != v0.47.0" in run()

def test_pin_equal_passes():
    tree(hugo="params:\n  makuVersion: v0.47.0\n", values='tag: "v0.47.0@sha256:abc"\n')
    assert "pin" not in run()

def test_active_cluster_must_equal_fence():
    tree(fence="factory: aws-0\n", status="---\nactiveCluster: gcp-0\n---\n")
    assert "active cluster: gcp-0 != aws-0" in run()
```

`values` is `tooling/base/agent-factory/helm-values-configmap.yaml` (the first `tag:` under the comment `maku v…`); `fence` is `.github/agent-factory.yaml`.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 scripts/ci/tests/test-check-site-contract.py`. Expected: fails, the script does not exist.

- [ ] **Step 3: Write `check-site-contract.py`** with `check_pin(root) -> list[str]` and `check_active_cluster(root) -> list[str]`, and add it to `task docs` after `check-reader-first.py`.

- [ ] **Step 4: Run the guard on the tree to see it fail**

Run: `python3 scripts/ci/check-site-contract.py`. Expected: `pin: <unset> != v0.47.0` and `active cluster: <unset> != gcp-0`.

- [ ] **Step 5: Fix `status.md`**

- Front matter: `activeCluster: gcp-0`, `lastVerified` set to the day of the change.
- "Current release" paragraph: "Maku {{< maku-version >}}" replaces "Maku v0.41.1"; the harness and bridge sentence states what the manifests pin, read from `tooling/base/agent-factory/` at the commit.
- New section `## Clusters {#clusters}`, after "Available": a two-row table (aws-0, gcp-0: cloud, what it proves), one sentence on the alternation ("One cluster runs the factory at a time. The owner finishes a phase of work on one, then switches, which proves the platform on both."), and "Active: gcp-0", which the guard holds equal to the fence.

- [ ] **Step 6: Verify and commit**

Run: `python3 scripts/ci/tests/test-check-site-contract.py && task docs`. Expected: both exit 0.
`git commit -m "docs(site): the Maku pin and the active cluster live on the status page, held by a guard"`

### Task 2: Stale versions and stale Maku links (defects 1, 3)

**Files:**
- Create: `website/layouts/_shortcodes/maku.html`
- Modify: `README.md:103`, `docs/runbooks/agent-factory/README.md:9`, `website/content/docs/reference/harness.md:23`, `website/content/docs/reference/factory-configuration.md`, `website/content/docs/how-it-works/roles.md:93`, `website/content/docs/reference/gate-reasons.md:81`

**Interfaces:**
- Produces: the shortcode `{{< maku "docs/factory.md#the-merge-gate" >}}`, which renders `https://github.com/Smana/maku/blob/<params.makuVersion>/<argument>`. It is used as a link target: `[the merge gate]({{< maku "docs/factory.md#the-merge-gate" >}})`. Task 9 converts every other Maku link and arms the raw-link rule.

- [ ] **Step 1: List the hits**

Run: `grep -rn -E 'Maku v0\.[0-9]+\.[0-9]+|maku/blob/v0\.' README.md docs/runbooks/agent-factory/README.md website/content/docs --include=*.md | grep -v -e decisions/ -e status.md`
Expected: seven lines.

- [ ] **Step 2: Fix**

Delete each version and link the status page instead ("the version this platform pins is on the [status page]"; in `README.md` an absolute link to `https://airef.ogenki.io/docs/status/`, on the site a `relref`). The two `blob/v0.38.0/` links become the `maku` shortcode with the same path and anchor; check each anchor exists at v0.47.0 with `git -C <maku> show v0.47.0:docs/factory.md | grep -n '<heading>'`.

- [ ] **Step 3: Verify and commit**

Run: the grep of step 1 (expected: nothing), then `task links docs`.
`git commit -m "docs: no Maku version outside the status page; the two stale Maku links follow the pin"`

### Task 3: The merge-policy pages are true at the pin (defects 4, 5, 18)

**Files:**
- Modify: `website/content/docs/use/guide/merge-policies.md` (l.37–127), `website/content/docs/operate/auto-merge-safety.md:13-21`, `website/content/docs/how-it-works/merge-gate.md:58-76`, `website/content/docs/use/guide/writing-a-good-task.md:103`, `website/content/docs/use/guide/merging.md:67`

- [ ] **Step 1: `use/guide/merge-policies.md`**

Reader: a maintainer who wants to see or change what merges without them. Sections kept, anchors unchanged: `#configuration` (the bound policies and modes of this platform, read from `tooling/base/agent-factory/resources/repository-*.yaml`), `#where`, `#change-a-class`, `#promote`, `#limits`. Rewritten: `#where` and `#change-a-class` describe a `MergePolicy` object and a binding under `Repository.spec.mergePolicies` (`name`, `mode`), with one example copied from `repository-cloud-native-ref.yaml`. Deleted: every `classes:` block in `.github/agent-factory.yaml`, the guided form, and `#starter` ("The starter policy and templates"), which v0.47.0 removed; its anchor moves onto `#change-a-class`.

- [ ] **Step 2: `operate/auto-merge-safety.md#go-live`**

"`shadow: true` under `repositories[].classes.<class>`" and "Switch the class to `live: true`" become a `mode:` change on the binding, shown as a two-line diff.

- [ ] **Step 3: Mode words**

`unarmed` as a mode becomes `"off"` on the three pages (`merge-gate.md#classes` keeps its anchor; its heading reads "Classes: live, shadow, off"). `class_unarmed` stays wherever it is the reason code.

- [ ] **Step 4: Re-read every labelled example on these five pages against the manifests**

Run: `grep -n -i 'example (the reference host)' <the five files>`; each value under such a label matches `tooling/base/agent-factory/resources/` at the commit.

- [ ] **Step 5: Verify and commit**

Run: `grep -rn -E '^\s*classes:|shadow: true|live: true|\*\*unarmed\*\*' website/content/docs --include=*.md | grep -v decisions/` (expected: nothing), then `task docs`.
`git commit -m "docs(site): merge policies as bindings, the way the pinned Maku reads them"`

### Task 4: "Get started" stops contradicting the platform (defects 6, 7, 16)

**Files:**
- Modify: `website/content/docs/get-started/agent-factory.md` (l.34–63, 64–85, 108–121)

- [ ] **Step 1: Delete three things**

- "New here? The ideas in two minutes" (the duplicated glossary): replaced by one sentence linking Maku's glossary through `{{< maku "docs/concepts.md#glossary" >}}`.
- The "target architecture" figure and the sentence about its legend (l.78).
- In "More than one repository", the row that lists a multi-repository intake as still needed; the section says the factory serves the repositories listed on the status page.

Keep every `{#id}` and heading other pages link: run `grep -rn 'agent-factory/#\|agent-factory.md#' website/content README.md` first and keep those targets.

- [ ] **Step 2: Verify and commit**

Run: `task docs`.
`git commit -m "docs(site): the overview drops its glossary copy, the target figure and a stale limitation"`

### Task 5: Cluster statements, the README, the runbooks README (defects 8, 17)

**Files:**
- Modify: `README.md`, `docs/runbooks/agent-factory/README.md` (title, "State" l.7–40), `docs/runbooks/agent-factory/14-gcp-0-session.md:11`, `clusters/gcp-0-agent-platform/README.md:4-5`, `clusters/aws-0-agent-platform/README.md:4`, `.github/agent-factory.yaml` (its comment), `scripts/ci/check-reader-first.py`, `scripts/ci/tests/test-check-reader-first.py`, `docs/docs-style.md` ("The gate")

**Interfaces:**
- Produces: `README.md` is read by `check-reader-first.py` under the same rules as a site page.

- [ ] **Step 1: Write the failing test** in `test-check-reader-first.py`

```python
def test_readme_is_scanned():
    write("README.md", "# X\n\nThe factory runs on aws-0 since 2026-10-30.\n")
    out = run()
    assert "README.md:3: cluster name: aws-0" in out
    assert "README.md:3: date: 2026-10-30" in out
```

- [ ] **Step 2: Run it to see it fail**, then add `README.md` to the files `check-reader-first.py` scans, and run the gate on the tree. Expected: findings in `README.md` "Status and roadmap" (l.100–123) and "What has been measured".

- [ ] **Step 3: Rewrite `README.md`**

Reader: an evaluator arriving from GitHub. Target 900 words. Sections, in order: one paragraph of what this repository is; "What you get" (one table that merges today's "What you gain", "What you get" and "How it compares": capability, how, what it replaces); "One task, end to end" (the existing diagram); "Try it" (three links: Maku's quickstart, the site's Get started, the user guide); "Status" (one sentence and a link to the status page); "Repository layout"; "Turning it on in a cluster" (one sentence linking `reference/host-contract.md`, which keeps the only `flux resume` block); "Validating a change"; "Support this work"; "License". Deleted: "What has been measured" (its figures are already in `docs/superpowers/specs/`; link the latest cost snapshot), every version, every cluster name, every date.

- [ ] **Step 4: Fix the four other pages**

| Page | Change |
|---|---|
| `docs/runbooks/agent-factory/README.md` | Title without a cluster name; the "State" section deleted, replaced by one line linking the status page's `#clusters`. |
| `14-gcp-0-session.md:11` | "gcp-0 was torn down" becomes a dated record: "On 2026-10-29 the factory moved off gcp-0 for a phase of work on aws-0." |
| `clusters/*/README.md` | "ran the factory until its teardown" becomes "runs the factory in alternation with the other cluster; the status page names the active one." |
| `.github/agent-factory.yaml` | The comment loses the session reference; it says the status page's active cluster must equal this value. |

- [ ] **Step 5: Verify and commit**

Run: `wc -w README.md` (at most 900), `python3 scripts/ci/tests/test-check-reader-first.py`, `task links docs sources`.
`git commit -m "docs: one README table, no cluster or version outside the status page"`

## Pull request B: rule 18, the vocabulary and the guards

### Task 6: The product is Maku (DOC2, DOC3)

**Files:**
- Modify: `docs/docs-style.md` (rule 18, "The gate"), `scripts/ci/check-site-contract.py`, its test, and the pages the guard reports under `website/content/docs/` and `README.md`

**Interfaces:**
- Produces: rules `product name` and `maku version` in `check-site-contract.py`. Both skip `decisions/`; `maku version` also skips `status.md`. Both skip fenced code, front matter and link targets, as the reader-first gate does (import its `scan` helpers rather than copy them).

- [ ] **Step 1: Write the failing tests**

```python
def test_agent_factory_is_refused_as_a_product():
    page("use/x.md", "The Agent Factory opened a pull request.\n")
    assert "use/x.md:1: product name: Agent Factory" in run()

def test_release_names_pass():
    page("use/x.md", "Released as Agent Factory v3.0.0 and Agent Factory [v2](u).\n")
    assert "product name" not in run()

def test_maku_version_refused_outside_status():
    page("use/x.md", "Runs Maku v0.47.0. Uses agentgateway v1.6.0.\n")
    out = run()
    assert "use/x.md:1: maku version: Maku v0.47.0" in out and "agentgateway" not in out

def test_status_and_decisions_are_records():
    page("status.md", "Maku v0.47.0\n"); page("decisions/0001.md", "The Agent Factory, Maku v0.30.0\n")
    assert run() == ""
```

- [ ] **Step 2: See them fail, implement, run on the tree**

Patterns: `Agent Factory(?! \[?v[0-3]\b)`; `Maku v0\.\d+\.\d+` and `Smana/maku/(?:blob|tree|releases/tag)/v0\.\d+\.\d+` (the second is read in link targets too). Expected on the tree: about 40 `product name` findings and none for `maku version` (Task 2 cleared them).

- [ ] **Step 3: Rewrite rule 18** to the spec's text, with its Bad and Good lines swapped accordingly ("Bad: The Agent Factory opened a pull request for your issue. Good: Maku opened a pull request for your issue."), and document the new script under "The gate".

- [ ] **Step 4: Clear the findings and the gateway term**

"The Agent Factory" becomes "Maku" where the product acts, "the factory" where that component acts. Run `grep -rn -i 'agent-router\|agent gateway' website/content/docs --include=*.md | grep -v decisions/`: in prose both become "the model gateway"; `agent-router` stays inside backticks when it names the Deployment or a path. `status.md`'s sentence "The Agent Factory is a bundle of open-source tools" is rewritten: Maku is the product, the platform bundles it with agentgateway, gVisor and the others.

- [ ] **Step 5: Verify and commit**

Run: `python3 scripts/ci/tests/test-check-site-contract.py && task docs`.
`git commit -m "docs: Maku is the product and the model gateway is its name, held by the site contract"`

### Task 7: Word ceilings by page type (rule 9)

**Files:**
- Modify: `scripts/ci/check-site-contract.py`, its test, `docs/docs-style.md` (rule 9, rule 3), the front matter of the pages step 4 marks

**Interfaces:**
- Produces: the front-matter key `diataxis:` with values `tutorial`, `how-to`, `explanation`, `reference`, `chapter`, `values`; the rule `ceiling`, printed as `file: ceiling: <n> words, <type> allows <limit>`. Limits: `chapter` 600, `values` 500, `tutorial` and `how-to` 1,200, `explanation` 1,500, `reference` none. Words are the body's, front matter and fenced code excluded. A page with no `diataxis` is not checked (see "Waiting", W3). The key is not Hugo's `type`, which selects a layout.

- [ ] **Step 1: Write the failing tests**

```python
def test_over_ceiling_fails():
    page("operate/x.md", "word " * 1300, front="diataxis: how-to")
    assert "operate/x.md: ceiling: 1300 words, how-to allows 1200" in run()

def test_values_page_is_500():
    page("reference/x.md", "word " * 501, front="diataxis: values")
    assert "values allows 500" in run()

def test_reference_and_untyped_pass():
    page("reference/y.md", "word " * 9000, front="diataxis: reference"); page("use/z.md", "word " * 9000)
    assert "ceiling" not in run()

def test_unknown_type_fails():
    page("use/w.md", "x", front="diataxis: essay")
    assert "use/w.md: ceiling: unknown diataxis: essay" in run()
```

- [ ] **Step 2: See them fail, implement `check_ceilings(root)`, run the tests.**

- [ ] **Step 3: Add to rule 9** the `values` limit and the sentence "A page declares its type in `diataxis:`; the gate reads it."

- [ ] **Step 4: Mark the pages that already fit**

Run a one-off count (`python3 scripts/ci/check-site-contract.py --report`, a flag that prints every page's body word count and exits 0). Mark each page whose count is under the limit of its evident type; leave the others unmarked for Tasks 11 and 12. Do not mark a page with a looser type to make it fit.

- [ ] **Step 5: Verify and commit**

Run: `task docs`. Expected: exit 0.
`git commit -m "docs(site): rule 9's limits are checked for every page that declares its type"`

## Pull request C: day 2

### Task 8: `operate/day-2.md`

**Files:**
- Create: `website/content/docs/operate/day-2.md`
- Modify: `website/content/docs/operate/_index.md` (a sixth card; the description names operating, not only tuning)

- [ ] **Step 1: Write the page**

Reader: the operator of this host, on a bad day or an upgrade day. `diataxis: how-to`, target 800. Sections: "Stop everything" (the kill switch: the one action, what it stops, the runbook); "Upgrade Maku" (the pins in this repository by path: the chart tag in `tooling/base/agent-factory/helm-values-configmap.yaml`, `params.makuVersion` in `website/hugo.yaml`, `HOST_REF`; what `task check` proves; where the live check is recorded); "Restore" (the room database and what a rebuild loses; the runbook); "Switch the active cluster" (the fence file and the status page change together; the guard refuses one without the other). Each section ends with one link to Maku's operations page through the `maku` shortcode and one to its runbook. No alert or metric table.

- [ ] **Step 2: The upgrade checklist** in "Upgrade Maku", as a numbered list: bump the chart tag and `params.makuVersion` together; re-read the three values pages (`use/guide/merge-policies.md`, `how-it-works/merge-gate.md`, `operate/auto-merge-safety.md`) against the new manifests; set `lastVerified` on `status.md`.

- [ ] **Step 3: Verify and commit**

Run: `task links docs`. Expected: exit 0, the page under 1,200 words.
`git commit -m "docs(site): a day-2 page for this host: stop, upgrade, restore, switch cluster"`

---

## After a Maku release carries the split pages and the pin is bumped here

The pin bump is its own pull request, validated on aws-0, and not part of this plan. Tasks 9 to 12 start from the commit that carries it: the docs version never leads the image tag.

### Task 9: Every Maku link follows the pin (DOC4)

**Files:**
- Modify: `scripts/ci/check-site-contract.py`, its test, every site page with a Maku link (ten files outside `status.md` and `decisions/`, plus `status.md`'s 21)

**Interfaces:**
- Produces: the rule `raw maku link`: `github.com/Smana/maku/(blob|tree)/` in a page source fails, outside `decisions/`. Links to a release, an issue or a pull request pass.

- [ ] **Step 1: Write the failing test**

```python
def test_raw_maku_link_fails():
    page("use/x.md", "[cli](https://github.com/Smana/maku/blob/main/docs/cli.md)\n")
    assert "use/x.md:1: raw maku link" in run()

def test_shortcode_release_and_issue_links_pass():
    page("use/x.md", '[a]({{< maku "docs/cli.md" >}}) [b](https://github.com/Smana/maku/releases/tag/v0.47.0) [c](https://github.com/Smana/maku/issues/51)\n')
    assert "raw maku link" not in run()
```

- [ ] **Step 2: See it fail, implement, run on the tree** (expected: about 30 findings).

- [ ] **Step 3: Convert each link** to the shortcode, pointing at the page that owns the text after Maku's split (`docs/reference/…`, `docs/operations/…`, `docs/hardening.md`), never at a `moved` stub.

- [ ] **Step 4: `status.md`'s release links** to a Maku tag pass the `raw maku link` rule but not `maku version` outside `status.md`; they stay on `status.md` only.

- [ ] **Step 5: Fetch every generated URL once**

Run: `cd website && hugo --gc --minify && grep -rhoE 'https://github.com/Smana/maku/blob/[^"#]+(#[^"]*)?' public | sort -u | while read -r u; do curl -s -o /dev/null -w "%{http_code} $u\n" "${u%%#*}"; done`
Expected: every line starts with `200`. For each URL with a fragment, confirm the heading exists at the tag with `git -C <maku> show <tag>:<path> | grep -n '^#'`.

- [ ] **Step 6: Verify and commit**

Run: `task links docs`.
`git commit -m "docs(site): every link to Maku is built from the pinned version"`

### Task 10: "Get started" becomes a path

**Files:**
- Modify: `website/content/docs/get-started/_index.md`, `website/content/docs/how-it-works/_index.md`, `website/content/docs/how-it-works/providers.md`
- Delete: `website/content/docs/get-started/agent-factory.md` (its URL added to `aliases:` of `how-it-works/_index.md`)

- [ ] **Step 1: Inventory the anchors**

Run: `grep -rn 'get-started/agent-factory' website/content README.md docs` and, in a checkout of the host, `git grep -n 'airef.ogenki.io/docs/get-started'`. Each `#anchor` found gets a `{#id}` on the section that takes the text.

- [ ] **Step 2: `get-started/_index.md`**

Reader: someone who has never run it. `diataxis: tutorial`, target 500. Three numbered steps: try it on a laptop (Maku's quickstart, through the shortcode); deploy it on the host (the host contract and Maku's install page); hand over a first task (the user guide's "Your first task"). One diagram of the three steps. Deleted: the parts table (it is in `how-it-works/_index.md`).

- [ ] **Step 3: Dissolve `agent-factory.md`**

| Section | Goes to |
|---|---|
| What it is; Architecture (the remaining figure); The parts | `how-it-works/_index.md`, merged with its parts table, one table |
| "Why self-host at all" (in `_index.md` today) | `how-it-works/providers.md` |
| More than one repository | One sentence on `how-it-works/factory.md`, linking the status page |
| Design documents | `how-it-works/_index.md`, last section |

- [ ] **Step 4: Verify and commit**

Run: `task links docs`; open `/docs/get-started/agent-factory/` in `hugo server` and confirm the redirect.
`git commit -m "docs(site): Get started is a three-step path; the overview joins How it works"`

### Task 11: The values pages

**Files:**
- Modify: `website/content/docs/use/guide/merge-policies.md`, `how-it-works/merge-gate.md`, `operate/auto-merge-safety.md` (400 words each); `reference/commands.md`, `reference/gate-reasons.md`, `reference/factory-configuration.md`, `reference/planner.md` (300 to 500 each); `reference/harness.md` (1,000, `diataxis: reference`)

- [ ] **Step 1: The shape of a values page**

`diataxis: values`. Three parts: one sentence of what the thing is, linking Maku's page through the shortcode; a table of this platform's values, each with the manifest path it is read from, in backticks; one sentence of why a value differs from Maku's default, when it does. Every existing `{#id}` stays, on the nearest remaining heading.

- [ ] **Step 2: Per page**

| Page | Keeps (this platform) | Deletes (Maku's) |
|---|---|---|
| `use/guide/merge-policies.md` | The bound policies and their modes per repository | How a policy is written, promoted, limited |
| `how-it-works/merge-gate.md` | Which gate status and Apps this platform uses; its daily cap | The evaluation order, the mode table, the reason table |
| `operate/auto-merge-safety.md` | The breaker and drill values set here; the Renovate adoption here | How the breaker, drills and recovery work |
| `reference/commands.md` | This host's URL and login command | Every command table |
| `reference/gate-reasons.md` | The reasons this platform's policies can produce, as a list of names | Each reason's meaning |
| `reference/factory-configuration.md` | The values in `tooling/base/agent-factory/resources/factory.yaml` that differ from the chart's defaults | The config table |
| `reference/planner.md` | The planner's model and repositories here | The settings table |
| `reference/harness.md` | The values set here | The settings table, linked |

- [ ] **Step 3: Diff against Maku**

For each page, open the Maku page it links at the pinned tag: no table on the site page has the same header row as a table there.

- [ ] **Step 4: Paths and examples**

Every value cites a path that `./scripts/ci/verify-doc-paths.sh` accepts; every "Example (the reference host)" block on these pages is re-read against that path.

- [ ] **Step 5: Verify and commit**

Run: `task links docs`. Expected: exit 0; each page under its ceiling.
`git commit -m "docs(site): the merge, command and configuration pages give this platform's values and link Maku"`

### Task 12: Measurements leave the site (rule 6)

**Files:**
- Modify: `website/content/docs/how-it-works/routing-and-cost.md` (5,422), `alternatives.md` (4,175), `gateways.md` (2,665), `website/content/docs/operate/tune-a-run.md` (3,044), `website/content/docs/status.md`
- Create: `docs/superpowers/specs/2026-11-14-routing-and-cost-measurements.md`, `docs/superpowers/specs/2026-11-14-alternatives-evaluations.md`

- [ ] **Step 1: Move, do not rewrite**

Each measurement table, cohort result and evaluation narrative moves verbatim to the matching file under `docs/superpowers/specs/`, with the commit and month it was read at. The site page keeps the reasoning and one sentence per moved block ("Measured in October 2026; the figures are in the repository's design records", linked by its GitHub URL).

| Page | Type | Target |
|---|---|---|
| `routing-and-cost.md`, `alternatives.md`, `gateways.md` | `explanation` | 1,500 each |
| `tune-a-run.md` | `how-to` | 1,200; each setting links `reference/harness.md` |
| `status.md` | none (a record) | 2,500: the "On the road to a factory" narrative and shipped-item history move to the release notes it already links |

- [ ] **Step 2: Word account**

`wc -w` of each site page plus its new record equals the old count within the linking sentences.

- [ ] **Step 3: Verify and commit**

Run: `task check` (or `task links docs sources`). Expected: exit 0; the four pages carry `diataxis` and pass.
`git commit -m "docs(site): measurements and evaluations move to the design records"`

---

## Waiting: not executed by this plan

| # | With | Change |
|---|---|---|
| W1 | Maku release N (workflows) | `how-it-works/roles.md` and the guide chapters that name roles or profiles: five roles, three workflows. |
| W2 | Maku release N+1 (merge policies) | `"off"` becomes `disabled`, `class_unarmed` becomes `no_policy_matched`, on the pages Task 3 and Task 11 touched. |
| W3 | The UX change | `use/slack.md` (1,500, the user's flow), `use/coding-clients.md` (1,200), the cheat sheet, the guide chapters; then `diataxis` becomes required on every page. The guide's chapters run up to 1,860 words against rule 9's 600: they are typed, and split or trimmed, in this rewrite and not before. |

## Self-review notes

- Spec coverage: defects 1–3 (Tasks 1, 2), 4–5 and 18 (Task 3), 6–7 and 16 (Task 4), 8 and 17 (Tasks 1, 5), DOC2 and DOC3 (Task 6), DOC4 (Tasks 2, 9), DOC5 (Tasks 1, 2, 5, 6), DOC12 (Tasks 1, 5), DOC13 (Tasks 1, 5, 6, 7, 9), the target table (Tasks 5, 8, 10, 11, 12).
- Two readings of the spec, stated: the `maku` shortcode lands in pull request A, because defect 3 needs it, and only its `raw maku link` guard waits for the pin bump; the active-cluster guard is added beyond the spec's guard table, because the fence file makes DOC12 checkable.
