#!/usr/bin/env python3
"""Model-Router Proxy: direkter API-Router für echtes Modell-Switching.

Start: python3 model_router.py
Port: 8648

GET  /v1/models   → alle Modelle (public)
POST /v1/chat/completions → routed direkt zum richtigen Provider
"""
import json, os, sys, http.server, urllib.request, urllib.error, logging, hashlib
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
ENV = {}
env_file = HOME / ".hermes" / ".env"
if env_file.exists():
    for line in env_file.read_text().split("\n"):
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip().strip('"').strip("'")

PORT = 8648
logging.basicConfig(level=logging.INFO, format="%(asctime)s [ROUTER] %(message)s")
logger = logging.getLogger("model-router")


def get_models():
    models = [{"id":"hermes-agent","object":"model","owned_by":"hermes"}]
    if ENV.get("DEEPSEEK_API_KEY"):
        models += [
            {"id":"deepseek-v4-pro","object":"model","owned_by":"deepseek"},
            {"id":"deepseek-v4-flash","object":"model","owned_by":"deepseek"},
        ]
    return {"object":"list","data":models}


def route_request(request_body_str, model):
    """Route to correct provider based on model name."""
    body = json.loads(request_body_str)
    
    # DeepSeek direct models
    if model in ("deepseek-v4-pro", "deepseek-v4-flash"):
        url = "https://api.deepseek.com/v1/chat/completions"
        key = ENV.get("DEEPSEEK_API_KEY", "")
        body["model"] = model  # Use exact model name for DeepSeek API
    # Hermes fallback
    else:
        url = "http://127.0.0.1:8642/v1/chat/completions"
        key = ENV.get("API_SERVER_KEY", "")
        body["model"] = "hermes-agent"
    
    if not key:
        return json.dumps({"error":{"message":f"No API key for {model}","type":"invalid_request_error"}}).encode(), 401
    
    logger.info(f"Routing {model} → {url}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read(), resp.status
    except urllib.error.HTTPError as e:
        logger.error(f"Upstream error: {e.code}")
        return e.read() if e.fp else b"{}", e.code
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return json.dumps({"error":{"message":str(e)[:200],"type":"proxy_error"}}).encode(), 502


class RouterHandler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/v1/models":
            data = get_models()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            logger.info("GET /v1/models → %d models", len(data["data"]))
        else:
            self.send_response(404); self._cors(); self.end_headers()
            self.wfile.write(b"not found")
    
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_response(404); self._cors(); self.end_headers()
            return
        
        length = int(self.headers.get("Content-Length", 0))
        body_str = self.rfile.read(length).decode()
        
        try:
            body = json.loads(body_str)
            model = body.get("model", "hermes-agent")
        except:
            self.send_response(400); self._cors(); self.end_headers()
            return
        
        result, status = route_request(body_str, model)
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(result)
        logger.info(f"POST /v1/chat/completions model={model} → {status}")
    
    def log_message(self, fmt, *args):
        logger.debug(fmt % args)


if __name__ == "__main__":
    import socketserver
    server = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), RouterHandler)
    server.allow_reuse_address = True
    logger.info(f"Model Router on http://0.0.0.0:{PORT}")
    logger.info(f"  GET  /v1/models")
    logger.info(f"  POST /v1/chat/completions")
    server.serve_forever()
