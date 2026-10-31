---
title: Access
weight: 5
description: "Give a person access to the Agent Factory: the platform's CA, the SSO groups, the GitHub link, who sees a room, and what a 403 means."
---

What an admin sets up so a person can follow and steer factory tasks. The user's side is
[chapter 2 of the user guide]({{< relref "/docs/use/guide/before-your-first-task.md" >}}).

| The person needs | Who grants it | Section |
|---|---|---|
| Maintainer rights on the repository | The repository's owner | — |
| Access to the tailnet | The platform team | — |
| Their OS trusting the platform's root CA | The platform team hands out the CA | [Root CA](#root-ca) |
| `agents-member` (or `agents-admin`) | An admin, in ZITADEL | [Groups](#groups) |
| Their GitHub account linked to their ZITADEL user | The person, or an admin | [GitHub link](#github-link) |

## Root CA {#root-ca}

The room page, the broker and `maku` talk to private endpoints signed by the platform's root CA.
Without it, `maku` fails with `x509: certificate signed by unknown authority`. Fetch and trust it as in
[runbook 11's prerequisites](https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/11-v1-validation.md#prerequisites).

## Groups {#groups}

| Group | Grants |
|---|---|
| `agents-member` | Watch rooms and runs, post notes, start a run by hand |
| `agents-admin` | Every room, approvals, `internal` work and `triager` runs |

A user exists only after their first login. Once they have logged in, grant the role:

```bash
scripts/provision/zitadel-oidc-clients.sh --grant agents-member=<their email>   # or agents-admin=
```

## The GitHub link {#github-link}

The person signs in at the platform's identity provider, chooses **GitHub**, and links it to their
existing user. Example (the reference host): `https://auth.gcp.cloud.ogenki.io`.

Someone who signs in with Google only ends on a password reset there. An admin adds the link instead:

```bash
IDP_URL=https://auth.<your-domain> scripts/provision/zitadel-idp.sh link-github \
  <zitadel-login> <github-login> --cluster <cluster> --cloud <cloud> --apply
```

Until the link exists, `maku rooms` lists nothing and says how to link. The hint goes away within
5 minutes of the link.

## Who sees a room {#who-sees-a-room}

A person sees a room only if GitHub lets them read its repository; `agents-admin` sees every room.

The broker reads the GitHub account linked to the person's ZITADEL user and asks GitHub for its
permission on the room's repository. It keeps the answer for 5 minutes, so a grant or a revocation takes
effect within that. A room they cannot read answers 404, as if it did not exist. When GitHub cannot be
asked, the broker refuses once its cached answer expires.

## A 403 after a valid login {#403}

oauth2-proxy and the broker admit a token only when its `groups` claim names `agents-member` or
`agents-admin`. Two things put the claim there:

1. **The `groupsFromRoles` ZITADEL Action**, which turns project roles into the claim. A broken or edited
   Action drops it from every token, so everyone gets a 403 at once.
2. **A grant of one of those roles** to the user ([Groups](#groups)). A fresh ZITADEL holds no grants.

Check the Action first (it fails for everyone), then the grant (it fails for one person).
