#!/usr/bin/env bash
# Spike measurements (docs/superpowers/specs/2026-10-17-substrate-spike.md). Needs kubectl-ate
# from the v0.5.0 tag on PATH, KUBECONFIG pointing at gcp-0, and
#   kubectl -n ate-system port-forward svc/atenet-router 18081:8081
# The router's plain HTTP port reaches an actor's port 80 only; agent-server listens on 8000, so
# requests go through the CONNECT listener (8081) with the port in the tunnel's authority.
# Usage: measure.sh start <template> <n> | conversation | baseline <n>
set -euo pipefail
AS=substrate-spike
ROUTER=${ROUTER:-http://127.0.0.1:18081}

now() { date +%s.%N; }
ms() { awk -v a="$1" -v b="$2" 'BEGIN{printf "%d", (b-a)*1000}'; }
oh() { # oh <actor> <method> <path> [json]: agent-server through the atenet router
  curl -sf --max-time 10 --proxytunnel --proxy "$ROUTER" --proxy-header "ate-target-actor: $AS/$1" \
    -X "$2" -H 'Content-Type: application/json' ${4:+--data "$4"} "http://actor:8000$3"
}
node_of() {
  local pod
  pod=$(kubectl ate get actor "$1" -a "$AS" -o json | jq -r '.status.workerAssignment.worker.name // .status.workerAssignment.workerPod // empty')
  kubectl -n "$AS" get pod "$pod" -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo "?"
}
timed() { # timed <label> <cmd...>: prints "label ms"
  local t0 t1; t0=$(now); "${@:2}" >/dev/null; t1=$(now); echo "$1 $(ms "$t0" "$t1")"
}

start() { # M1/M2: create + resume until the wakeup probe passes, then the first 200 via the router
  local tpl=$1 n=$2 i a t0 t1 t2
  for i in $(seq 1 "$n"); do
    a="$tpl-$i-$RANDOM"
    kubectl ate create actor "$a" --template "$tpl" -a "$AS" >/dev/null
    t0=$(now); kubectl ate resume actor "$a" -a "$AS" >/dev/null; t1=$(now)
    until oh "$a" GET /health >/dev/null; do sleep 0.05; done; t2=$(now)
    echo "$tpl run=$i resume_ms=$(ms "$t0" "$t1") first_200_ms=$(ms "$t0" "$t2") node=$(node_of "$a")"
    kubectl ate delete actor "$a" -a "$AS" --any-state >/dev/null
  done
}

events() { oh "$1" GET "/api/conversations/$2/events/search?limit=100" | jq '.items | length'; }
agent_said() { oh "$1" GET "/api/conversations/$2/events/search?limit=100" |
  jq -r '[.items[] | select(.kind=="MessageEvent" and .source=="agent")] | length'; }
wait_reply() { # wait_reply <actor> <cid> <n>: until the agent has sent n messages
  local i; for i in $(seq 1 120); do
    [ "$(agent_said "$1" "$2")" -ge "$3" ] && return 0; sleep 1; done; return 1
}
say() {
  oh "$1" POST "/api/conversations/$2/events" \
    "{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"$3\"}],\"run\":true}" >/dev/null
}

conversation() { # M3-M7
  local a="conv-$RANDOM" cid
  kubectl ate create actor "$a" --template openhands-warm -a "$AS" >/dev/null
  timed resume_initial kubectl ate resume actor "$a" -a "$AS"
  echo "node_initial $(node_of "$a")"
  cid=$(oh "$a" POST /api/conversations '{
    "agent": {"llm": {"model": "openai/mock", "base_url": "http://127.0.0.1:4000/v1",
                      "api_key": "not-a-key", "usage_id": "agent", "num_retries": 0},
              "tools": []},
    "workspace": {"working_dir": "/tmp/ws"},
    "initial_message": {"role": "user", "content": [{"type": "text", "text": "Reply with the word PONG."}], "run": true},
    "autotitle": false}' | jq -r .id)
  wait_reply "$a" "$cid" 1; echo "conversation $cid events=$(events "$a" "$cid")"

  timed M3_pause kubectl ate pause actor "$a" -a "$AS"
  timed M5_resume_after_pause kubectl ate resume actor "$a" -a "$AS"
  echo "node_after_pause $(node_of "$a") events=$(events "$a" "$cid")"

  timed M4_suspend kubectl ate suspend actor "$a" -a "$AS"
  timed M5_resume_after_suspend kubectl ate resume actor "$a" -a "$AS"
  echo "node_after_suspend $(node_of "$a") events=$(events "$a" "$cid")"

  timed M4_suspend_2 kubectl ate suspend actor "$a" -a "$AS"
  echo "moving the worker off $(kubectl -n "$AS" get pods -l ate.dev/worker-pool=openhands -o jsonpath='{.items[0].spec.nodeName}')"
  kubectl -n "$AS" patch workerpool openhands --type json -p \
    '[{"op":"replace","path":"/spec/template/nodeAffinity/requiredDuringSchedulingIgnoredDuringExecution/nodeSelectorTerms/0/matchExpressions/0/operator","value":"NotIn"}]' >/dev/null
  kubectl -n "$AS" rollout status deploy/openhands --timeout=15m >/dev/null
  timed M6_restore_other_node kubectl ate resume actor "$a" -a "$AS"
  echo "node_after_restore $(node_of "$a") events=$(events "$a" "$cid")"

  say "$a" "$cid" "Reply with the word PONG again."
  if wait_reply "$a" "$cid" 2; then echo "M7 continued events=$(events "$a" "$cid")"; else echo "M7 FAILED"; fi
  echo "actor $a kept for inspection"
}

baseline() { # B1: the same image as a GKE Sandbox pod, created -> first 200
  local n=$1 i p t0
  for i in $(seq 1 "$n"); do
    p="baseline-$i-$RANDOM"; t0=$(now)
    kubectl -n "$AS" run "$p" --restart=Never --labels=spike=substrate,app=baseline \
      --image=ghcr.io/openhands/agent-server:1.49.6-python@sha256:02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37 \
      --overrides='{"spec":{"runtimeClassName":"gvisor","nodeSelector":{"cloud.google.com/gke-nodepool":"agents-gvisor"},
        "containers":[{"name":"'"$p"'","image":"ghcr.io/openhands/agent-server:1.49.6-python@sha256:02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37",
        "args":["--host","0.0.0.0","--port","8000"],"resources":{"requests":{"cpu":"1","memory":"2Gi"},"limits":{"cpu":"2","memory":"4Gi"}},
        "readinessProbe":{"httpGet":{"path":"/health","port":8000},"periodSeconds":1}}]}}' >/dev/null
    kubectl -n "$AS" wait pod "$p" --for=condition=Ready --timeout=10m >/dev/null
    echo "baseline run=$i ready_ms=$(ms "$t0" "$(now)") node=$(kubectl -n "$AS" get pod "$p" -o jsonpath='{.spec.nodeName}')"
    kubectl -n "$AS" delete pod "$p" --wait=false >/dev/null
  done
}

"$@"
