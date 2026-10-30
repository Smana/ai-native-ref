# Truthful costs, PR 4: the nightly price drift check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A nightly GitHub Actions workflow compares every `meter.prices` row with genai-prices,
LiteLLM and models.dev, and keeps one issue labelled `prices-drift` in step with what it finds. It
never edits the table and never opens a pull request.

**Architecture:** `scripts/ci/check-price-drift.py` reads `meter.prices` from the factory's values
ConfigMap and fetches the three catalogs. It compares each row's four rates through a mapping held in
the script. The result is a list of findings, and from it an issue action: open, update, close or
nothing. The comparison and the issue text are pure functions. A suite tests them on committed
excerpts of the three catalogs, with the network and `gh` stubbed. Fetching and `gh` are thin layers,
and every fetch and parse happens before the first `gh` call, so a catalog that cannot be read fails
the run and leaves the issue alone. `.github/workflows/price-drift.yaml` runs the script nightly and
on dispatch, with `contents: read` and `issues: write`.

**Tech Stack:** Python 3.12-compatible (the `ubuntu-latest` runner's `python3`), the standard library
and PyYAML; the `gh` CLI; GitHub Actions; the suite runs under `scripts/ci/run-tests.sh` inside
`.composite/`.

**Spec:** [the truthful costs design](../specs/2026-10-22-truthful-costs-design.md), decision TC10,
"The drift check" under Interfaces, PR 4 in "Pull requests, in order", offline proof 14 and live
proof 6.

**Out of PR 4:** PRs 1 to 3 (the charge rule, the USD ledger, the release pin, and `source` and
`checkedAt` on each row). Anthropic's Models API as a source of new models (the spec's "Not in this
design"). Editing the table or opening a pull request from the check (TC10's rejected option).

### This plan's rulings

The spec leaves "the catalogs' exact URLs and field names, and the fixtures; the cron minute and the
issue body's layout" to the builder. These rulings settle those points and the smaller ones the
prototype ran into.

| # | Ruling | Why |
|---|---|---|
| R1 | **genai-prices' live feed is v2**: `https://raw.githubusercontent.com/pydantic/genai-prices/main/prices/new_data/v2/data.json`, not `prices/data.json` | genai-prices' `prices/README.md` says "v1 is frozen". `prices/data.json` was last written 2026-07-25. It lists no 5.5 model and no `zai` provider, so every row would read as missing |
| R2 | **The mapping is four tables in the script.** `MAPPING` holds each row's key in each catalog, by the catalog's own id, plus the provider's pricing page. `ABSENT` holds the rows a catalog lacks, each with its reason. `TIERS` holds the context tier a row is priced at. `ACCEPTED` holds deviations, each pinned to the catalog value it accepts, with its reason | This is the spec's mapping row: "each row's key in each catalog. A row that differs on purpose names what it matches … or an accepted deviation with its reason". Keys are exact ids, not genai-prices' `match` clauses, so the mapping says which entry it reads. A deviation pinned to a value becomes a finding again if the catalog moves again |
| R3 | **Z.ai rows read the pay-as-you-go entries**: genai-prices `zai`, models.dev `zai` and LiteLLM `zai/…` | genai-prices' `zhipuai` prices are converted from CNY (GLM-5.3 at 1.103 / 0.276 / 3.862). models.dev's `zai-coding-plan` rows are priced 0, as the spec notes |
| R4 | **A declared absence is not a finding while the key is absent. It becomes one when the catalog lists the key.** Today LiteLLM has no `zai/glm-5.3-flashx`, only `tencent/glm-5.3-flashx` | A permanent "not listed" finding would keep the issue open forever, against "the first clean run closes it". When the key appears, the row should start being compared |
| R5 | **How rates are compared.** Rates are Decimals, read from the JSON literal (`parse_float=Decimal`) or from YAML through `str`, and rounded `ROUND_HALF_UP` to 4 decimals. The absent-means-0 rule applies to `cacheWrite` only. A tiered row reads the tier whose threshold is its own, and falls back to the flat rate. genai-prices' dated prices use the last entry in force on the run's UTC date. Batch `price_variants` and time-of-day prices are not list prices, so they are ignored | Decimals avoid float noise: LiteLLM's `2.6e-07` × 1e6 is exactly 0.26. The spec's absent rule covers cache writes Z.ai does not bill. AG10 already fails a pinned model's row that lacks `input`, `cacheRead` or `output`, or an Anthropic row that lacks `cacheWrite`. If a catalog drops a tier, the row then shows as a difference, which a human should see |
| R6 | **A catalog that lists none of the rows fails the run**, as one that cannot be parsed does | That means a moved or reshaped feed (R1's v1 file reads that way), not six missing rows. A failed run says "fix the script"; an issue would say "check six prices" |
| R7 | **The Source column** shows the row's `source` when it has one, and otherwise the provider's page from the mapping | PR 3 adds `source`. PR 4 depends on nothing (the spec's PR table), and until PR 2's release the factory's strict decoder rejects a `source` key |
| R8 | **The issue.** It has a fixed title. Its body depends only on the sorted findings: no date, no run link. The same findings therefore give the same body, and the issue is not edited. The script acts on the oldest open `prices-drift` issue. It creates the label (`--force`) only when it opens an issue, and closes an issue with a fixed comment | Editing an issue to the same content would notify its watchers every night. The label step copies the host's `notify-main-broken` job. Live proof 6 expects at most one issue |
| R9 | **Fetching and `gh` are thin layers in the script.** Every fetch and parse comes before the first `gh` call. There is no retry. The workflow sets `GH_REPO` | This gives the spec's "a catalog that cannot be fetched or parsed fails the run … and leaves the issue alone" by construction, and one unit test covers it. A failed night notifies the owner, and the next night tries again. `GH_REPO` is the host's lesson from `notify-main-broken` |
| R10 | **The workflow** runs at `17 4 * * *` (04:17 UTC). It has a concurrency group, installs PyYAML the way `ci.yaml` does, and pins `actions/checkout` by SHA, as `ci.yaml` does | Off the hour, because GitHub delays scheduled runs at busy times. The concurrency group stops a dispatched run and the scheduled run from both opening an issue |
| R11 | **No suite checks the workflow's shape.** actionlint checks it when it is written, and the first `workflow_dispatch` run after merge proves it (live proof 6) | Suites run inside `.composite/`, whose `.github/` is the host's (`host-profile.sh` copies `scripts/`, not `.github/`), so a suite cannot read this repository's workflow there |
| R12 | **Fixtures** live in `scripts/ci/tests/price-drift-fixtures/`. They are excerpts of the 2026-10-22 catalogs, one model per line, and include entries the mapping must not read: `zhipuai`, `zai-coding-plan`, `tencent/glm-5.3-flashx`, and two Anthropic decoys listed before the real rows (genai-prices `quicksilverpro`'s `claude-opus-5-5`, LiteLLM `us-gov.anthropic.claude-opus-5-5`), so a reader matching by model id alone fails the "all agree" case. The suite compares against its own copy of the table. On the real tree it checks only that `meter.prices` loads | The host names test data `<name>-fixtures` (`alertmanager-fixtures`). A price edit in a later pull request must not break this suite; the nightly run is where the real table meets the real catalogs |
| R13 | **A row with no mapping entry** is a nightly finding, one per catalog. It does not fail anything at pull-request time | The spec lists "a row the mapping lacks" as a finding. The comment above `prices:` now tells whoever adds a row to add its entry in the same pull request |

**Measured 2026-10-22** with a prototype in `$SCRATCH/drift/` (the code below is that prototype's):

- **The URLs.** All three returned 200: genai-prices v2 (774 KB), LiteLLM (2.97 MB) and models.dev
  (6.05 MB). The script's `fetch` (urllib, `User-Agent` set) read all three live in a `--dry-run`:
  `check-price-drift: 6 rows, 3 catalogs, 0 finding(s); issue: nothing`.
- **Today's table against today's catalogs.** No finding. Every row a catalog lists agrees on all
  four fields:

  | Row (input / cacheRead / cacheWrite / output) | genai-prices v2 | LiteLLM | models.dev |
  |---|---|---|---|
  | `glm-5.3` 1.40 / 0.26 / — / 4.40 | `zai/GLM-5.3` agrees; no cache-write field | `zai/glm-5.3` agrees; cache write 0 | `zai/glm-5.3` agrees; cache write 0 |
  | `glm-5.3-flashx` 0.37 / 0.075 / — / 1.25 | `zai/GLM-5.3-FlashX` agrees | **absent** (only `tencent/glm-5.3-flashx`): declared in `ABSENT` | `zai/glm-5.3-flashx` agrees |
  | `glm-5.3-flash` 0.15 / 0.03 / — / 0.50 | `zai/GLM-5.3-Flash` agrees on the entry dated 2026-09-10; the earlier one is the launch promotion at half price | `zai/glm-5.3-flash` agrees | `zai/glm-5.3-flash` agrees |
  | `claude-opus-5-5` 4.00 / 0.20 / 5.00 / 20.00 | agrees | agrees | agrees |
  | `claude-sonnet-5-5` 2.00 / 0.10 / 2.50 / 10.00 | agrees | agrees | agrees |
  | `claude-haiku-5-5` 0.50 / 0.05 / 0.625 / 2.50 | agrees at the tier starting at 100000; base 0.10 / 0.01 / 0.125 / 0.50 | agrees on the `_above_100k_tokens` fields | agrees on the tier `{type: context, size: 100000}` |

- **The frozen v1 file** (R1) has none of these rows, and the check refuses it:
  `genai-prices: lists none of meter.prices' rows`.
- **The suite.** 30 checks pass on the prototype, and again when the files are copied into this
  worktree's `.composite/` and run there. Twelve mutants of the script each fail at least one check,
  among them: no tier, no rounding, the first dated price instead of the last, `ABSENT` ignored,
  `ACCEPTED` ignored, `gh` called before the fetches, and a catalog with no rows accepted.
- **The workflow.** actionlint 1.7.12 reports nothing.
- **Baseline `task check`** on this branch (`origin/main` plus the spec): `21 passed, 1 skipped,
  0 failed`, `exit=0`. The skip is `test-agent-traces-filter` when no Docker daemon is running.

## Global Constraints

- **Branch:** work on `feat/price-drift-check`, which carries the spec and this plan, in its own
  worktree. In a new worktree, run `mise trust mise.toml` once. Rebase onto a freshly fetched
  `origin/main` before every push.
- **`$SCRATCH`** is a scratch directory outside the repository. It holds two helpers:
  - `check.sh <worktree>` runs `task check` with a `python3` that has PyYAML ahead of mise's. It
    logs to `$SCRATCH/check-<worktree directory name>.log` and ends the log with `exit=N`.
  - `run-suite.sh <command…>` runs one command with that `python3`.
  The `python3` on `PATH` lacks PyYAML, so every Python command below goes through one of the two
  helpers.
- **`task check` is the evidence** (AGENTS.md). Never claim done without its log.
- **`__pycache__/` is ignored on main since #97, not on this branch until it rebases.** Run `export PYTHONDONTWRITEBYTECODE=1` in the shell first,
  and `git add` named paths only, never `-A`.
- **The suite contract:** line 1 is the shebang and line 2 is `# requires: <tools>`. Exit 77 is a
  SKIP. Suites read the real tree and never the network. `run-tests.sh` runs them inside
  `.composite/` and finds them with `git ls-files`, so a new suite counts only once it is committed.
  `host-profile.sh` copies all of `scripts/` into the composite, fixtures included.
- **Python 3.12.** Nothing newer than the runner's `python3`; no dependency beyond PyYAML.
- **Host scripts are never vendored.** The script is this repository's own CI script, like
  `check-sources.sh`. It imports nothing from the host.
- **No new workload.** The check runs in CI only and nothing reaches a cluster, so the platform
  constitution's workload rules gain nothing new to apply to.
- **Actions are pinned by SHA with a version comment**, as in `ci.yaml`:
  `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7`.
- **Commits** are conventional, in English, with **no trailers**.
- **Verbatim from the spec:**
  - TC10: "A scheduled GitHub Actions workflow runs `scripts/ci/check-price-drift.py` against
    genai-prices, LiteLLM and models.dev. On a mismatch or a missing row it opens or updates one issue
    labelled `prices-drift`." A pull request is the rejected option: "Catalogs copy the providers'
    page mistakes: a human confirms against the provider's page."
  - Workflow: "`.github/workflows/price-drift.yaml`: nightly `schedule` and `workflow_dispatch`;
    `contents: read`, `issues: write`".
  - Compared: "Every `meter.prices` row's `input`, `cacheRead`, `cacheWrite` and `output`, equal when
    they round to the same 4 decimals in USD per M. Our absent `cacheWrite` matches a catalog's absent
    or 0".
  - Finding: "A field that differs; a row a catalog lacks; a row the mapping lacks".
  - Outcome: "The first clean run closes it. A catalog that cannot be fetched or parsed fails the
    run, which notifies, and leaves the issue alone".
  - Network: "Only the workflow's fetches and its `gh` calls. The comparison and the issue action
    (open, update, close, nothing) are in the script and tested on fixtures".
  - Offline proof 14: "The drift script's tests, on trimmed fixtures of the three catalogs: they
    agree; Sonnet 5.5's cache read at $0.20 … is one finding; a row a catalog lacks; Haiku's tier;
    Z.ai's absent `cacheWrite`; the issue action for each case, the same findings twice giving the
    same body."

## File structure

| File | Change | Responsibility |
|---|---|---|
| `scripts/ci/check-price-drift.py` | create | Reads `meter.prices`, fetches the three catalogs, compares them through the mapping, keeps the issue |
| `scripts/ci/tests/price-drift-fixtures/genai-prices.json`, `litellm.json`, `models-dev.json` | create | Excerpts of each catalog as of 2026-10-22 |
| `scripts/ci/tests/test-check-price-drift.py` | create | The suite: 35 checks with no network access (offline proof 14) |
| `.github/workflows/price-drift.yaml` | create | Nightly and on dispatch; `contents: read`, `issues: write` |
| `tooling/base/agent-factory/helm-values-configmap.yaml` | modify: the comment above `prices:` | A new row needs its mapping entry |
| `website/content/docs/platform/ai-platform/routing.md` | modify: one paragraph | Tells readers of the price table about the check |
| `docs/superpowers/specs/2026-10-22-truthful-costs-design.md` | modify: "Left to the builder" | Records R1, R2, R6, R8 and R10 |

---

### Task 1: The comparison, its fixtures and its tests

**Files:**
- Create: `scripts/ci/tests/price-drift-fixtures/genai-prices.json`, `litellm.json`, `models-dev.json`
- Create: `scripts/ci/tests/test-check-price-drift.py`
- Create: `scripts/ci/check-price-drift.py`

**Interfaces:**
- Consumes: `config.meter.prices` inside the `values.yaml` key of the ConfigMap at
  `tooling/base/agent-factory/helm-values-configmap.yaml`. Each row is a mapping with any of
  `input`, `cacheRead`, `cacheWrite`, `output` (numbers) and, after PR 3, `source` (a URL) and
  `checkedAt`.
- Produces (Task 2 relies on these):
  - `VALUES: PurePosixPath`, `FIELDS: tuple[str, ...]` = `("input", "cacheRead", "cacheWrite", "output")`.
  - `CATALOGS: dict[str, str]`, catalog name to URL. The names are `"genai-prices"`, `"LiteLLM"` and
    `"models.dev"`.
  - `MAPPING`, `ABSENT`, `TIERS`, `ACCEPTED` (R2), and `READERS: dict[str, callable]`.
  - `class CatalogError(ValueError)`.
  - `class Finding(NamedTuple)`: `model, catalog, field, ours, theirs, key, source`, all `str`.
    `field` is `"—"` when the finding is about the whole row.
  - `load_prices(text: str) -> dict[str, dict]`: model to `{field: Decimal, "source": str}`. Raises
    `ValueError` when the ConfigMap has no `config.meter.prices`.
  - `parse_catalog(name: str, text: str) -> object`: the JSON, with floats as `Decimal`. Raises
    `CatalogError`.
  - `usd(d: Decimal | None) -> str`: `"absent"`, or at most 4 decimals and at least 2.
  - `compare(prices, catalogs, today: date, mapping=MAPPING, absent=ABSENT, tiers=TIERS,
    accepted=ACCEPTED) -> list[Finding]`, sorted by model, then catalog, then field. Raises
    `CatalogError`.

- [ ] **Step 1: Write the fixtures and the failing test**

`scripts/ci/tests/price-drift-fixtures/genai-prices.json` (from
`prices/new_data/v2/data.json`, 2026-10-22):

```json
[
  {"id": "quicksilverpro", "name": "QuickSilver Pro", "models": [
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "match": {"equals": "claude-opus-5-5"}, "context_window": 1000000, "prices": {"input_mtok": 1, "cache_write_mtok": 1.25, "cache_read_mtok": 0.05, "output_mtok": 5}}
  ]},
  {"id": "anthropic", "name": "Anthropic", "pricing_urls": ["https://www.anthropic.com/pricing#api"], "models": [
    {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5", "prices": {"input_mtok": {"base": 0.1, "tiers": [{"start": 100000, "price": 0.5}]}, "cache_write_mtok": {"base": 0.125, "tiers": [{"start": 100000, "price": 0.625}]}, "cache_read_mtok": {"base": 0.01, "tiers": [{"start": 100000, "price": 0.05}]}, "output_mtok": {"base": 0.5, "tiers": [{"start": 100000, "price": 2.5}]}, "cache_write_1h_mtok": {"base": 0.2, "tiers": [{"start": 100000, "price": 1}]}, "web_searches_kcount": 10}},
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "prices": {"input_mtok": 4, "cache_write_mtok": 5, "cache_read_mtok": 0.2, "output_mtok": 20, "cache_write_1h_mtok": 8, "web_searches_kcount": 10}, "price_variants": [{"when": {"processing": "batch"}, "prices": {"input_mtok": 2, "cache_write_mtok": 2.5, "cache_read_mtok": 0.1, "output_mtok": 10, "cache_write_1h_mtok": 4}, "constraint": {"start_date": "2026-10-14"}}]},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "prices": {"input_mtok": 2, "cache_write_mtok": 2.5, "cache_read_mtok": 0.1, "output_mtok": 10, "cache_write_1h_mtok": 4, "web_searches_kcount": 10}}
  ]},
  {"id": "zai", "name": "Z.AI", "pricing_urls": ["https://docs.z.ai/guides/overview/pricing"], "models": [
    {"id": "GLM-5.3", "name": "GLM-5.3", "prices": {"input_mtok": 1.4, "cache_read_mtok": 0.26, "output_mtok": 4.4}},
    {"id": "GLM-5.3-Flash", "name": "GLM-5.3-Flash", "prices": [{"prices": {"input_mtok": 0.075, "cache_read_mtok": 0.015, "output_mtok": 0.25}}, {"constraint": {"start_date": "2026-09-10"}, "prices": {"input_mtok": 0.15, "cache_read_mtok": 0.03, "output_mtok": 0.5}}]},
    {"id": "GLM-5.3-FlashX", "name": "GLM-5.3-FlashX", "prices": {"input_mtok": 0.37, "cache_read_mtok": 0.075, "output_mtok": 1.25}}
  ]},
  {"id": "zhipuai", "name": "Zhipu AI", "pricing_urls": ["https://open.bigmodel.cn/pricing", "https://docs.bigmodel.cn/cn/guide/start/model-overview"], "models": [
    {"id": "GLM-5.3", "name": "GLM-5.3", "prices": {"input_mtok": 1.103, "cache_read_mtok": 0.276, "output_mtok": 3.862}}
  ]}
]
```

`scripts/ci/tests/price-drift-fixtures/litellm.json` (from `model_prices_and_context_window.json`,
2026-10-22; batch fields left out):

```json
{
  "us-gov.anthropic.claude-opus-5-5": {"input_cost_per_token": 4.8e-06, "cache_read_input_token_cost": 2.4e-07, "cache_creation_input_token_cost": 6e-06, "output_cost_per_token": 2.4e-05, "litellm_provider": "bedrock_converse", "mode": "chat"},
  "claude-opus-5-5": {"input_cost_per_token": 4e-06, "cache_read_input_token_cost": 2e-07, "cache_creation_input_token_cost": 5e-06, "output_cost_per_token": 2e-05, "cache_creation_input_token_cost_above_1hr": 8e-06, "litellm_provider": "anthropic", "mode": "chat"},
  "claude-sonnet-5-5": {"input_cost_per_token": 2e-06, "cache_read_input_token_cost": 1e-07, "cache_creation_input_token_cost": 2.5e-06, "output_cost_per_token": 1e-05, "cache_creation_input_token_cost_above_1hr": 4e-06, "litellm_provider": "anthropic", "mode": "chat"},
  "claude-haiku-5-5": {"input_cost_per_token": 1e-07, "cache_read_input_token_cost": 1e-08, "cache_creation_input_token_cost": 1.25e-07, "output_cost_per_token": 5e-07, "cache_creation_input_token_cost_above_1hr": 2e-07, "input_cost_per_token_above_100k_tokens": 5e-07, "cache_read_input_token_cost_above_100k_tokens": 5e-08, "cache_creation_input_token_cost_above_100k_tokens": 6.25e-07, "output_cost_per_token_above_100k_tokens": 2.5e-06, "litellm_provider": "anthropic", "mode": "chat"},
  "zai/glm-5.3": {"input_cost_per_token": 1.4e-06, "cache_read_input_token_cost": 2.6e-07, "cache_creation_input_token_cost": 0, "output_cost_per_token": 4.4e-06, "litellm_provider": "zai", "mode": "chat"},
  "zai/glm-5.3-flash": {"input_cost_per_token": 1.5e-07, "cache_read_input_token_cost": 3e-08, "cache_creation_input_token_cost": 0, "output_cost_per_token": 5e-07, "litellm_provider": "zai", "mode": "chat"},
  "tencent/glm-5.3-flashx": {"input_cost_per_token": 3.7e-07, "cache_read_input_token_cost": 7.5e-08, "cache_creation_input_token_cost": 0.0, "output_cost_per_token": 1.25e-06, "litellm_provider": "tencent", "mode": "chat"}
}
```

`scripts/ci/tests/price-drift-fixtures/models-dev.json` (from `api.json`, 2026-10-22):

```json
{
  "anthropic": {"id": "anthropic", "name": "Anthropic", "doc": "https://docs.anthropic.com/en/docs/about-claude/models", "models": {
    "claude-opus-5-5": {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "cost": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 5}, "last_updated": "2026-09-22"},
    "claude-sonnet-5-5": {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "cost": {"input": 2, "output": 10, "cache_read": 0.1, "cache_write": 2.5}, "last_updated": "2026-09-28"},
    "claude-haiku-5-5": {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5", "cost": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125, "tiers": [{"input": 0.5, "output": 2.5, "cache_read": 0.05, "cache_write": 0.625, "tier": {"type": "context", "size": 100000}}]}, "last_updated": "2026-10-07"}
  }},
  "zai": {"id": "zai", "name": "Z.AI", "doc": "https://docs.z.ai/guides/overview/pricing", "models": {
    "glm-5.3": {"id": "glm-5.3", "name": "GLM-5.3", "cost": {"input": 1.4, "output": 4.4, "cache_read": 0.26, "cache_write": 0}, "last_updated": "2026-08-14"},
    "glm-5.3-flashx": {"id": "glm-5.3-flashx", "name": "GLM-5.3-FlashX", "cost": {"input": 0.37, "output": 1.25, "cache_read": 0.075, "cache_write": 0}, "last_updated": "2026-09-18"},
    "glm-5.3-flash": {"id": "glm-5.3-flash", "name": "GLM-5.3-Flash", "cost": {"input": 0.15, "output": 0.5, "cache_read": 0.03, "cache_write": 0}, "last_updated": "2026-08-26"}
  }},
  "zai-coding-plan": {"id": "zai-coding-plan", "name": "Z.AI Coding Plan", "doc": "https://docs.z.ai/devpack/overview", "models": {
    "glm-5.3": {"id": "glm-5.3", "name": "GLM-5.3", "cost": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, "last_updated": "2026-08-14"}
  }}
}
```

`scripts/ci/tests/test-check-price-drift.py`:

```python
#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/check-price-drift.py, the nightly price drift check (truthful costs, TC10).

The fixtures in price-drift-fixtures/ are excerpts of the three catalogs as fetched on
2026-10-22, when all six rows agreed. Each case changes one thing and checks the findings, the
issue body and the issue action. main() runs with the network and gh stubbed: nothing here leaves
the machine.

Run: python3 scripts/ci/tests/test-check-price-drift.py
"""
import importlib.util
import pathlib
import sys
from datetime import date
from decimal import Decimal

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("check_price_drift", ROOT / "scripts/ci/check-price-drift.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

FIX = pathlib.Path(__file__).resolve().parent / "price-drift-fixtures"
FILES = {"genai-prices": "genai-prices.json", "LiteLLM": "litellm.json", "models.dev": "models-dev.json"}
TODAY = date(2026, 10, 22)
ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
# meter.prices on 2026-10-22.
TABLE = {
    "glm-5.3": {"input": 1.40, "cacheRead": 0.26, "output": 4.40},
    "glm-5.3-flashx": {"input": 0.37, "cacheRead": 0.075, "output": 1.25},
    "glm-5.3-flash": {"input": 0.15, "cacheRead": 0.03, "output": 0.50},
    "claude-opus-5-5": {"input": 4.00, "cacheRead": 0.20, "cacheWrite": 5.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cacheRead": 0.10, "cacheWrite": 2.50, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.50, "cacheRead": 0.05, "cacheWrite": 0.625, "output": 2.50},
}
FAILURES = []


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def configmap(table):
    values = yaml.safe_dump({"config": {"meter": {"prices": table}}})
    return yaml.safe_dump({"apiVersion": "v1", "kind": "ConfigMap", "data": {"values.yaml": values}})


def prices(table=TABLE):
    return gen.load_prices(configmap(table))


def catalogs():
    """A fresh copy of each fixture, parsed as the script parses a catalog."""
    return {name: gen.parse_catalog(name, (FIX / f).read_text()) for name, f in FILES.items()}


def genai_model(cats, provider, model):
    p = next(p for p in cats["genai-prices"] if p["id"] == provider)
    return next(m for m in p["models"] if m["id"] == model)


def findings(cats=None, table=TABLE, today=TODAY, **kw):
    return gen.compare(prices(table), cats or catalogs(), today, **kw)


def summary(fs):
    return [(f.model, f.catalog, f.field, f.ours, f.theirs) for f in fs]


# --- The comparison ---
got = findings()
check("today's fixtures agree: no finding (zhipuai and zai-coding-plan are not read)", got == [], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("2e-07")
got = findings(cats)
check("Sonnet 5.5's cache read at 0.20 is one finding",
      got == [gen.Finding("claude-sonnet-5-5", "LiteLLM", "cacheRead", "0.10", "0.20", "claude-sonnet-5-5",
                          ANTHROPIC)], str(got))
SONNET = got

cats = catalogs()
del cats["models.dev"]["anthropic"]["models"]["claude-opus-5-5"]
got = findings(cats)
check("a row a catalog lacks is one finding",
      summary(got) == [("claude-opus-5-5", "models.dev", "—", "—", "not listed")]
      and got[0].key == "anthropic/claude-opus-5-5", str(got))

got = findings(tiers={})
check("Haiku's tier: without it, each catalog's base rate differs on all four fields",
      len(got) == 12 and {f.model for f in got} == {"claude-haiku-5-5"}
      and ("claude-haiku-5-5", "genai-prices", "input", "0.50", "0.10") in summary(got), str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["zai/glm-5.3"]["cache_creation_input_token_cost"] = Decimal("1.68e-06")
got = findings(cats)
check("Z.ai's absent cacheWrite agrees with 0 and absent, not with a price",
      summary(got) == [("glm-5.3", "LiteLLM", "cacheWrite", "absent", "1.68")], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["zai/glm-5.3-flashx"] = dict(cats["LiteLLM"]["tencent/glm-5.3-flashx"], litellm_provider="zai")
got = findings(cats)
check("a declared absence that gets listed is one finding",
      summary(got) == [("glm-5.3-flashx", "LiteLLM", "—", "—", "listed now: drop its ABSENT entry")],
      str(summary(got)))

got = findings(table={**TABLE, "glm-6": {"input": 1.0, "cacheRead": 0.2, "output": 4.0}})
check("a row the mapping lacks is one finding per catalog",
      summary(got) == [("glm-6", c, "—", "—", "not in the mapping")
                       for c in ("LiteLLM", "genai-prices", "models.dev")], str(summary(got)))

cats = catalogs()
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("2e-07")
accepted = {("claude-sonnet-5-5", "LiteLLM", "cacheRead"): ("0.20", "LiteLLM lags; the provider's page says 0.10")}
check("an accepted deviation at its accepted value is no finding", findings(cats, accepted=accepted) == [])
cats["LiteLLM"]["claude-sonnet-5-5"]["cache_read_input_token_cost"] = Decimal("3e-07")
check("an accepted deviation at another value is a finding again",
      summary(findings(cats, accepted=accepted)) == [("claude-sonnet-5-5", "LiteLLM", "cacheRead", "0.10", "0.30")])

cats = catalogs()
cats["models.dev"]["zai"]["models"]["glm-5.3-flashx"]["cost"]["cache_read"] = Decimal("0.07504")
check("equal to 4 decimals: 0.07504 agrees with 0.075", findings(cats) == [])
cats["models.dev"]["zai"]["models"]["glm-5.3-flashx"]["cost"]["cache_read"] = Decimal("0.07505")
check("0.07505 rounds to 0.0751 and differs",
      summary(findings(cats)) == [("glm-5.3-flashx", "models.dev", "cacheRead", "0.075", "0.0751")])

got = findings(today=date(2026, 9, 5))
check("genai-prices' dated prices: before 2026-09-10 the GLM-5.3-Flash promotion is in force",
      summary(got) == [("glm-5.3-flash", "genai-prices", "input", "0.15", "0.075"),
                       ("glm-5.3-flash", "genai-prices", "cacheRead", "0.03", "0.015"),
                       ("glm-5.3-flash", "genai-prices", "output", "0.50", "0.25")], str(summary(got)))

cats = catalogs()
genai_model(cats, "anthropic", "claude-opus-5-5")["prices"]["cache_read_mtok"] = Decimal("0.25")
opus = {**TABLE["claude-opus-5-5"], "source": "https://example.test/opus"}
got = findings(cats, table={**TABLE, "claude-opus-5-5": opus})
check("the row's source wins over the mapping's page",
      [f.source for f in got] == ["https://example.test/opus"], str(got))

for name, what, mutate in [
    ("genai-prices", "a genai-prices that is not a list",
     lambda c: c.__setitem__("genai-prices", {"providers": []})),
    ("LiteLLM", "a LiteLLM price that is a string",
     lambda c: c["LiteLLM"]["zai/glm-5.3"].__setitem__("input_cost_per_token", "1.4e-06")),
    ("genai-prices", "a genai-prices dated price with a malformed start_date",
     lambda c: genai_model(c, "zai", "GLM-5.3-Flash")["prices"][1]["constraint"].__setitem__(
         "start_date", "soon")),
    ("models.dev", "a models.dev that is not an object", lambda c: c.__setitem__("models.dev", [])),
    # genai-prices' frozen v1 file would read so: no 5.5 model, no zai provider.
    ("models.dev", "a catalog listing none of the rows",
     lambda c: c.__setitem__("models.dev", {"opencode": {"models": {}}})),
]:
    cats = catalogs()
    mutate(cats)
    try:
        gen.compare(prices(), cats, TODAY)
        check(f"{what} is refused", False, "no CatalogError")
    except gen.CatalogError as e:
        check(f"{what} is refused", str(e).startswith(name), str(e))

try:
    gen.parse_catalog("LiteLLM", "<html>rate limited</html>")
    check("a catalog that is not JSON is refused", False, "no CatalogError")
except gen.CatalogError as e:
    check("a catalog that is not JSON is refused", str(e).startswith("LiteLLM: not JSON"), str(e))

real = gen.load_prices((ROOT / gen.VALUES).read_text())
check("the real tree's meter.prices loads, every row with an input and an output",
      bool(real) and all(r.get("input", 0) > 0 and r.get("output", 0) > 0 for r in real.values()), str(real))

print("all passed" if not FAILURES else f"{len(FAILURES)} failed: {FAILURES}")
sys.exit(1 if FAILURES else 0)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
export PYTHONDONTWRITEBYTECODE=1
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-check-price-drift.py; echo "exit=$?"
```

Expected: `FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/ci/check-price-drift.py'`,
then `exit=1`.

- [ ] **Step 3: Write the comparison**

`scripts/ci/check-price-drift.py`:

```python
#!/usr/bin/env python3
"""Compares meter.prices with three public price catalogs and keeps one `prices-drift` issue.

Run nightly by .github/workflows/price-drift.yaml (truthful costs design, TC10). A catalog copies the
providers' page mistakes, so a finding only tells a human where to look: this script never edits
the table and never opens a pull request.

  python3 scripts/ci/check-price-drift.py [--dry-run] [ROOT]

Exit 0: the issue now matches the night's findings (opened, updated, closed or left as it was).
Exit 1: the table or a catalog could not be read; the issue is left alone and the failed run
notifies. A failed gh call also exits 1 (gh's error goes to the job log), possibly after the
label was created. --dry-run fetches and compares, prints the body, and calls no gh.
"""
import json
import pathlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

import yaml

VALUES = pathlib.PurePosixPath("tooling/base/agent-factory/helm-values-configmap.yaml")
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
CATALOGS = {
    # v2 is genai-prices' live feed; prices/data.json is a v1 snapshot frozen since 2026-07-25.
    "genai-prices": "https://raw.githubusercontent.com/pydantic/genai-prices/main/prices/new_data/v2/data.json",
    "LiteLLM": "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
    "models.dev": "https://models.dev/api.json",
}
ZAI = "https://docs.z.ai/guides/overview/pricing"
ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"

# Each meter.prices row's key in each catalog, and the provider page a human confirms it on (the
# row's `source` replaces `page` once rows carry one). genai-prices and models.dev keys are
# <provider id>/<model id>; LiteLLM's are its own top-level keys. Z.ai rows name the pay-as-you-go
# providers: genai-prices `zai`, not `zhipuai` (CNY converted), and models.dev `zai`, not
# `zai-coding-plan` (priced 0).
MAPPING = {
    "glm-5.3": {"page": ZAI, "genai-prices": "zai/GLM-5.3", "LiteLLM": "zai/glm-5.3",
                "models.dev": "zai/glm-5.3"},
    "glm-5.3-flashx": {"page": ZAI, "genai-prices": "zai/GLM-5.3-FlashX", "LiteLLM": "zai/glm-5.3-flashx",
                       "models.dev": "zai/glm-5.3-flashx"},
    "glm-5.3-flash": {"page": ZAI, "genai-prices": "zai/GLM-5.3-Flash", "LiteLLM": "zai/glm-5.3-flash",
                      "models.dev": "zai/glm-5.3-flash"},
    "claude-opus-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-opus-5-5",
                        "LiteLLM": "claude-opus-5-5", "models.dev": "anthropic/claude-opus-5-5"},
    "claude-sonnet-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-sonnet-5-5",
                          "LiteLLM": "claude-sonnet-5-5", "models.dev": "anthropic/claude-sonnet-5-5"},
    "claude-haiku-5-5": {"page": ANTHROPIC, "genai-prices": "anthropic/claude-haiku-5-5",
                         "LiteLLM": "claude-haiku-5-5", "models.dev": "anthropic/claude-haiku-5-5"},
}
# Rows a catalog does not list, checked 2026-10-22. No finding while the key stays absent; the
# night it appears, one, so the entry is dropped here and the row compared.
ABSENT = {
    ("glm-5.3-flashx", "LiteLLM"): "LiteLLM lists GLM-5.3-FlashX under tencent/ only",
}
# Rows held at a context tier on purpose, by the tier's threshold in prompt tokens. Haiku 5.5: the
# over-100K rate, which an agent's context soon reaches; over-counting is a cap's safe direction.
TIERS = {"claude-haiku-5-5": 100_000}
# Accepted deviations: (row, catalog, field) -> (the catalog value accepted, why). Any other value
# of that field is a finding again.
ACCEPTED: dict = {}

# Each catalog's name for a field. genai-prices and models.dev are in USD per million tokens,
# LiteLLM in USD per token.
NAMES = {
    "genai-prices": {"input": "input_mtok", "cacheRead": "cache_read_mtok",
                     "cacheWrite": "cache_write_mtok", "output": "output_mtok"},
    "LiteLLM": {"input": "input_cost_per_token", "cacheRead": "cache_read_input_token_cost",
                "cacheWrite": "cache_creation_input_token_cost", "output": "output_cost_per_token"},
    "models.dev": {"input": "input", "cacheRead": "cache_read", "cacheWrite": "cache_write",
                   "output": "output"},
}
Q = Decimal("0.0001")


class CatalogError(ValueError):
    """A catalog whose shape is not the one this script reads."""


class Finding(NamedTuple):
    model: str
    catalog: str
    field: str   # one of FIELDS, or "—" when the whole row is concerned
    ours: str
    theirs: str
    key: str     # the catalog key, "" when the mapping has none
    source: str


def load_prices(text):
    """meter.prices from the factory's values ConfigMap: model -> {field: Decimal}, plus `source`."""
    cm = yaml.safe_load(text) or {}
    values = yaml.safe_load((cm.get("data") or {}).get("values.yaml") or "") or {}
    prices = ((values.get("config") or {}).get("meter") or {}).get("prices")
    if not isinstance(prices, dict) or not prices:
        raise ValueError(f"{VALUES}: no config.meter.prices")
    return {m: {k: (v if k == "source" else Decimal(str(v)))
                for k, v in row.items() if k in FIELDS or k == "source"}
            for m, row in prices.items()}


def parse_catalog(name, text):
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as e:
        raise CatalogError(f"{name}: not JSON ({e})") from None


def _number(name, key, field, v):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise CatalogError(f"{name}: {key} {field} is {v!r}, not a number")
    return Decimal(v)


def _in_force(key, constraint, today):
    """A genai-prices constraint: none, a start_date, or a time of day (off-peak, never the list price)."""
    if not constraint:
        return True
    if "start_date" not in constraint:
        return False
    try:
        return date.fromisoformat(str(constraint["start_date"])) <= today
    except ValueError:
        raise CatalogError(f"genai-prices: {key} has start_date {constraint['start_date']!r}, not a date") from None


def _genai(data, key, tier, today):
    if not isinstance(data, list):
        raise CatalogError("genai-prices: not a list of providers")
    provider, _, model = key.partition("/")
    p = next((p for p in data if isinstance(p, dict) and p.get("id") == provider), None)
    m = next((m for m in (p or {}).get("models") or [] if m.get("id") == model), None)
    if m is None:
        return None
    prices = m.get("prices")
    if isinstance(prices, list):  # dated prices: the last one in force today wins
        live = [c for c in prices if _in_force(key, c.get("constraint"), today)]
        prices = live[-1]["prices"] if live else {}
    if not isinstance(prices, dict):
        raise CatalogError(f"genai-prices: {key} prices is {type(prices).__name__}")
    out = {}
    for f, n in NAMES["genai-prices"].items():
        v = prices.get(n)
        if isinstance(v, dict):  # tiered: {base, tiers: [{start, price}]}
            v = next((t["price"] for t in v.get("tiers") or [] if t.get("start") == tier), v.get("base"))
        out[f] = _number("genai-prices", key, f, v)
    return out


def _litellm(data, key, tier, today):
    if not isinstance(data, dict):
        raise CatalogError("LiteLLM: not an object keyed by model")
    e = data.get(key)
    if e is None:
        return None
    suffix = f"_above_{tier // 1000}k_tokens" if tier else ""
    out = {}
    for f, n in NAMES["LiteLLM"].items():
        v = _number("LiteLLM", key, f, e.get(n + suffix, e.get(n)))
        out[f] = None if v is None else v * 1_000_000
    return out


def _modelsdev(data, key, tier, today):
    if not isinstance(data, dict):
        raise CatalogError("models.dev: not an object keyed by provider")
    provider, _, model = key.partition("/")
    m = ((data.get(provider) or {}).get("models") or {}).get(model)
    if m is None:
        return None
    cost = m.get("cost") or {}
    if tier:
        cost = next((t for t in cost.get("tiers") or [] if t.get("tier") == {"type": "context", "size": tier}),
                    cost)
    return {f: _number("models.dev", key, f, cost.get(n)) for f, n in NAMES["models.dev"].items()}


READERS = {"genai-prices": _genai, "LiteLLM": _litellm, "models.dev": _modelsdev}


def usd(d):
    """A rate as the table writes it: 4 decimals at most, 2 at least."""
    if d is None:
        return "absent"
    whole, _, frac = format(d.quantize(Q, rounding=ROUND_HALF_UP), "f").partition(".")
    return f"{whole}.{frac.rstrip('0').ljust(2, '0')}"


def same(field, ours, theirs):
    if ours is None and field == "cacheWrite":  # not billed: a catalog's absent or 0 agrees
        return theirs is None or theirs == 0
    if ours is None or theirs is None:
        return ours is None and theirs is None
    return ours.quantize(Q, rounding=ROUND_HALF_UP) == theirs.quantize(Q, rounding=ROUND_HALF_UP)


def compare(prices, catalogs, today, mapping=MAPPING, absent=ABSENT, tiers=TIERS, accepted=ACCEPTED):
    """Every disagreement between meter.prices and the catalogs, sorted. Raises CatalogError."""
    out, found = [], set()
    for model in sorted(prices):
        row, entry = prices[model], mapping.get(model) or {}
        source = row.get("source") or entry.get("page") or ""
        for name in sorted(catalogs):
            key = entry.get(name)
            if not key:
                out.append(Finding(model, name, "—", "—", "not in the mapping", "", source))
                continue
            theirs = READERS[name](catalogs[name], key, tiers.get(model), today)
            if theirs is not None:
                found.add(name)
            if (model, name) in absent:
                if theirs is not None:
                    out.append(Finding(model, name, "—", "—", "listed now: drop its ABSENT entry", key, source))
                continue
            if theirs is None:
                out.append(Finding(model, name, "—", "—", "not listed", key, source))
                continue
            for f in FIELDS:
                ours, their = row.get(f), theirs[f]
                if same(f, ours, their):
                    continue
                ok = accepted.get((model, name, f))
                if ok and their is not None and same(f, Decimal(ok[0]), their):
                    continue
                out.append(Finding(model, name, f, usd(ours), usd(their), key, source))
    blind = sorted(set(catalogs) - found)
    if blind:  # a moved or reshaped feed, not every row gone
        raise CatalogError(f"{blind[0]}: lists none of meter.prices' rows")
    return out
```

Two details matter here:
- The catalog names sort as `LiteLLM`, `genai-prices`, `models.dev`, because uppercase sorts first.
  The findings, and so the issue body, come in that order.
- LiteLLM reads `<field>_above_100k_tokens` for a 100 000-token tier and falls back to the base field.
  genai-prices and models.dev read the tier whose threshold equals the row's and fall back to the flat
  rate. If a catalog drops Haiku's tier, Haiku then differs on every field, which a human should see.

- [ ] **Step 4: Run the tests**

```bash
chmod +x scripts/ci/check-price-drift.py scripts/ci/tests/test-check-price-drift.py
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-check-price-drift.py; echo "exit=$?"
```

Expected: 19 `ok` lines, from `today's fixtures agree` to `the real tree's meter.prices loads`, then
`all passed` and `exit=0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/check-price-drift.py scripts/ci/tests/test-check-price-drift.py \
  scripts/ci/tests/price-drift-fixtures/genai-prices.json scripts/ci/tests/price-drift-fixtures/litellm.json \
  scripts/ci/tests/price-drift-fixtures/models-dev.json
git commit -m "feat(ci): check-price-drift compares meter.prices with three public catalogs"
```

---

### Task 2: The issue, the fetch and the command line

**Files:**
- Modify: `scripts/ci/check-price-drift.py`: the import block, three constants after `FIELDS`, and
  the functions after `compare`
- Modify: `scripts/ci/tests/test-check-price-drift.py`: the import block, and the issue and `main()`
  cases before the final `print`

**Interfaces:**
- Consumes: Task 1's `compare`, `Finding`, `load_prices`, `parse_catalog`, `CATALOGS`, `VALUES`,
  `CatalogError`.
- Produces (Task 3 relies on these):
  - The command line `python3 scripts/ci/check-price-drift.py [--dry-run] [ROOT]`. `ROOT` defaults
    to the repository the script is in. Exit 0 means the issue matches the findings; exit 1 means
    the table or a catalog could not be read (no `gh` call was made), or a `gh` call failed (its
    error is in the job log). It needs `GH_TOKEN` and
    reads `GH_REPO`.
  - `LABEL = "prices-drift"`, `TITLE`, `CLOSING`.
  - `issue_body(findings) -> str`.
  - `issue_action(findings, issue: dict | None) -> tuple[str, str | None]`, where `issue` is
    `{"number": int, "body": str}`. The action is one of `"open"`, `"update"`, `"close"` or
    `"nothing"`.
  - `fetch(url) -> str`, `gh(*args, stdin=None) -> str`, `open_issue() -> dict | None`,
    `apply(action, body, issue)` and `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing tests**

In `scripts/ci/tests/test-check-price-drift.py`, replace:

```python
import importlib.util
import pathlib
import sys
from datetime import date
from decimal import Decimal
```

with:

```python
import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
from datetime import date
from decimal import Decimal
```

Then, immediately before the final `print("all passed" if not FAILURES else …)` line, insert:

```python
# --- The issue ---
body = gen.issue_body(SONNET)
row = (f"| `claude-sonnet-5-5` | cacheRead | 0.10 | 0.20 | [LiteLLM]({gen.CATALOGS['LiteLLM']}) "
       f"`claude-sonnet-5-5` | {ANTHROPIC} |")
check("the body names model, field, ours, theirs, catalog and source", row in body.splitlines(), body)
check("the body says closing the issue by hand silences nothing; ACCEPTED or ABSENT does",
      "Closing it by hand silences nothing" in body and "`ACCEPTED`" in body and "`ABSENT`" in body, body)
check("the same findings twice give the same body", gen.issue_body(list(SONNET)) == body)
check("clean, no issue: nothing", gen.issue_action([], None) == ("nothing", None))
check("clean, an open issue: close", gen.issue_action([], {"number": 7, "body": body}) == ("close", None))
check("findings, no issue: open", gen.issue_action(SONNET, None) == ("open", body))
check("findings, the same body: nothing",
      gen.issue_action(SONNET, {"number": 7, "body": body.replace("\n", "\r\n")}) == ("nothing", None))
check("findings, another body: update", gen.issue_action(SONNET, {"number": 7, "body": "old"}) == ("update", body))


# --- gh's own error reaches the job log ---
# A fake gh on PATH fails the way gh does. The real gh() must neither swallow its stderr nor hide the exit.
real_gh = gen.gh
with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryFile() as err:
    fake = pathlib.Path(tmp) / "gh"
    fake.write_text("#!/bin/sh\necho 'HTTP 403: Resource not accessible by integration' >&2\necho out\nexit 1\n")
    fake.chmod(0o755)
    old_path, saved = os.environ["PATH"], os.dup(2)
    os.environ["PATH"] = f"{tmp}:{old_path}"
    os.dup2(err.fileno(), 2)
    try:
        real_gh("issue", "create")
        failed = False
    except subprocess.CalledProcessError:
        failed = True
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.environ["PATH"] = old_path
    err.seek(0)
    shown = err.read().decode()
check("a failing gh call still raises", failed)
check("a failing gh call's stderr reaches the job log", "HTTP 403: Resource not accessible" in shown, shown)


# --- main(), with the network and gh stubbed ---
def run_main(table, fetched, open_issues):
    calls = []

    def fetch(url):
        name = next(n for n, u in gen.CATALOGS.items() if u == url)
        v = fetched[name]
        if isinstance(v, Exception):
            raise v
        return v

    def gh(*args, stdin=None):
        calls.append((args, stdin))
        return open_issues if args[:2] == ("issue", "list") else ""

    with tempfile.TemporaryDirectory() as tmp:
        values = pathlib.Path(tmp) / gen.VALUES
        values.parent.mkdir(parents=True)
        values.write_text(configmap(table))
        gen.fetch, gen.gh = fetch, gh
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = gen.main([tmp])
    return code, calls, out.getvalue()


texts = {name: (FIX / f).read_text() for name, f in FILES.items()}
code, calls, out = run_main(TABLE, {**texts, "models.dev": urllib.error.URLError("timed out")}, "[]")
check("an unreachable catalog fails the run, names it and its URL, and calls no gh",
      code == 1 and calls == [] and "left alone" in out
      and f"models.dev ({gen.CATALOGS['models.dev']}): " in out, out)
code, calls, out = run_main(TABLE, {**texts, "genai-prices": urllib.error.HTTPError(
    gen.CATALOGS["genai-prices"], 429, "Too Many Requests", {}, None)}, "[]")
check("a rate-limited catalog is named too", code == 1 and calls == [] and "genai-prices (" in out
      and "429" in out, out)
code, calls, out = run_main(TABLE, {**texts, "LiteLLM": "<html>"}, "[]")
check("an unparseable catalog fails the run and calls no gh", code == 1 and calls == [], out)

drift = {**TABLE, "claude-sonnet-5-5": {**TABLE["claude-sonnet-5-5"], "cacheRead": 0.20}}
code, calls, out = run_main(drift, texts, "[]")
verbs = [a[:2] for a, _ in calls]
check("drift with no open issue: list, label, create",
      code == 0 and verbs == [("issue", "list"), ("label", "create"), ("issue", "create")]
      and "--label" in calls[2][0] and gen.LABEL in calls[2][0] and "| cacheRead | 0.20 | 0.10 |" in calls[2][1],
      f"{code} {calls}")
code, calls, out = run_main(TABLE, texts, '[{"number": 9, "body": "x"}, {"number": 7, "body": "y"}]')
check("clean with an open issue: the oldest is closed",
      code == 0 and [a for a, _ in calls][1:] == [("issue", "close", "7", "--comment", gen.CLOSING)], f"{code} {calls}")

```

- [ ] **Step 2: Run them and watch them fail**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-check-price-drift.py; echo "exit=$?"
```

Expected: Task 1's 19 `ok` lines, then
`AttributeError: module 'check_price_drift' has no attribute 'issue_body'`, then `exit=1`.

- [ ] **Step 3: Write the issue handling and the command line**

In `scripts/ci/check-price-drift.py`, replace:

```python
import json
import pathlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple
```

with:

```python
import argparse
import http.client
import json
import pathlib
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple
```

Replace:

```python
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
```

with:

```python
FIELDS = ("input", "cacheRead", "cacheWrite", "output")
LABEL = "prices-drift"
TITLE = "Price drift: a public catalog disagrees with meter.prices"
CLOSING = "The nightly price drift check found no disagreement: every row matches its catalogs."
```

At the end of the file, after `compare`'s `return out`, append:

```python


def issue_body(findings):
    lines = [
        "The nightly price drift check (`.github/workflows/price-drift.yaml`) found public catalogs that "
        "disagree with `meter.prices` in `tooling/base/agent-factory/helm-values-configmap.yaml`.",
        "",
        "Catalogs copy the providers' page mistakes: confirm each finding on the provider's page "
        "(Source) before changing anything. Then correct the row, or record the deviation in "
        "`scripts/ci/check-price-drift.py` (`MAPPING`, `ABSENT`, `TIERS` or `ACCEPTED`). This check "
        "never edits the table; the first clean run closes this issue. Closing it by hand silences "
        "nothing: a finding stops only when it is recorded in `ACCEPTED` (a deliberate deviation) or "
        "`ABSENT` (a row a catalog lacks).",
        "",
        "| Model | Field | Ours | Theirs | Catalog | Source |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        cat = f"[{f.catalog}]({CATALOGS[f.catalog]})" + (f" `{f.key}`" if f.key else "")
        lines.append(f"| `{f.model}` | {f.field} | {f.ours} | {f.theirs} | {cat} | {f.source or '—'} |")
    lines += ["", "USD per million tokens; equal when both round to the same 4 decimals."]
    return "\n".join(lines) + "\n"


def issue_action(findings, issue):
    """(action, body): open, update, close or nothing, given the open issue ({number, body}) or None."""
    if not findings:
        return ("close", None) if issue else ("nothing", None)
    body = issue_body(findings)
    if issue is None:
        return "open", body
    if issue.get("body", "").replace("\r\n", "\n").strip() == body.strip():
        return "nothing", None
    return "update", body


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-native-ref price drift check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def read(name, url):
    """One catalog, fetched and parsed; any failure names the catalog and its URL."""
    try:
        return parse_catalog(name, fetch(url))
    except (OSError, http.client.HTTPException, UnicodeDecodeError) as e:
        raise CatalogError(f"{name} ({url}): {e}") from None


def gh(*args, stdin=None):
    return subprocess.run(["gh", *args], input=stdin, check=True, stdout=subprocess.PIPE, encoding="utf-8").stdout


def open_issue():
    issues = json.loads(gh("issue", "list", "--state", "open", "--label", LABEL,
                           "--json", "number,body", "--limit", "100"))
    return min(issues, key=lambda i: i["number"]) if issues else None


def apply(action, body, issue):
    if action == "open":
        gh("label", "create", LABEL, "--color", "fbca04", "--force",
           "--description", "A public price catalog disagrees with meter.prices")
        gh("issue", "create", "--title", TITLE, "--label", LABEL, "--body-file", "-", stdin=body)
    elif action == "update":
        gh("issue", "edit", str(issue["number"]), "--body-file", "-", stdin=body)
    elif action == "close":
        gh("issue", "close", str(issue["number"]), "--comment", CLOSING)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="print the body; call no gh")
    p.add_argument("root", nargs="?", default=str(pathlib.Path(__file__).resolve().parents[2]))
    a = p.parse_args(argv)
    try:
        prices = load_prices((pathlib.Path(a.root) / VALUES).read_text())
        catalogs = {name: read(name, url) for name, url in CATALOGS.items()}
        findings = compare(prices, catalogs, datetime.now(timezone.utc).date())
    except (OSError, ValueError, http.client.HTTPException) as e:
        print(f"FAIL {e}: the {LABEL} issue is left alone", file=sys.stderr)
        return 1
    for f in findings:
        print(f"finding: {f.model} {f.field} ours {f.ours}, {f.catalog} {f.key or '-'} {f.theirs}")
    issue = None if a.dry_run else open_issue()
    action, body = issue_action(findings, issue)
    print(f"check-price-drift: {len(prices)} rows, {len(catalogs)} catalogs, {len(findings)} finding(s);"
          f" issue: {action}" + (f" #{issue['number']}" if issue else ""))
    if a.dry_run:
        print(body or "", end="")
    else:
        apply(action, body, issue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The `except` catches every way a fetch, a parse or the table can fail. `urllib.error.URLError`,
`HTTPError` and timeouts are `OSError`s. `CatalogError`, `JSONDecodeError` and a bad date are
`ValueError`s. A truncated read is an `http.client.HTTPException`. Nothing above that line calls `gh`.

- [ ] **Step 4: Run the tests**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/tests/test-check-price-drift.py; echo "exit=$?"
```

Expected: 32 `ok` lines, the last `clean with an open issue: the oldest is closed`, then `all passed`
and `exit=0`.

- [ ] **Step 5: Run it against the real catalogs, with no issue touched**

```bash
bash $SCRATCH/run-suite.sh python3 scripts/ci/check-price-drift.py --dry-run; echo "exit=$?"
```

Expected on 2026-10-22: `check-price-drift: 6 rows, 3 catalogs, 0 finding(s); issue: nothing`, then
`exit=0`. A later day may print `finding:` lines and a body instead. That is real drift, not a bug:
quote it in the pull request. Do not change `meter.prices`, which is the owner's call (TC10), and do
not change the fixtures. `exit=1` with `FAIL …` means a catalog moved or changed shape: fix the URL
or the reader before going on.

- [ ] **Step 6: Commit**

```bash
git add scripts/ci/check-price-drift.py scripts/ci/tests/test-check-price-drift.py
git commit -m "feat(ci): check-price-drift keeps one prices-drift issue in step with its findings"
```

---

### Task 3: The workflow, and where the check is documented

**Files:**
- Create: `.github/workflows/price-drift.yaml`
- Modify: `tooling/base/agent-factory/helm-values-configmap.yaml`: the comment above `prices:`
- Modify: `website/content/docs/platform/ai-platform/routing.md`: the paragraph after the
  `meter.prices` table
- Modify: `docs/superpowers/specs/2026-10-22-truthful-costs-design.md`: the end of "Left to the
  builder"

**Interfaces:**
- Consumes: Task 2's command line, its exit codes, and its use of `GH_TOKEN` and `GH_REPO`.
- Produces: the workflow `price-drift`, which Task 4's pull request body and live proof 6 name.

- [ ] **Step 1: Write the workflow**

`.github/workflows/price-drift.yaml`:

```yaml
name: price-drift

# Truthful costs design, TC10: compares meter.prices with genai-prices, LiteLLM and models.dev
# and keeps one issue labelled prices-drift. It never edits the table: a human confirms each
# finding on the provider's page. A catalog that cannot be fetched or parsed fails the run, which
# notifies, and leaves the issue alone.
on:
  schedule:
    # 04:17 UTC: off the hour, when GitHub delays or drops scheduled runs under load.
    - cron: "17 4 * * *"
  workflow_dispatch:

permissions: {}

# A dispatched run and the scheduled one must not both open the issue.
concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false

jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - run: python3 -m pip install --quiet --disable-pip-version-check pyyaml
      - name: Compare meter.prices with the catalogs
        env:
          GH_TOKEN: ${{ github.token }}
          # Every gh call names this repository, whatever the checkout's remote says.
          GH_REPO: ${{ github.repository }}
        run: python3 scripts/ci/check-price-drift.py
```

```bash
actionlint .github/workflows/price-drift.yaml; echo "exit=$?"
```

Expected: no output, `exit=0`. If `actionlint` is not installed, say so in the pull request; the
`lint` job's `check-yaml` and the first dispatched run still check the file.

- [ ] **Step 2: Point whoever adds a row to the mapping**

In `tooling/base/agent-factory/helm-values-configmap.yaml`, replace:

```yaml
        # cache writes). Haiku 5.5 is at its over-100K-prompt rate, which an agent's context
        # soon reaches: over-counting is the safe direction for a cap.
        prices:
```

with:

```yaml
        # cache writes). Haiku 5.5 is at its over-100K-prompt rate, which an agent's context
        # soon reaches: over-counting is the safe direction for a cap. A nightly workflow compares
        # every row with three public catalogs: a new row needs its entry in the MAPPING of
        # scripts/ci/check-price-drift.py, or the check reports it.
        prices:
```

Only a comment changes. The rendered chart values, and so the factory's config, stay the same.

- [ ] **Step 3: The site and the spec**

In `website/content/docs/platform/ai-platform/routing.md`, replace:

```markdown
Haiku is at its over-100K-prompt rate, which an agent's context soon reaches. Over-counting is the
safe direction for a cap.
```

with:

```markdown
Haiku is at its over-100K-prompt rate, which an agent's context soon reaches. Over-counting is the
safe direction for a cap.

A nightly workflow, `.github/workflows/price-drift.yaml`, compares every row with genai-prices,
LiteLLM and models.dev. A disagreement, or a row a catalog stops listing, opens or updates one issue
labelled `prices-drift`, and the first clean run closes it. The check never edits the table: catalogs
copy the providers' page mistakes, so a person confirms each finding on the provider's page first.
```

If PR 1 has merged and moved that paragraph, put the new one directly after the `meter.prices`
table, wherever the table now is.

In `docs/superpowers/specs/2026-10-22-truthful-costs-design.md`, after the paragraph that ends
`whether the values-parse check of offline proof 12 becomes a suite.`, append:

```markdown

Ruled in PR 4 ([plan](../plans/2026-10-22-price-drift-check-plan.md#this-plans-rulings)):

- **The catalogs:** genai-prices' live feed is `prices/new_data/v2/data.json`. Its `prices/data.json`
  is a v1 snapshot, frozen since 2026-07-25, that lists no 5.5 model and no `zai` provider.
- **The mapping:** four tables in `scripts/ci/check-price-drift.py`. `MAPPING` holds each row's key
  in each catalog. `ABSENT` holds the rows a catalog lacks (LiteLLM has no `zai/glm-5.3-flashx`).
  `TIERS` holds the tier a row is priced at (Haiku 5.5's over-100K rate). `ACCEPTED` holds accepted
  deviations (none yet).
- **The issue:** its body depends only on the findings, so a night with the same findings leaves the
  issue alone. A catalog that lists none of the rows fails the run, as one that cannot be parsed does.
- **The cron:** 04:17 UTC.
```

```bash
bash $SCRATCH/run-suite.sh ./scripts/ci/validate-links.sh
bash $SCRATCH/run-suite.sh ./scripts/ci/verify-doc-paths.sh
```

Expected: no broken link, since `../plans/…` resolves to this plan. Then
`==> Every repository path named in the docs site exists.` That check also requires
`.github/workflows/price-drift.yaml` to exist, because `.github/` is one of its known top-level
directories. It needs `.host/`, which the first `task check` cloned.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/price-drift.yaml tooling/base/agent-factory/helm-values-configmap.yaml \
  website/content/docs/platform/ai-platform/routing.md docs/superpowers/specs/2026-10-22-truthful-costs-design.md
git commit -m "feat(ci): run the price drift check nightly, and say where it lives"
```

---

### Task 4: Verify, push, open the pull request

- [ ] **Step 1: The whole check, and the lint job's hooks**

```bash
bash $SCRATCH/check.sh "$PWD"
grep -E "check-price-drift|passed,|exit=" "$SCRATCH/check-$(basename "$PWD").log"
pre-commit run --files scripts/ci/check-price-drift.py scripts/ci/tests/test-check-price-drift.py \
  scripts/ci/tests/price-drift-fixtures/*.json .github/workflows/price-drift.yaml \
  tooling/base/agent-factory/helm-values-configmap.yaml website/content/docs/platform/ai-platform/routing.md \
  docs/superpowers/specs/2026-10-22-truthful-costs-design.md
```

Expected:
- `PASS  test-check-price-drift`.
- `22 passed, 1 skipped, 0 failed`. The baseline on this branch on 2026-10-22 was `21 passed,
  1 skipped`, the skip being `test-agent-traces-filter` with no Docker daemon, and this plan adds one
  suite. If other suites have merged since, the counts are higher. What matters is the PASS above
  and `0 failed`.
- `exit=0`.
- Every pre-commit hook `Passed` or `Skipped`. `check-json` covers the fixtures, `check-yaml` the
  workflow, `detect-secrets` everything.

- [ ] **Step 2: Rebase and push**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/price-drift-check
```

If the rebase changes anything (for example, if PR 1 rewrote `routing.md`), run Step 1 again before
pushing.

- [ ] **Step 3: Open the pull request**

Title: `feat(ci): truthful costs PR 4, a nightly price drift check`.

The body is in English and covers:
- **The outcome:** the workflow, what it compares, and the one `prices-drift` issue. It never edits
  the table and never opens a pull request (TC10).
- **Today's comparison:** 0 findings across 6 rows and 3 catalogs. LiteLLM lacks
  `zai/glm-5.3-flashx`, which is declared in `ABSENT`. Haiku agrees at the 100K tier. Quote Task 2
  Step 5's line, with any findings it printed.
- **The rulings:** R1 to R13. Name R1 (the v2 feed) and R6 (a catalog listing no row fails the run).
- **The suite:** `test-check-price-drift`, 35 checks, offline proof 14 case by case.
- **The `task check` summary.**
- **What waits for merge:** live proof 6. Once merged, the owner dispatches the workflow once and
  reads the first two scheduled runs.
- **A test plan:** the commands in "After merge" below.

No attribution line.

### After merge (live proof 6)

```bash
gh workflow run price-drift.yaml --repo Smana/ai-native-ref
gh run list --workflow price-drift.yaml --repo Smana/ai-native-ref --limit 1
gh issue list --repo Smana/ai-native-ref --label prices-drift --state all
```

With 2026-10-22's catalogs, the dispatched run succeeds, prints `0 finding(s); issue: nothing`, and
no issue exists. After the first two scheduled runs there is at most one `prices-drift` issue, and
the owner confirms each of its findings on the provider's page (the spec's live proof 6).
