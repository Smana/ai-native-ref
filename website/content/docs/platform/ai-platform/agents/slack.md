---
title: Slack
weight: 34
description: "Hand work to the factory from a Slack thread: mention, draft, edit by reply, a maintainer's check mark files the issue and starts the task."
lastVerified: 2026-10-29
---

`maku-slack`, Maku's Slack app, turns a Slack thread into a factory task. **Live, proven on 2026-10-29**:
a mention drafts the issue, a reply edits it, a maintainer's ✅ files it and starts the task, and the
thread then follows the room. Approvals and steering stay on the room page.

| Step | Do this |
|---|---|
| Once | Mention `@factory link` in a served channel and confirm the one-time page it answers you with. `@factory unlink` undoes it |
| Draft | `@factory <owner/repo> <title>`, then optional lines: `Should:` and `Acceptance:` |
| Edit | Reply in the draft's thread: `Title:`, `Should:`, `Acceptance:` or free text. Each reply posts a newer draft |
| File | A maintainer reacts ✅ on the latest draft. The issue is filed, the task starts, and the thread shows its triage, runs, pull request and end |
| Act | Approve, answer or steer on the room page linked in the thread; merge on GitHub |

The full guide, with every refusal and its fix, is in the
[user guide]({{< relref "/docs/platform/ai-platform/agents/user-guide.md#from-slack" >}}). The task is
sponsored by your linked GitHub login, filed by the factory's App, and capped by the channel's
`maxCostUSD`.

Setting it up (the Slack App, its keys, the machine user, the channels it serves) is the operator's:
[runbook 22](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/22-slack.md),
and [runbook 18](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/18-factory-interfaces.md)
for the sponsored principal and the webhooks it rides on.
