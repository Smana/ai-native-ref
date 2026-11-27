# 33 — Maku v0.56.0: browser verification and screenshots, live

What the Maku v0.56.0 adoption turned on: the `ai-native-ref` Repository's implementer and tester runs
get a loopback-only browser, every screenshot shows in the room, the verdict links to it, and images
attached to an issue reach a run whose model sees images. Run it on the cluster the fences name. Keep
each step's run ID, task name and cost in a results file beside this runbook
(`results-<cluster>-<date>.md`).

Sources: the Maku [harness screenshots plan](https://github.com/Smana/maku/blob/main/docs/superpowers/plans/2026-11-26-harness-screenshots-plan.md)
(its "Live acceptance drill") and the [design](../../superpowers/specs/2026-11-23-v5-harness-screenshots-design.md) (§11, as built).

## 0. Each vision alias answers an image (the owner)

The owner runs the plan's drill D0: one call per alias in `runController.model.gateway.vision`, with a
64×64 red PNG, through the model gateway. It needs a gateway token, so only the owner runs it. Every
listed alias answers "red"; public `agent-default` (`glm-5.3`, text-only) is the negative control.
An alias that answers wrong leaves the vision list in a follow-up pull request.

## 1. A visual bug, fixed and checked

| Step | Do | Expected |
|---|---|---|
| Plant | On a branch, set the website's hero button text colour equal to its background in dark mode; open an issue "The hero button is invisible in dark mode on the website; fix it and verify visually", labels `factory/ready` and `model:mistral-standard` | Triage freezes `status.profile.screenshots`; `kubectl -n agents get pod -l agents.ogenki.io/role=implementer -o jsonpath='{.spec.initContainers[*].name}'` lists `browser`; the reviewer's pod has no `browser` |
| Watch | The room | The agent starts `hugo server --bind 127.0.0.1`, reads `browser_snapshot`, switches dark mode with `browser_emulate_media`, takes a screenshot, names the defect, fixes the CSS and takes another; the gate's log shows `screenshot n=` at most 10 |
| OpenCode | The same with `harness:opencode` | The same |
| Internal | The same on `dataClass: internal` (`agent-default`, Claude Opus 5.5) | The same: Anthropic's translation carries the image |
| Text-only | The same with `model:agent-default` (public) | The screenshots still show in the room, each card says the model could not see it; the model reads snapshots only |

## 2. What humans see

| Step | Do | Expected |
|---|---|---|
| Gallery | Open the step-1 room as a reader | The run shows a gallery of its screenshots; each card names the page and size; one opens full size |
| Not a reader | Open the room and one image URL as a GitHub user without read access | 404 for both |
| Link | Read the pull request's verdict comment | One line links to `/r/<room>#screenshots`, which opens on the gallery; no image on GitHub |
| Git | `git status` on the branch and the pull request's diff | No image file anywhere; the pull request changes the CSS only |

## 3. The boundaries

| Step | Do | Expected |
|---|---|---|
| URLs | Steer the step-1 run to open `https://example.com` and `http://169.254.169.254/` | Both refused `url_refused`; a local page's external image shows a failed request |
| Out of memory | During step 1, kill the browser's Chromium (`kubectl exec … -c browser -- sh -c 'kill -9 $(pgrep -f chrome-headless | head -1)'`) | The `browser` container restarts; the run ends normally |
| Cost | Compare step 1's prompt-cache read share and cost with the same issue run without screenshots | Within 5 points; every vision turn is priced |

## 4. An image in the request

File an issue with a pasted screenshot of a bug, `model:mistral-standard`. The brief lists `image 1`,
the agent calls `room_image`, and the run describes what the image shows. Edit the issue's text after
labelling it on a second issue: its images are not attached.
