#!/usr/bin/env python3
"""Hermes Multi-Provider API Server — OpenAI-kompatibel für OpenWebUI.

Port 8650. Einziger Endpunkt den OpenWebUI braucht.

Features:
  GET  /v1/models           → alle Modelle aus Hermes Config
  POST /v1/chat/completions  → routed zum richtigen Provider, streaming SSE

Provider-Routing:
  deepseek-v4-pro   → api.deepseek.com
  deepseek-v4-flash → api.deepseek.com
  deepseek/*        → openrouter.ai (200+ Modelle)
  anthropic/*       → openrouter.ai
  openai/*          → openrouter.ai
  google/*          → openrouter.ai
  
  Fallback → Hermes API Server (8642)
"""
import json, os, sys, re, logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HOME = Path(os.path.expanduser("~"))
PORT = 8650

# ── Config ──────────────────────────────────────────────

ENV = {}
env_file = HOME / ".hermes" / ".env"
if env_file.exists():
    for line in env_file.read_text().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip().strip('"').strip("'")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [API] %(message)s")
log = logging.getLogger("hermes-api")

# ── Models ───────────────────────────────────────────────

def get_models():
    """Dynamisch aus Hermes Config + .env — echte hinterlegte Modelle."""
    models = []
    
    # DeepSeek (wenn Key vorhanden)
    if ENV.get("DEEPSEEK_API_KEY"):
        models += [
            {"id":"deepseek-v4-pro","object":"model","owned_by":"deepseek"},
            {"id":"deepseek-v4-flash","object":"model","owned_by":"deepseek"},
        ]
    
    # OpenRouter (200+ Modelle via gleichen Key)
    if ENV.get("OPENROUTER_API_KEY"):
        models += [
            {"id":"deepseek/deepseek-chat","object":"model","owned_by":"openrouter"},
            {"id":"anthropic/claude-sonnet-4","object":"model","owned_by":"openrouter"},
            {"id":"openai/gpt-4o","object":"model","owned_by":"openrouter"},
            {"id":"openai/gpt-4o-mini","object":"model","owned_by":"openrouter"},
            {"id":"google/gemini-2.5-pro","object":"model","owned_by":"openrouter"},
            {"id":"google/gemini-2.5-flash","object":"model","owned_by":"openrouter"},
            {"id":"meta-llama/llama-4-maverick","object":"model","owned_by":"openrouter"},
            {"id":"mistral/mistral-large","object":"model","owned_by":"openrouter"},
            {"id":"microsoft/phi-4","object":"model","owned_by":"openrouter"},
        ]
    
    # NVIDIA (wenn Key vorhanden)
    if ENV.get("NVIDIA_API_KEY"):
        models.append({"id":"nvidia/nemotron","object":"model","owned_by":"nvidia"})
    
    # Hermes default
    if not models:
        models = [{"id":"hermes-agent","object":"model","owned_by":"hermes"}]
    
    return models


def resolve_provider(model):
    """Resolve model → (api_url, api_key)."""
    if model in ("deepseek-v4-pro","deepseek-v4-flash"):
        return "https://api.deepseek.com/v1/chat/completions", ENV.get("DEEPSEEK_API_KEY","")
    if "/" in model:
        return "https://openrouter.ai/api/v1/chat/completions", ENV.get("OPENROUTER_API_KEY","")
    if model.startswith("nvidia"):
        return "https://integrate.api.nvidia.com/v1/chat/completions", ENV.get("NVIDIA_API_KEY","")
    return "http://127.0.0.1:8642/v1/chat/completions", ENV.get("API_SERVER_KEY","")


def proxy_request(body, stream=False):
    """Proxy chat completion to correct provider. Returns (bytes, content_type, status)."""
    model = body.get("model", "hermes-agent")
    url, key = resolve_provider(model)
    
    if not key:
        return json.dumps({"error":{"message":f"No API key for {model}","type":"invalid_request_error"}}).encode(), "application/json", 401
    
    # Fix model name for external APIs
    req_body = dict(body)
    req_body["stream"] = stream
    
    log.info(f"Routing {model} → {url} (stream={stream})")
    
    req = Request(url, data=json.dumps(req_body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    
    try:
        with urlopen(req, timeout=180) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "application/json")
            return data, ct, resp.status
    except HTTPError as e:
        body = e.read() if e.fp else b"{}"
        log.error(f"Upstream error {e.code}: {body[:200]}")
        return body, "application/json", e.code
    except Exception as e:
        log.error(f"Proxy error: {e}")
        return json.dumps({"error":{"message":str(e)[:200],"type":"proxy_error"}}).encode(), "application/json", 502


# ── HTTP Handler ────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
    
    def _json(self, data, status=200):
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()
    
    def do_GET(self):
        if self.path in ("/v1/models","/models"):
            data = {"object":"list","data":get_models()}
            self._json(data)
            log.info(f"GET {self.path} → {len(data['data'])} models")
        else:
            self.send_response(404); self._cors(); self.end_headers()
    
    def do_POST(self):
        if self.path not in ("/v1/chat/completions","/chat/completions"):
            self.send_response(404); self._cors(); self.end_headers(); return
        
        length = int(self.headers.get("Content-Length", 0))
        body_str = self.rfile.read(length).decode()
        
        try:
            body = json.loads(body_str)
            model = body.get("model","hermes-agent")
        except:
            self._json({"error":{"message":"Invalid JSON","type":"invalid_request_error"}},400)
            return
        
        stream = body.get("stream", False)
        data, ct, status = proxy_request(body, stream)
        
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(data)
        log.info(f"POST /v1/chat/completions model={model} → {status}")


if __name__ == "__main__":
    import socketserver
    server = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler)
    server.allow_reuse_address = True
    log.info(f"Hermes API Server → http://0.0.0.0:{PORT}")
    log.info(f"  OpenWebUI: http://192.168.2.150:{PORT}/v1")
    log.info(f"  Models: {len(get_models())} verfügbar")
    server.serve_forever()
