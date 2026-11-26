#!/usr/bin/env python3
"""The model gateway's AWS credentials, in the shape Google's client library reads (aws-0 only).

agentgateway 1.6 gets the proxy's Google token through google-cloud-auth 1.16, whose external_account
AWS source reads AWS credentials from AWS_ACCESS_KEY_ID and friends or from an IMDS-shaped URL, never
from EKS Pod Identity. This sidecar is that URL: on loopback only, it answers the two IMDS paths the
library calls, from the pod's Pod Identity session.

  GET /latest/meta-data/iam/security-credentials           -> the role name (text)
  GET /latest/meta-data/iam/security-credentials/<role>    -> {AccessKeyId, SecretAccessKey, Token}
  GET /healthz                                             -> ok, once Pod Identity is injected

It holds the session for one request and writes nothing. Standard library only: it runs in a
distroless image from a ConfigMap. Design: cloud-native-ref
docs/superpowers/specs/2026-11-26-aws-vertex-federation-design.md.
"""
import http.server
import json
import os
import sys
import urllib.request

ROLE_PATH = "/latest/meta-data/iam/security-credentials"
# Any non-empty name: the library reads it from the first path and sends it back on the second.
ROLE_NAME = os.environ.get("ROLE_NAME", "pod-identity")
FIELDS = ("AccessKeyId", "SecretAccessKey", "Token", "Expiration")


def pod_identity_credentials():
    """The Pod Identity agent's session: AWS_CONTAINER_* are what EKS injects in every container."""
    uri = os.environ["AWS_CONTAINER_CREDENTIALS_FULL_URI"]
    with open(os.environ["AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE"], encoding="utf-8") as f:
        token = f.read().strip()  # re-read each time: kubelet rotates it
    request = urllib.request.Request(uri, headers={"Authorization": token})
    with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310 (the agent's own URI)
        body = json.load(response)
    return {k: body[k] for k in FIELDS if k in body}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "aws-creds"
    sys_version = ""

    def _send(self, status, body, ctype="text/plain"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 (http.server's name)
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/healthz":
            ready = all(os.environ.get(k) for k in ("AWS_CONTAINER_CREDENTIALS_FULL_URI",
                                                    "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE"))
            return self._send(200 if ready else 503, "ok" if ready else "no Pod Identity in this pod")
        if path == ROLE_PATH:
            return self._send(200, ROLE_NAME)
        if path == f"{ROLE_PATH}/{ROLE_NAME}":
            try:
                creds = pod_identity_credentials()
            except Exception as e:  # noqa: BLE001 (any failure is the agent's, answered as 502)
                self.log_message("pod identity: %s", type(e).__name__)
                return self._send(502, "pod identity unavailable")
            return self._send(200, json.dumps(creds), "application/json")
        return self._send(404, "not found")

    def log_message(self, fmt, *args):
        # The path and status only: a body here would be a credential.
        sys.stderr.write("aws-creds: " + (fmt % args) + "\n")


def main():
    port = int(os.environ.get("LISTEN_PORT", "8099"))
    # Loopback only: the proxy is the one reader. The pod IP would let any peer the network policy
    # admits ask for the session.
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
