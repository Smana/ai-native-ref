#!/usr/bin/env python3
# requires: python3
"""The model gateway's aws-creds sidecar on aws-0 (infrastructure/aws-0/agent-gateway/model-gateway/aws-creds/server.py).

It answers google-cloud-auth 1.16's AWS source (external_account, aws1) from the pod's EKS Pod
Identity session, because that library reads AWS credentials from env or an IMDS-shaped URL only.
Against a fake Pod Identity agent:

  A1  The role path returns a name; <role path>/<name> returns AccessKeyId, SecretAccessKey and
      Token: the three fields the library deserialises (AwsSecurityCredentials).
  A2  It presents the agent the token file's CURRENT contents (kubelet rotates it) as Authorization.
  A3  An agent failure is a 502 with no detail; an unknown path a 404; a log line never carries a
      credential.
  A4  /healthz is 503 without Pod Identity's env, 200 with it.
  A5  It listens on loopback only.

Run: python3 scripts/ci/tests/test-model-gateway-aws-creds.py
"""
import http.server
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
SERVER = ROOT / "infrastructure/aws-0/agent-gateway/model-gateway/aws-creds/server.py"
ROLE = "/latest/meta-data/iam/security-credentials"
SECRET = "fake-secret-value"  # pragma: allowlist secret
problems = []
seen_auth = []


class Agent(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        seen_auth.append(self.headers.get("Authorization"))
        if self.headers.get("Authorization") != pathlib.Path(os.environ["TOKEN_FILE"]).read_text().strip():
            self.send_response(401); self.end_headers(); return
        body = json.dumps({"AccessKeyId": "ASIAFAKE", "SecretAccessKey": SECRET, "Token": "fake-session",
                           "AccountId": "111122223333", "Expiration": "2026-11-26T20:00:00Z"}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def start(env, port):
    p = subprocess.Popen([sys.executable, "-I", str(SERVER)], env=env, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            return p
        except OSError:
            time.sleep(0.1)
    p.kill()
    raise SystemExit("FAIL: the sidecar did not listen")


with tempfile.TemporaryDirectory() as tmp:
    token = pathlib.Path(tmp, "eks-pod-identity-token")
    token.write_text("token-one\n")
    os.environ["TOKEN_FILE"] = str(token)
    agent = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Agent)
    threading.Thread(target=agent.serve_forever, daemon=True).start()
    port = free_port()
    env = {"PATH": os.environ.get("PATH", ""), "LISTEN_PORT": str(port),
           "AWS_CONTAINER_CREDENTIALS_FULL_URI": f"http://127.0.0.1:{agent.server_address[1]}/v1/credentials",
           "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE": str(token)}
    proc = start(env, port)
    try:
        code, name = get(port, ROLE)
        code2, body = get(port, f"{ROLE}/{name}")
        creds = json.loads(body) if code2 == 200 else {}
        if code != 200 or not name or {k: creds.get(k) for k in ("AccessKeyId", "SecretAccessKey", "Token")} != \
                {"AccessKeyId": "ASIAFAKE", "SecretAccessKey": SECRET, "Token": "fake-session"}:
            problems.append(f"A1: role {code} {name!r}, credentials {code2} {body!r}")
        token.write_text("token-two\n")
        get(port, f"{ROLE}/{name}")
        if seen_auth[-2:] != ["token-one", "token-two"]:
            problems.append(f"A2: the agent saw Authorization {seen_auth}, not the token file's current contents")
        if get(port, "/latest/meta-data/placement/availability-zone")[0] != 404:
            problems.append("A3: an unknown path must be a 404")
        if get(port, "/healthz")[0] != 200:
            problems.append("A4: /healthz must be 200 with Pod Identity's env")
        agent.shutdown(); agent.server_close()
        code, body = get(port, f"{ROLE}/{name}")
        if code != 502 or "127.0.0.1" in body:
            problems.append(f"A3: an agent failure must be a bare 502, got {code} {body!r}")
        try:  # this host's outward address: a UDP connect sends nothing
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
                u.connect(("10.255.255.255", 9))
                ip = u.getsockname()[0]
        except OSError:
            ip = None
        if not ip or ip.startswith("127."):
            print("SKIP A5: no non-loopback address to probe")
        else:
            try:
                socket.create_connection((ip, port), timeout=0.5).close()
                problems.append(f"A5: the sidecar answers on {ip}, not loopback only")
            except OSError:
                pass
    finally:
        proc.terminate()
        _, err = proc.communicate(timeout=5)
    if SECRET in err or "fake-session" in err:
        problems.append("A3: the sidecar logged a credential")
    port2 = free_port()
    bare = {"PATH": env["PATH"], "LISTEN_PORT": str(port2)}
    proc = start(bare, port2)
    try:
        if get(port2, "/healthz")[0] != 503:
            problems.append("A4: /healthz must be 503 without Pod Identity's env")
    finally:
        proc.terminate(); proc.communicate(timeout=5)

for p in problems:
    print(f"FAIL {p}")
print(f"==> aws-creds sidecar: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
