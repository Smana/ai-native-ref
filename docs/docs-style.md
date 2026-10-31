# Docs style guide

How to write a page for [airef.ogenki.io](https://airef.ogenki.io/) (`website/content/docs/`).
It is for anyone who edits the site, people and agents alike. The reader is someone evaluating or
using the platform, who was not at any of our sessions.

`task docs` runs [`scripts/ci/check-reader-first.py`](../scripts/ci/check-reader-first.py), which
enforces rules 1, 4 and 5 (see [The gate](#the-gate)).

## The rules

**1. Write for someone who was not there.** No cluster names (`aws-0`, `gcp-0`), session dates,
proof or plan IDs (N6, AM4, F11, SP4 R13, AG8, OD-6), run IDs or people's handles in prose.

- Bad: "Proven live on `gcp-0` on 2026-10-29 (N6)."
- Good: "The scoper asks you a question before the run starts."

**2. Second person, present tense, active voice.** Warm and plain. No insider words ("programme",
"wave", "session switch", "drill") unless the page defines them.

- Bad: "A maintainer's approval is then consumed by the merge gate."
- Good: "You approve the pull request, and the merge gate merges it."

**3. One [Diátaxis](https://diataxis.fr/) type per page.** Tutorial (learn by doing), how-to (reach
a goal), reference (look something up), explanation (understand why). When a section wants
another type, link to a page of that type.

- Bad: a "How it works" page that ends with a table of every Helm value.
- Good: the explanation ends with one sentence, "Every setting is in the harness reference", linked.

**4. State lives on the status page.** One line per capability: Available, Experimental, Planned
or Known limitation. No other page says "proven live", "today", "not yet" or "since <date>", carries
a live badge, or keeps a UI bug in a callout.

- Bad, on a concept page: "**Live, proven end to end on 2026-10-29.**"
- Good, on `status.md`: "| RunLore hand-off | Available | … |"

**5. History is not documentation.** "We tried X", "renamed in v0.30.0", "since #238" and "moved
on 2026-10-16 (#2408)" go. The *why* lives in an ADR, and the page links to it once. An
evaluation may say when it was checked, to the month, with the commit it read.

- Bad: "Runs moved to agentgateway on 2026-10-16 (#2408)."
- Good: "Runs go through agentgateway (ADR-0053)", with the ADR linked. On an evaluation:
  "*Checked in October 2026 at `ac23328`.*"

**6. Setup-specific material goes off the site.**

| Material | Where it goes |
|---|---|
| Session evidence, pass or fail stories | `docs/runbooks/agent-factory/results-*.md` |
| Measurements and evaluations | `docs/superpowers/specs/` |
| Work still to do | `docs/superpowers/plans/` or an issue |
| Billing and wallet details | nowhere public |

- Bad, on a how-to: "The aws-0 session found the median hand-off at 150 s."
- Good: the same line in `results-aws-0-2026-10-30.md`, and nothing on the site.

**7. Issue and PR links only as tracking links**, on the status page's known limitations.

- Bad: "not under `--needs-me` yet ([maku#51])".
- Good, on `status.md`: "`--needs-me` misses split proposals (tracked in maku#51)."

**8. The reference host's values are examples, and labelled so.** Write "Example (the reference
host):" before a repository name, a class such as `docs-links`, a hostname, a cluster or a dollar
figure. Everywhere else, use placeholders: `owner/repo`, `rooms.example`, `llm.<your-domain>`.
The label covers the rest of its paragraph, list item or table row, and the block after it
when the labelled paragraph ends with ":". An `<!-- example -->` line covers the block below it.

- Bad: "The base URL is `https://llm.priv.aws.ogenki.io/v1`."
- Good: "Example (the reference host): `https://llm.priv.aws.ogenki.io/v1`."

**9. One idea per paragraph, at most four sentences.** Split a sentence over 35 words. A book
chapter runs 300 to 600 words, a how-to under 1,200, an explanation under 1,500. A longer reference
has a table of contents and anchors.

- Bad: one paragraph covering the label, the review and the merge.
- Good: three paragraphs, one each.

**10. Define a term before its first use, or link the glossary.** Never show a reason code before
the reader knows what it reports.

- Bad: "The gate refuses it (`no_approving_verdict`)."
- Good: "The gate merges only after the reviewer agent approves. Without that approval it hands the
  pull request to you, with the reason `no_approving_verdict`."

**11. Tables only for real lookups.** At most four columns and 25 words a cell. Steps are a
numbered list; a story is prose.

- Bad: a six-column roles table with 60-word cells.
- Good: Role / What it does / Writes code?, with the triggers in the reference.

**12. Lead with what the reader does**, then the mechanism.

- Bad: "Rows 1 to 12 of the decision table are evaluated; on `stale_approval` …"
- Good: "Approve the current head. If you approved an older commit, approve again."

**13. Say it once.** Each fact has one home; other pages link to it in one sentence.

- Bad: the merge-gate rule restated on six pages.
- Good: "The merge gate decides what merges without you", the page linked once.

**14. Moving a page keeps its old URLs working.** Add every old path to the moved page's
`aliases:`. An alias covers the page, not its anchors: keep each `{#id}` other pages or the
host link to.

- Bad: renaming `user-guide.md` to `use/guide/_index.md` with no alias.
- Good:

  ```yaml
  aliases:
    - /docs/platform/ai-platform/agents/use/user-guide/
  ```

**15. A site page is linked with `relref`; a repository file with a GitHub URL.** Hugo fails the
build on a broken `relref`, so a site link cannot rot silently. A runbook or spec is not on the
site, so it takes a `https://github.com/Smana/ai-native-ref/blob/main/…` URL. That URL 404s until
the file is on `main`: link a file the same pull request adds only once it has merged.

- Bad: `[guide](https://airef.ogenki.io/docs/use/guide/)` from another site page.
- Good: `[guide]({{< relref "/docs/use/guide/_index.md" >}})`.

**16. Images carry no state.** A diagram shows the current design, never its progress: no
"built / deployed / proven" legends. Alt text says what the reader sees, in under 40 words, and
no caption names a version or a real PR number.

- Bad: alt text "Slack intake, proven live on gcp-0".
- Good: alt text "Slack intake: a mention drafts an issue, a maintainer's check mark files it".

**17. A mermaid diagram stays between 2.5:1 and 1:1.5 (width to height).** Pick `LR` or `TB` by
shape, and fold a long chain into subgraphs, so the diagram reads at the page's width.

- Bad: `flowchart LR` with nine nodes in one row, rendered as a thin strip.
- Good: `flowchart TB` with three subgraphs of three nodes each.

**18. Agent Factory is the product; Maku is its controller.** Name Maku only when you mean that
project's components (`maku-factory`, the broker, the `maku` CLI).

- Bad: "Maku opened a pull request for your issue."
- Good: "The Agent Factory opened a pull request for your issue."

## The gate

[`scripts/ci/check-reader-first.py`](../scripts/ci/check-reader-first.py) runs in `task docs`
(and so in `task check`). It fails on a cluster name, an ISO date, "proven live", a handle or a
proof ID in `website/content/docs/**/*.md`. It does not read:

- the status page (`status.md`) and the decision records (`decisions/`);
- front matter, such as `lastVerified`;
- fenced code blocks;
- a labelled example (rule 8);
- link targets, `relref` shortcodes and bare URLs: a runbook file name may carry a date or a cluster;
- repository paths in backticks, such as `clusters/aws-0/flux/`;
- a handle in inline code, such as the Slack app's `@factory link`.

When it fails, rewrite the sentence for a reader who was not there, move it to the status page or
off the site (rule 6), or label it as an example (rule 8). Do not add an allowlist.
