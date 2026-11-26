# 30 — Gemini on Vertex AI from aws-0: the live proof

The model gateway on aws-0 calls Gemini on Vertex AI as its EKS Pod Identity role, which a GCP
Workload Identity Federation pool trusts. No Google key exists. This runbook proves it on the next
aws-0 session, in order; stop at the first step that fails and record it. Keep the results in
`results-aws-0-<date>.md` beside this runbook.

Sources: cloud-native-ref's design (`docs/superpowers/specs/2026-11-26-aws-vertex-federation-design.md`)
and its ADR-0063; the overlay in `infrastructure/aws-0/agent-gateway/model-gateway/`.

## 0. Before the session

| Check | Command | Expected |
|---|---|---|
| The predict role exists (gke/init creates it; its destroy keeps it) | `gcloud iam roles describe xplane_vertex_predict_v3 --project ogenki-435905 --format='value(includedPermissions)'` | `aiplatform.endpoints.predict` |
| The Vertex API is on | `gcloud services list --enabled --project ogenki-435905 \| grep aiplatform` | `aiplatform.googleapis.com` |
| The pins | Maku chart `maku-gateway` at a release carrying `gcpCredentials` and `proxy`; `HOST_REF` at a cloud-native-ref commit with `vertex.tf` | both merged and released |

## 1. The host side

Run with Google credentials (the shared stack now needs them: `vertex_federation_enabled = true`).

```bash
cd opentofu/shared/aws-gcp-federation && tofu init && tofu plan -var-file=variables.tfvars
```

Expected plan: a pool `aws-workloads`, a provider `aws-account`, one `google_project_iam_member`,
no change to the AWS roles. Apply, then:

```bash
tofu output vertex_wif_audience
gcloud iam workload-identity-pools providers describe aws-account --location global \
  --workload-identity-pool aws-workloads --project ogenki-435905 --format='value(attributeCondition)'
```

Expected: the audience equals `gcp_vertex_wif_audience` in `opentofu/aws/eks/configure/variables.tfvars`
(fix the tfvars and re-apply eks/configure if not); the condition names
`assumed-role/xplane-model-gateway-iam-role/`.

## 2. The cluster side

```bash
kubectl get cm -n flux-system eks-aws-0-vars -o jsonpath='{.data.gcp_vertex_wif_audience}{"\n"}{.data.gcp_project_id}{"\n"}'
kubectl -n agent-gateway get epi xplane-model-gateway
aws eks list-pod-identity-associations --cluster-name aws-0 --namespace agent-gateway \
  --service-account model-gateway --query 'associations[].associationArn'
kubectl -n agent-gateway get pod -l gateway.networking.k8s.io/gateway-name=model-gateway \
  -o jsonpath='{range .items[*]}{.metadata.name} {.status.containerStatuses[*].name} {.status.containerStatuses[*].ready}{"\n"}{end}'
```

Expected: both keys set; the `EPI` `Synced` and `Ready`; one association; each proxy pod runs
`agentgateway` and `aws-creds`, both ready.

## 3. The sidecar, from inside the pod

The proxy image has no shell; ask from the sidecar's Python:

```bash
pod=$(kubectl -n agent-gateway get pod -l gateway.networking.k8s.io/gateway-name=model-gateway -o name | head -1)
kubectl -n agent-gateway exec "$pod" -c aws-creds -- /usr/bin/python3.11 -c \
  "import urllib.request as u, json; b='http://127.0.0.1:8099/latest/meta-data/iam/security-credentials'; n=u.urlopen(b).read().decode(); print(n, sorted(json.load(u.urlopen(b+'/'+n))))"
```

Expected: `pod-identity ['AccessKeyId', 'Expiration', 'SecretAccessKey', 'Token']`. Never print the
values.

## 4. One Gemini call

From a run on the public listener, or with a public token for `maku-gateway.public.gemini-light`
(runbook 04's token recipe), call `/m/gemini-light/v1/chat/completions` with one short message.

| Result | Meaning, next step |
|---|---|
| 200 with content | Proven. Record the response's `model` and the access log's `cost` |
| 401/403 from `sts.googleapis.com` in the proxy log, `The caller does not have permission` or `unauthorized` | The pool refused the ARN: compare the provider's condition with `aws iam get-role --role-name xplane-model-gateway-iam-role --query Role.Arn` (role name, account) |
| 403 `PERMISSION_DENIED` from Vertex naming `aiplatform.endpoints.predict` | The grant: check the `principalSet` member and the role suffix |
| 403 from Vertex naming the federated principal, not the permission | Vertex refused direct federated access (design, open question 1): add a service account the principalSet impersonates; a host change |
| `GCP access token fetch timed out` | Egress: `hubble observe --pod agent-gateway/<pod> --verdict DROPPED` for `sts.googleapis.com` or `169.254.170.23:80` |

## 5. Over an hour

Leave a call every 10 minutes for 70 minutes (`for i in $(seq 7); do <call>; sleep 600; done`).
Expected: all 200, so the Google token refresh (1 h) works through the sidecar. Then confirm the proxy
holds no key: `kubectl -n agent-gateway get pod "$pod" -o yaml | grep -c -i private_key` is `0`.

## 6. Close

Record the results file. If every step passed, the design's status becomes "live-proven on aws-0"
and ADR-0063 moves to Accepted (cloud-native-ref PR).
