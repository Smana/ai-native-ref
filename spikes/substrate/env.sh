# Sourced by the numbered scripts. Set before running:
#   KUBECONFIG  gcp-0 only; the scripts refuse any other cluster
#   SUBSTRATE   a checkout of agent-substrate/substrate at v0.5.0, with ate-setup and kubectl-ate
#               built into $SUBSTRATE/bin (go build -o bin/ ./cmd/ate-setup ./cmd/kubectl-ate)
set -euo pipefail
: "${KUBECONFIG:?point KUBECONFIG at gcp-0}" "${SUBSTRATE:?point SUBSTRATE at a v0.5.0 checkout}"
export KUBECONFIG
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REG=europe-west4-docker.pkg.dev/ogenki-435905/substrate-spike
ATE_SETUP=$SUBSTRATE/bin/ate-setup
KUBECTL_ATE=$SUBSTRATE/bin/kubectl-ate
case "$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')" in
  *gcp-0*) ;;
  *) echo "KUBECONFIG is not gcp-0" >&2; exit 1 ;;
esac
