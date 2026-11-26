---
title: Developer quickstart
weight: 5
diataxis: how-to
description: "From a small fix to a merged pull request in eight words: what a developer needs to know, and nothing else."
---

You have a repository, a small fix in mind, and no time to learn a platform. This page is all you
need for a first task. It uses eight words, defined where they first appear.

## 1. Get access {#access}

Ask your platform team for access to Maku, and for the address of its room list. Open it once and
sign in. If your repository is not in the **New task** picker, ask them to connect it.

## 2. Make your repository ready {#ready}

Add three small files so the agents can build and test their work before they push:
[Make your repository ready]({{< relref "/docs/use/make-your-repository-ready.md" >}}).

## 3. Hand off a task {#hand-off}

A **task** is one piece of work: a fix, written as an issue. Open the room list, press **New task**,
and write what is wrong and what it should be. Name the file when you know it.

Maku drafts the issue for you. It has an **acceptance check**: the one test that says the fix is done.
Read it, change it if it is wrong, then file the task.

A **maintainer** is someone your repository lets approve and merge. If you are not one, ask one to
start the task.

## 4. Follow it {#follow}

Each task gets a **room**: a page with every step the agents take. The link is on the issue.

The task runs a **workflow**, the steps it goes through, such as an implementer then a reviewer. It
also has a **budget**, the most it may spend in dollars. The room shows both.

You do not have to watch. Maku comments on the issue when something needs you.

## 5. Read the pull request {#review}

An agent opens a pull request. Then a **reviewer**, a second agent on another model, reads it and
gives a verdict before you do.

Read the change. To ask for changes, submit your review as **Request changes**: the agent revises
on the same branch. To check the branch out locally, run `maku checkout <room>`.

## 6. Merge {#merge}

Approve the pull request, and Maku merges it. A **merge policy** decides which kinds of change may
merge without your approval. Until your team turns one on, every change waits for you.

**Next:** the [user guide]({{< relref "/docs/use/guide/_index.md" >}}) covers Slack, your coding agent
and what to do when a task needs you.
