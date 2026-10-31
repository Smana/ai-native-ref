---
title: Autoscaling & GPUs
weight: 10
description: Three KEDA triggers on leading vLLM signals, why minReplicas is never zero, and the GPU and storage foundation underneath.
lastVerified: 2026-10-20
aliases:
  - /docs/platform/ai-platform/autoscaling-and-gpu/
  - /docs/platform/ai-platform/serving/autoscaling-and-gpu/
---

Scaling a GPU workload is not scaling a web service. A cold start is 30–90
seconds of model load and CUDA-graph compilation, a replica costs an entire
L4, and by the time a lagging signal like request count has moved, the users
who caused it have already waited. Everything below follows from that.

## Three triggers, OR-combined

One KEDA `ScaledObject` per model, always rendered, with three Prometheus
triggers evaluated against VictoriaMetrics — any one at or above threshold
drives a scale-up. Verified against the pinned KCL module
(`apis/inferenceservice/kcl/main.k` in `Smana/crossplane-configuration`):

| # | Signal | Query | Default threshold |
|---|---|---|---|
| 1 | batch saturation | `max(vllm:num_requests_running{model_name="X"}) / scalar(vector(<maxNumSeqs>))` | `0.7` |
| 2 | KV-cache pressure | `max(vllm:kv_cache_usage_perc{model_name="X"})` | `0.6` |
| 3 | queue depth | `max(vllm:num_requests_waiting{model_name="X"})` | `8` |

All three are **leading** signals: they fire before the batch saturates,
before the cache evicts, before the queue builds. And `max()` rather than an
average is deliberate — it tracks the hottest replica instead of a fleet mean
that would hide it behind idle capacity.

Defaults: `pollingInterval: 15s`, `cooldownPeriod: 300s`.

Trigger 1's denominator is the claim's own `model.maxNumSeqs`. That field is
not only a memory setting: raising it to fit more concurrent requests also
raises the bar for a scale-up, because saturation is measured as a fraction
of it.

![The three KEDA triggers OR-combined against VictoriaMetrics, the two metric families vLLM exposes, and the dashboards and alerts they feed](/images/diagrams/llm-platform-3.svg)

## Why `minReplicas` is never zero

Scale-to-zero on a Prometheus-driven autoscaler is a deadlock, not a
trade-off: at zero replicas there is no pod, so there is no
`vllm:num_requests_running` series, so no trigger can fire, so nothing ever
scales back up. The metric that would wake the model only exists once the
model is already awake.

That deadlock was first worked around with the KEDA HTTP add-on, which put a
proxy in the data path and scaled on a lagging request count. It is **no
longer used**. What replaced it is simply `minReplicas: 1` plus leading
signals — the deadlock disappears once a replica is always present, and the
AI Gateway routes directly to each vLLM Service with no scaling proxy in
front of the fleet.

The cost is explicit rather than hidden: four models at `min=1` hold four
GPUs continuously, whether or not anyone sends a request.

A fourth, opt-in trigger on the InferencePool saturation gauge is specified but **not
shipped**; see the
[serving roadmap]({{< relref "/docs/status.md#serving-roadmap" >}}) before
citing it as delivered.

## The GPU foundation

Karpenter NodePool `gpu-l4`:

- **Single-GPU `g6` instances only.** The NodePool explicitly excludes
  multi-GPU SKUs such as `g6.12xlarge` and `g6.48xlarge`, so one claim can
  never consume the whole GPU budget.
- **Spot-first**, with the reclaim consequence below.
- **Bottlerocket NVIDIA AMI.** There is no NVIDIA device-plugin DaemonSet —
  the Bottlerocket NVIDIA variant advertises `nvidia.com/gpu` through the
  kubelet natively.
- **Capped at `nvidia.com/gpu: "4"`** across the whole pool.
- **`consolidationPolicy: WhenEmpty`**, not the default
  `WhenEmptyOrUnderutilized`. An always-warm model serving one request a
  minute looks underutilised to Karpenter, and consolidating its node would
  trigger exactly the cold start `minReplicas: 1` exists to avoid.

