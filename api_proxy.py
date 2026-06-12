#!/usr/bin/env python3
"""Hermes API Auth Proxy — multi-key support."""
import os, sys, json, hashlib, http.server, urllib.request, urllib.error, logging

HOME = os.path.expanduser("~")
sys.path.insert(0, os.path.join(HOME, ".hermes", "plugins", "hermes-remote"))
from hermes_db import query, execute

PORT = 8643
UPSTREAM = "http://127.0.0.1:8642"

# Load master key
env_path = os.path.join(HOME, ".hermes", ".env")
MASTER_KEY = ""
prefix = "API_SERVER_" + "KEY="
if os.path.exists(env_path):
    for line in open(env_path).read().split("\n"):
        if line.startswith(prefix):
            MASTER_KEY = line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
            break

logging.basicConfig(level=logging.INFO, format="%(asctime)s [proxy] %(message)s")
logger = logging.getLogger("api-proxy")


def check_key(token):
    if MASTER_KEY and token == MASTER_KEY:
        return "master"
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        rows = query("SELECT name FROM api_keys WHERE key_hash=%s AND active=true", (key_hash,))
        if rows:
            execute("UPDATE api_keys SET last_used=now() WHERE key_hash=%s", (key_hash,))
            return rows[0]["name"]
    except: pass
    return None


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self): self._proxy("POST")
    def do_GET(self): self._proxy("GET")
    def do_DELETE(self): self._proxy("DELETE")
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def _proxy(self, method):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._error(401, "Missing API key"); return
        token = auth[7:]
        name = check_key(token)
        if not name:
            self._error(401, "Invalid API key"); return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else None
        url = UPSTREAM + self.path
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", "Bearer " + MASTER_KEY)
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                self.send_header("Access-Control-Allow-Origin", "*")
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
                logger.info(f"{method} {self.path} — {name}")
        except urllib.error.HTTPError as e:
            self._error(e.code, str(e))
        except Exception as e:
            self._error(502, f"Upstream: {e}")

    def _error(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": {"message": str(msg)[:200]}}).encode())

    def log_message(self, format, *args): pass


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    logger.info(f"Proxy on 0.0.0.0:{PORT} -> {UPSTREAM}")
    server.serve_forever()
