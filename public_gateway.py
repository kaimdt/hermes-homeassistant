#!/usr/bin/env python3
"""Hermes Public Gateway — API Key-geschützter Zugriff auf alle Services.

Port 8650 — kann via Cloudflare oder direkt exponiert werden.

Endpoints:
  /health                  — Health Check (no auth)
  /chat                    — HA Chat UI (HTML)
  /api/chat/{path}         — HA Chat API (requires X-API-Key)
  /status                  — System Status Dashboard (HTML)
  /api/status              — System Status JSON (requires X-API-Key)
  /api/dashboard/{path}    — Hermes Dashboard Proxy (requires X-API-Key)

Auth: X-API-Key header checked against PostgreSQL api_keys table.
"""
import json, os, sys, hashlib, http.server, socketserver, urllib.request, urllib.error, logging
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
sys.path.insert(0, str(HOME / ".hermes" / "plugins" / "hermes-remote"))
from hermes_db import query

PORT = 8650
HOST = "0.0.0.0"

# Internal service URLs
DASHBOARD = "http://127.0.0.1:9119"
API_SERVER = "http://127.0.0.1:8642"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [GW] %(message)s")
logger = logging.getLogger("hermes-gw")


def check_api_key(key: str) -> bool:
    """Validate API key against PostgreSQL."""
    if not key:
        return False
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    try:
        rows = query("SELECT id FROM api_keys WHERE key_hash=%s AND active=true", (key_hash,))
        return len(rows) > 0
    except:
        return False


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    
    def _require_key(self) -> bool:
        key = self.headers.get("X-API-Key", "")
        return check_api_key(key)
    
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_html(self, html, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode() if isinstance(html, str) else html)
    
    def _proxy(self, target_url: str, data: str = None, method: str = "GET"):
        """Proxy request to internal service."""
        try:
            if data is not None and method == "POST":
                req = urllib.request.Request(target_url, data=data.encode(), method="POST")
                req.add_header("Content-Type", "application/json")
            else:
                req = urllib.request.Request(target_url)
            # Add Hermes API key when proxying to API server  
            if API_SERVER in target_url:
                # Key loaded from env file, cached in module
                if hasattr(sys.modules['__main__'], 'HERMES_API_KEY'):
                    api_key = sys.modules['__main__'].HERMES_API_KEY
                else:
                    import os
                    p = os.path.expanduser("~/.hermes/.env")
                    api_key = ""
                    if os.path.exists(p):
                        with open(p) as fh:
                            for line in fh:
                                if line.startswith("API_SERVER_KEY="):
                                    api_key = line.split("=", 1)[1].strip().strip('"')
                                    break
                    sys.modules['__main__'].HERMES_API_KEY = api_key
                if api_key:
                    req.add_header("Authorization", "Bearer " + api_key)
            
            for header, value in self.headers.items():
                if header.lower() not in ("host", "x-api-key", "content-type", "content-length"):
                    req.add_header(header, value)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                self.send_response(resp.status)
                for h, v in resp.getheaders():
                    if h.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(h, v)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self._send_json({"error": str(e)[:200]}, 502)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-API-Key,Authorization,X-HA-User")
        self.end_headers()
    
    def do_GET(self):
        path = self.path.rstrip("/") or "/"
        
        # Health — no auth
        if path == "/health":
            return self._send_json({"status": "ok", "service": "hermes-public-gw", "port": PORT})
        
        # OpenAI-compatible /v1/models
        if path == "/v1/models":
            models = [
                {"id":"deepseek-v4-pro","name":"DeepSeek V4 Pro","provider":"DeepSeek"},
                {"id":"deepseek-v4-flash","name":"DeepSeek V4 Flash","provider":"DeepSeek"},
                {"id":"deepseek/deepseek-chat","name":"DeepSeek V3 (OpenRouter)","provider":"OpenRouter"},
                {"id":"anthropic/claude-sonnet-4","name":"Claude Sonnet 4","provider":"OpenRouter"},
                {"id":"openai/gpt-4o","name":"GPT-4o","provider":"OpenRouter"},
                {"id":"openai/gpt-4o-mini","name":"GPT-4o Mini","provider":"OpenRouter"},
                {"id":"google/gemini-2.5-pro","name":"Gemini 2.5 Pro","provider":"OpenRouter"},
                {"id":"google/gemini-2.5-flash","name":"Gemini 2.5 Flash","provider":"OpenRouter"},
                {"id":"meta-llama/llama-4-maverick","name":"Llama 4 Maverick","provider":"OpenRouter"},
                {"id":"mistral/mistral-large","name":"Mistral Large","provider":"OpenRouter"},
                {"id":"microsoft/phi-4","name":"Phi-4","provider":"OpenRouter"},
            ]
            data = [{"id":m["id"],"object":"model","owned_by":m["provider"]} for m in models]
            return self._send_json({"object":"list","data":data})
        
        # Models list — no auth (public)
        if path == "/api/models":
            # Comprehensive model list from Hermes + OpenRouter
            models = [
                {"id":"deepseek-v4-pro","name":"DeepSeek V4 Pro","provider":"DeepSeek"},
                {"id":"deepseek-v4-flash","name":"DeepSeek V4 Flash","provider":"DeepSeek"},
                {"id":"deepseek/deepseek-chat","name":"DeepSeek V3 (OpenRouter)","provider":"OpenRouter"},
                {"id":"anthropic/claude-sonnet-4","name":"Claude Sonnet 4","provider":"OpenRouter"},
                {"id":"openai/gpt-4o","name":"GPT-4o","provider":"OpenRouter"},
                {"id":"openai/gpt-4o-mini","name":"GPT-4o Mini","provider":"OpenRouter"},
                {"id":"google/gemini-2.5-pro","name":"Gemini 2.5 Pro","provider":"OpenRouter"},
                {"id":"google/gemini-2.5-flash","name":"Gemini 2.5 Flash","provider":"OpenRouter"},
                {"id":"meta-llama/llama-4-maverick","name":"Llama 4 Maverick","provider":"OpenRouter"},
                {"id":"mistral/mistral-large","name":"Mistral Large","provider":"OpenRouter"},
                {"id":"microsoft/phi-4","name":"Phi-4","provider":"OpenRouter"},
            ]
            return self._send_json({"models": models})
        
        # Chat HTML
        if path in ("/chat", "/chat/"):
            chat_html = HOME / ".hermes" / "plugins" / "hermes-homeassistant" / "ha_chat.html"
            if chat_html.exists():
                return self._send_html(chat_html.read_text())
            return self._send_json({"error": "Chat HTML not found"}, 404)
        
        # Status Dashboard HTML
        if path in ("/status", "/status/"):
            # Build inline status page
            html = '''<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hermes Status</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#041c1c;color:#ffe6cb;font:13px/1.5 Inter,system-ui;padding:20px}
h1{font-size:18px;color:rgba(255,230,203,.5);margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}
.card{padding:14px;border:1px solid rgba(255,230,203,.06);border-radius:8px}.card h3{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:rgba(255,230,203,.3);margin-bottom:4px}
.card .val{font-size:24px;font-weight:700}.card .sub{font-size:9px;color:rgba(255,230,203,.25);margin-top:4px}
#time{text-align:center;margin-top:16px;font-size:10px;color:rgba(255,230,203,.15)}</style></head>
<body><h1>Hermes System Status</h1><div class="grid" id="cards"></div><div id="time"></div>
<script>
async function load(){try{const r=await fetch('/api/status');const d=await r.json();
const c=[['Gateway',d.gateway_running?'Running':'Down',d.gateway_running?'#4ade80':'#ef4444','PID '+d.gateway_pid],
['Webhook',d.webhook_active?'Active':'Inactive',d.webhook_active?'#4ade80':'#ef4444',d.webhook_events||''],
['PostgreSQL',d.pg_status||'?',d.pg_status==='connected'?'#4ade80':'#ef4444',(d.pg_memories||0)+' mem · '+(d.pg_knowledge||0)+' kb'],
['CPU',d.cpu_usage||'?','#a78bfa','Load: '+d.load_1m],
['RAM',d.ram_usage||'?','#a78bfa',(d.ram_free||'?')+' / '+(d.ram_total||'?')],
['Disk',d.disk_usage||'?','#a78bfa',d.system_uptime||'?'],
['Sessions',d.active_sessions||'0','#a78bfa','Total: '+d.total_sessions],
['Plugins',d.plugin_count||'0','#4ade80',(d.plugin_list||[]).slice(0,3).join(', ')],
['Issues',(d.issues||[]).length||0,(d.issues||[]).length?'#ef4444':'#4ade80',(d.issues||[])[0]?.msg||'All good']];
document.getElementById('cards').innerHTML=c.map(([t,v,cl,sub])=>`<div class="card"><h3>${t}</h3><div class="val" style="color:${cl||'#ffe6cb'}">${v}</div><div class="sub">${sub}</div></div>`).join('');
document.getElementById('time').textContent='Updated: '+new Date().toLocaleTimeString()}catch(e){}
}load();setInterval(load,5000)</script></body></html>'''
            return self._send_html(html)
        
        # API Status (needs key)
        if path == "/api/status":
            if not self._require_key():
                return self._send_json({"error": "Invalid or missing API key"}, 401)
            return self._proxy(f"{DASHBOARD}/api/plugins/github-bot/system/status")
        
        # API Chat
        if path.startswith("/api/chat/"):
            if not self._require_key():
                return self._send_json({"error": "Invalid or missing API key"}, 401)
            sub_path = path[len("/api/chat/"):]
            return self._proxy(f"{DASHBOARD}/api/plugins/github-bot/ha/chat/{sub_path}")
        
        # Dashboard Proxy
        if path.startswith("/dashboard"):
            if not self._require_key():
                return self._send_json({"error": "Invalid or missing API key"}, 401)
            return self._proxy(f"{DASHBOARD}{path}")
        
        self._send_json({"error": "Not found", "endpoints": ["/health","/chat","/status","/api/status","/api/chat","/dashboard"]}, 404)
    
    def do_POST(self):
        # Read body
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""
        
        # OpenAI-compatible /v1/chat/completions
        if self.path == "/v1/chat/completions":
            return self._proxy(f"{API_SERVER}/v1/chat/completions", body.decode("utf-8"), "POST")
        
        if self.path.startswith("/api/chat/") or self.path.startswith("/api/status"):
            if not self._require_key():
                return self._send_json({"error": "Invalid or missing API key"}, 401)
        
        # Proxy POST to internal services
        if self.path.startswith("/api/chat/"):
            sub_path = self.path[len("/api/chat/"):]
            target = f"{DASHBOARD}/api/plugins/github-bot/ha/chat/{sub_path}"
        elif self.path.startswith("/api/status"):
            target = f"{DASHBOARD}/api/plugins/github-bot/system/status"
        elif self.path.startswith("/dashboard"):
            target = f"{DASHBOARD}{self.path}"
        else:
            return self._send_json({"error": "Endpoint not found"}, 404)
        
        try:
            req = urllib.request.Request(target, data=body, method="POST")
            req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
            for h, v in self.headers.items():
                if h.lower() not in ("host", "content-length", "x-api-key"):
                    req.add_header(h, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result)
        except Exception as e:
            self._send_json({"error": str(e)[:200]}, 502)
    
    def do_DELETE(self):
        if self.path.startswith("/api/chat/"):
            if not self._require_key():
                return self._send_json({"error": "Invalid or missing API key"}, 401)
            sub_path = self.path[len("/api/chat/"):]
            target = f"{DASHBOARD}/api/plugins/github-bot/ha/chat/{sub_path}"
            try:
                req = urllib.request.Request(target, method="DELETE")
                for h, v in self.headers.items():
                    if h.lower() not in ("host", "x-api-key"):
                        req.add_header(h, v)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp.read())
            except Exception as e:
                self._send_json({"error": str(e)[:200]}, 502)
        else:
            self._send_json({"error": "Method not allowed"}, 405)
    
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")


def run():
    server = socketserver.ThreadingTCPServer((HOST, PORT), GatewayHandler)
    server.allow_reuse_address = True
    logger.info(f"Hermes Public Gateway on http://{HOST}:{PORT}")
    logger.info(f"  /health    — no auth")
    logger.info(f"  /chat      — Chat UI (HTML)")
    logger.info(f"  /api/chat/ — Chat API (key required)")
    logger.info(f"  /status    — Status Dashboard (HTML)")
    logger.info(f"  /api/status — Status JSON (key required)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    run()