Spot reclaim can still force a 30–90s multi-AZ PVC re-attach. That is an
accepted trade for a personal platform and would not be for a team tier.

## Weights on shared storage

An Amazon S3 Files filesystem — POSIX semantics over S3 — is mounted RWX at
`/models` by both the preload Job and the serving pod, each under its own
`subPath`.

One operational must-know: the PV is provisioned out-of-band, with a
hand-copied `volumeHandle` in `apps/aws-0/llm/models-pvc.yaml` that every
`tofu apply` of `opentofu/aws/llm-platform/` regenerates. After a rebuild,
fetch it with `tofu -chdir=opentofu/aws/llm-platform output -raw volume_handle`,
update that file, and delete the existing PV+PVC so Flux recreates them
(`volumeHandle` is immutable) — otherwise every mount fails against the old
filesystem id.

The consequence worth understanding: **the serving pod never fetches
weights itself.** They arrive over the CSI mount, so each claim's serving
ServiceAccount carries only a per-claim **read-only** EKS Pod Identity,
scoped to its own weights prefix and rendered by the composition — write
access belongs solely to the shared preload Job's identity
(`xplane-llm-models-preload`). That is also why the serving pod's egress
policy can be kube-dns only, while `world:443` is granted solely to the
short-lived preload Job — the runtime pod cannot reach HuggingFace even in
principle.

[ADR-0004]({{< relref "/docs/decisions/0004-amazon-s3-files-for-model-weights-storage.md" >}})
records why this replaced an init-container sync, and
[ADR-0003]({{< relref "/docs/decisions/0003-vllm-production-stack-over-kserve.md" >}})
why vLLM Production Stack was chosen over KServe + llm-d.

## GPU sharing {#gpu-sharing}

Today every model holds a whole L4. The two small always-warm models, the FIM coder
(`xplane-qwen-coder-fim`) and LlamaGuard (`xplane-llamaguard3-1b`), use a fraction of its 24 GB:
packing them on one GPU frees a node, about $263 a month on a `g6.xlarge` spot and $325 on a
`g2-standard-4` spot. The L4 has no MIG, so sharing is done in software. Options checked on
2026-10-20 ([evaluation](https://github.com/Smana/ai-native-ref/blob/main/docs/superpowers/specs/2026-10-20-hami-gpu-sharing-research.md)):

| Option | Isolation | Verdict |
|---|---|---|
| **Native time-slicing + vLLM memory fractions** | Memory: each model limits itself with `--gpu-memory-utilization`. Compute: best effort | **Next.** Native on GKE and on Bottlerocket; no new component |
| MPS | Memory split and thread caps, enforced | Needs `hostIPC` on GKE, which the pod security baseline forbids |
| [HAMi](https://project-hami.io/) | Memory cap per container; its compute cap misses CUDA graphs, which vLLM decodes with | **Watch.** It replaces the GPU device plugin on both clouds, adds a privileged DaemonSet and a second scheduler, and Karpenter cannot provision for its resources |
| DRA sharing (NVIDIA DRA driver) | As time-slicing or MPS | **Watch:** alpha; Karpenter support behind a gate on Kubernetes 1.36 |
| `g6f` fractional L4 | Hard partition | Not offered in `eu-west-3` |

Two traps for any of them: **Karpenter's NodePool limit counts the GPUs a node advertises**, so a
time-sliced node with 3 replicas counts as 3 against `nvidia.com/gpu: "4"`; and time-slicing makes
the models on one GPU one fault domain, so their memory fractions must add up to less than 1.

## Future improvements

[kvcached](https://github.com/ovg-project/kvcached) gives the serving engine virtual memory for its
KV cache, backed by GPU memory only on demand, so several models can share one GPU elastically; it
could let the two small always-warm models, the FIM model (`xplane-qwen-coder-fim`) and LlamaGuard
(`xplane-llamaguard3-1b`), which each hold a whole L4 today, share one. It needs [GPU sharing](#gpu-sharing)
first, and a change to the `InferenceService` composition. HAMi's fixed memory caps would defeat its
elasticity.
