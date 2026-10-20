# HAMi and GPU sharing for model serving

**Date:** 2026-10-20 · **Verdict:** HAMi watch; native time-slicing with per-model memory fractions
next · **Read at:** HAMi v2.10.0
[`4707fb0`](https://github.com/Project-HAMi/HAMi/tree/4707fb02c91c545bc7343ce26dba4c32919f9a3e)
(2026-08-21, `main` `228a333` checked for later changes), HAMi-core
[`b216ba1`](https://github.com/Project-HAMi/HAMi-core/tree/b216ba1be1b8e21488d1c7370ed3357b3049aad1)
(the submodule v2.10.0 pins), Karpenter `statenode.go@1f754cf` and `cluster.go@637bceb`, vLLM
`cache.py@9499c94`, Bottlerocket up to v1.67.0. Code read, nothing executed; *unverified* marks the
rest. Summary on the site: [GPU sharing](../../../website/content/docs/platform/ai-platform/serving/autoscaling-and-gpu.md#gpu-sharing).

## The need

Two small always-warm models, the FIM coder (`xplane-qwen-coder-fim`) and LlamaGuard
(`xplane-llamaguard3-1b`), each hold a whole L4 (24 GB) for a fraction of its memory. Packing them on
one GPU frees a node: about **$263 a month** on a `g6.xlarge` spot in `eu-west-3` ($0.352–0.370/h,
AWS spot price history, 2026-10-18→20) and about **$325** on a `g2-standard-4` spot in
`europe-west4` ([$0.4457/h](https://gcloud-compute.com/g2-standard-4.html), third-party). Adding the
quantized 7B coder to the same GPU roughly doubles it. The L4 has no MIG.

## Conclusion

**HAMi: watch.** Its memory cap works; its compute cap does not apply to vLLM; Karpenter cannot
provision for its resources; and it replaces the platform-managed GPU stack on both clouds, with
privileged components and a second scheduler. **Next: each platform's native time-slicing, with
vLLM's own `--gpu-memory-utilization` dividing the memory**, on a dedicated GPU pool. The operations
HAMi would add cost more than the node it saves.

## What HAMi is

| Aspect | Finding |
|---|---|
| Components | A mutating webhook; a **second scheduler** (`hami-scheduler`, kube-scheduler plus an HTTP extender, [configmap.yaml](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/templates/scheduler/configmap.yaml#L25-L43)); its own NVIDIA device plugin (a fork) and a monitor DaemonSet; HAMi-core `libvgpu.so`, injected into every GPU container. The default scheduler is untouched. DRA is a separate project, [HAMi-DRA](https://github.com/Project-HAMi/HAMi-DRA) v0.2.3 |
| Resources | `nvidia.com/gpu`, `gpumem`, `gpumem-percentage`, `gpucores`, `priority` ([values.yaml](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/values.yaml#L25-L28)). A node advertises `gpu` × `deviceSplitCount` (10 by default, [values.yaml](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/values.yaml#L347)); `gpumem` and `gpucores` are not node resources but fitted by the extender ([_helpers.tpl](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/templates/_helpers.tpl#L198-L200)) |
| Memory isolation | `/etc/ld.so.preload` plus `CUDA_DEVICE_MEMORY_LIMIT_n` ([server.go](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/pkg/device-plugin/nvidiadevice/nvinternal/plugin/server.go#L833-L883)): an allocation over the cap gets `CUDA_ERROR_OUT_OF_MEMORY` ([allocator.c](https://github.com/Project-HAMi/HAMi-core/blob/b216ba1be1b8e21488d1c7370ed3357b3049aad1/src/allocator/allocator.c#L36-L62)), and `cuMemGetInfo` reports the cap as the total ([memory.c](https://github.com/Project-HAMi/HAMi-core/blob/b216ba1be1b8e21488d1c7370ed3357b3049aad1/src/cuda/memory.c#L486-L512)). **Cooperative, not a security boundary**: `CUDA_DISABLE_CONTROL=true` skips the preload ([server.go](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/pkg/device-plugin/nvidiadevice/nvinternal/plugin/server.go#L866-L883)) |
| Compute isolation | A token bucket on `cuLaunchKernel*` only ([memory.c](https://github.com/Project-HAMi/HAMi-core/blob/b216ba1be1b8e21488d1c7370ed3357b3049aad1/src/cuda/memory.c#L541-L551)); **`cuGraphLaunch` passes unthrottled** ([graph.c](https://github.com/Project-HAMi/HAMi-core/blob/b216ba1be1b8e21488d1c7370ed3357b3049aad1/src/cuda/graph.c#L267-L270), also on `main`), and vLLM decodes through CUDA graphs. Under the default policy the limit never engages ([HAMi-core#350](https://github.com/Project-HAMi/HAMi-core/issues/350), open); on an L4 `gpucores=25` gives 47–56% of the GPU ([#360](https://github.com/Project-HAMi/HAMi-core/issues/360), open) |
| Requirements | Kubernetes ≥ 1.23, NVIDIA as the **default container runtime** ([README](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/README.md#L99-L100)) |
| Maturity | CNCF Incubating since [2026-07-02](https://www.cncf.io/projects/hami/); 4.9k stars, 188 contributors, a release every 1–3 months; [74 listed adopters](https://github.com/Project-HAMi/website/blob/e1e5424541ef5c31a7ac7b5d3260ae650449323c/src/data/adopters.json), LinkedIn and SAP among them. Apache-2.0; HAMi-core gained its LICENSE file only after the v2.10.0 pin. An inactivity bot closes unfixed issues |

## Fit with our setup

| Question | Finding |
|---|---|
| Bottlerocket (EKS) | HAMi must **replace** Bottlerocket's built-in device plugin: both advertise `nvidia.com/gpu`, and one plugin per resource name runs per node ([core-kit#1035](https://github.com/bottlerocket-os/bottlerocket-core-kit/pull/1035)). Bottlerocket ≥ 1.63.0 can switch its own off; `/usr/local` is read-only, which [#1714](https://github.com/Project-HAMi/HAMi/pull/1714) worked around. Whether HAMi's fork avoids the upstream plugin's crashloop on Bottlerocket is *unverified* |
| Karpenter | It cannot simulate `gpumem`, so scale-up fails ([#1099](https://github.com/Project-HAMi/HAMi/issues/1099)); node-capacity reporting ([#2874](https://github.com/Project-HAMi/HAMi/pull/2874)) is on `main`, in no release; Karpenter's NodeOverlay could declare it, alpha behind a gate. **NodePool limits count the GPUs a node advertises** ([statenode.go](https://github.com/kubernetes-sigs/karpenter/blob/1f754cfd42d9c43d72f35fac82fb6ec0d1d92561/pkg/controllers/state/statenode.go#L458-L474), [cluster.go](https://github.com/kubernetes-sigs/karpenter/blob/637bcebae2d485b865554bed18ec72d94a398e80/pkg/controllers/state/cluster.go#L871-L875)): one HAMi node (10 vGPUs) exceeds our cap of 4, and time-slicing replicas would too (inferred from code) |
| GKE | GKE's managed device plugin and drivers must be disabled (`gke-no-default-nvidia-gpu-device-plugin=true`, `gpu-driver-version=disabled`, [docs](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/gpu-operator)), and HAMi wants an NVIDIA default runtime ([#1153](https://github.com/Project-HAMi/HAMi/issues/1153)): in practice the GPU Operator in place of GKE's stack. GKE's own [time-sharing](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/timesharing-gpus) (no memory limits, chosen by node selector, works with auto-provisioning) and [MPS](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/nvidia-mps-gpus) (memory and thread caps, needs `hostIPC`) already cover the need |
| vLLM | `--gpu-memory-utilization` becomes a fraction of HAMi's cap. vLLM's CUDA-graph memory profiling has run out of memory under HAMi ([HAMi-core#181](https://github.com/Project-HAMi/HAMi-core/issues/181); vLLM closed its side, [vllm#40937](https://github.com/vllm-project/vllm/issues/40937)). Overhead: +1.3% time to first token and +2.1% per token on v2.9.0 in HAMi's own single-tenant A100 benchmark ([benchmark.md](https://github.com/Project-HAMi/website/blob/fef5b35b751781f9cc26dd6a22600e216219112c/docs/userguide/benchmark.md)); about 80% on one launch-heavy workload ([#164](https://github.com/Project-HAMi/HAMi-core/issues/164), closed unfixed) |
| Security | The device plugin is `privileged` with `hostPID` and hostPaths on `/usr/bin`, `/var`, `/sys`, `/tmp`, `/run/containerd` ([values.yaml](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/values.yaml#L411-L418), [DaemonSet](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/templates/device-plugin/daemonsetnvidia.yaml#L207-L250)); the monitor needs `SYS_ADMIN`; host directories and `/tmp/vgpulock` are created 0777, shared by every GPU pod ([server.go](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/pkg/device-plugin/nvidiadevice/nvinternal/plugin/server.go#L851-L854)). The webhook sees **every pod creation** (`failurePolicy: Ignore`) and moves any pod requesting `nvidia.com/gpu` to its scheduler ([webhook.go](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/pkg/scheduler/webhook.go#L99-L113)); its ClusterRole patches all pods and nodes ([clusterrole.yaml](https://github.com/Project-HAMi/HAMi/blob/4707fb02c91c545bc7343ce26dba4c32919f9a3e/charts/hami/templates/scheduler/clusterrole.yaml#L9-L17)). Chart defaults to override: NodePort Services, kube-scheduler pulled from `registry.cn-hangzhou.aliyuncs.com`. vLLM pods themselves can stay restricted |
| DRA | The NVIDIA DRA driver's time-slicing and [MPS](https://dra-driver-nvidia-gpu.sigs.k8s.io/docs/guides/mps/) sharing are alpha; pods share a GPU only through the **same** ResourceClaim in one namespace; Karpenter simulates it from 1.15 behind `DRANVIDIAGPU` on Kubernetes ≥ 1.36 ([EKS docs](https://docs.aws.amazon.com/eks/latest/userguide/device-management-nvidia-time-slicing.md)); Bottlerocket v1.66.0 adds opt-in DRA. Promising, not simpler today |

## Options compared

| Option | Memory | Compute | EKS (Bottlerocket) | GKE | Note |
|---|---|---|---|---|---|
| **Time-slicing + vLLM memory fractions** | Each model self-limits (`--gpu-memory-utilization`, [cache.py](https://github.com/vllm-project/vllm/blob/9499c949be17a8a10ac4176a33843e82469d2ff5/vllm/config/cache.py#L215-L220)) | Best effort | Native setting since v1.25 | Native, works with auto-provisioning | One fault domain; Karpenter counts each request as a whole GPU |
| MPS | Equal split, enforced | Thread-percentage cap | Native since v1.54 | Needs `hostIPC` | Breaks the baseline pod security profile on GKE |
| HAMi | Cap per container | Not effective on vLLM | Replaces the built-in plugin | Replaces GKE's GPU stack | Karpenter blind to `gpumem` |
| DRA sharing | As MPS or time-slicing | Same | Bottlerocket v1.66 | *Unverified* | Alpha |
| kvcached | Elastic KV cache across models | — | Needs one of the above | Same | Complements sharing; static caps defeat its elasticity |
| Two vLLM processes in one pod | Self-limited | Best effort | Works | Works | Breaks one Deployment per model and per-model KEDA |
| `g6f` fractional L4 | Hard partition | Hard partition | **Not offered in `eu-west-3`** | None | `g6f.xlarge` (3 GB) about $0.10/h spot in `us-east-1` |
| LlamaGuard on CPU | — | — | — | — | Latency to benchmark |

Only MPS, HAMi's memory cap and `g6f` enforce isolation; the rest change scheduling.

## Recommendation

**Next, on the serving roadmap: "GPU sharing for the small always-warm models".**
- GKE: native time-sharing, `max-shared-clients-per-gpu` 2–3.
- EKS: Bottlerocket `device-sharing-strategy="time-slicing"` on a dedicated, tainted GPU pool.
- Every shared model sets an explicit `--gpu-memory-utilization`; the `InferenceService` composition
  gains a sharing option.
- The GPU pool's limit is rewritten to count shared replicas, not physical GPUs.

**HAMi: watch. Reconsider when** HAMi-core #350 and #360 close with evidence on L4 and
`cuGraphLaunch` is throttled; node-capacity reporting ships in a release with a Karpenter recipe; or
we need caps enforced between teams, or time-slicing causes an out-of-memory between neighbours.

**DRA: reconsider when** the NVIDIA DRA driver's sharing reaches beta and Karpenter's `DRANVIDIAGPU`
gate is GA.
