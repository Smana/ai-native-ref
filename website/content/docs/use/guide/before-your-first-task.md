---
title: "2. Before your first task"
linkTitle: "2. Before your first task"
weight: 2
description: "The five things you need before you hand the factory a task, and who gives you each one."
---

By the end of this chapter you will have what you need, and know whom to ask for each piece.

It is a one-time set-up. To hand over a task you need only the first item; the other four let you
watch it in its room. If you do not know your platform team, ask whoever told you about the factory.

## The five things {#five-things}

**1. Maintainer rights on the repository.** Labels and reviews are how you talk to the factory. A
*maintainer* is someone the repository lets approve and merge, usually GitHub's Maintain or Admin
role. The repository's owner grants it. The repository must also be one your platform team has
connected to the factory. Example (the reference host, the set-up these docs were written on):
`Smana/cloud-native-ref`.

**2. Access to the private network.** The room pages are not on the public internet. Your
platform team adds you to the private network that reaches them, and gives you the room list's
address.

**3. Your computer trusting the platform's certificate.** The private pages use the platform's own
certificate authority. Your platform team gives you its certificate; you add it to your system once.

**4. A place in the `agents-member` group.** You sign in to the room pages with the platform's single
sign-on. Sign in once, so your account exists, then ask an admin (someone in `agents-admin`) to add
you to `agents-member`.

**5. Your GitHub account linked to your sign-in.** You see a room only if GitHub lets you read its
repository, so the platform must know who you are on GitHub. Link the accounts yourself, once, on the
sign-in page.

## Check it works {#check}

Open the room list. You should see your repositories' rooms, or an empty list with no error. A "403"
means step 4 is missing; an empty list with a GitHub hint means step 5 is. Your admin's side of all
this is [Operate › Access]({{< relref "/docs/operate/access.md" >}}).

**Next:** [chapter 3]({{< relref "your-first-task.md" >}}) takes your first task from issue to merge.
