"""Pi-Memory Bridge — dedicated HTTP endpoints for Pi.dev.
Pi.dev ruft diese Endpoints per curl auf, um mit dem Hermes Memory zu arbeiten.

Endpoints:
  GET  /v1/memory/search?q=keyword
  POST /v1/memory/add  {"content":"...","priority":"normal","category":"general"}
  GET  /v1/memory/stats

Gateway hook: plugins/gateway/pi_memory.py
"""
import json, logging, os, sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".hermes" / "plugins" / "hermes-remote"))
from hermes_db import query, execute, execute_returning

logger = logging.getLogger(__name__)


def register(app_ref, gateway_ref):
    
    async def memory_search_handler(request):
        q = request.rel_url.query.get("q", "")
        if not q:
            return web.json_response({"entries": []})
        try:
            rows = query(
                "SELECT content, priority, category FROM memories WHERE archived=false AND content ILIKE %s ORDER BY accessed_at DESC LIMIT 10",
                (f"%{q}%",)
            )
            return web.json_response({"entries": rows, "query": q})
        except Exception as e:
            return web.json_response({"error": str(e)[:200]}, status=500)
    
    async def memory_add_handler(request):
        try:
            data = await request.json()
            content = data.get("content", "")
            priority = data.get("priority", "normal")
            category = data.get("category", "general")
            if not content.strip():
                return web.json_response({"error": "content required"}, status=400)
            
            row = execute_returning(
                "INSERT INTO memories (content, priority, category) VALUES (%s,%s,%s) RETURNING id",
                (content, priority, category)
            )
            execute("UPDATE memories SET accessed_at=now() WHERE id=%s", (row["id"],))
            return web.json_response({"status": "saved", "id": row["id"][:12]})
        except Exception as e:
            return web.json_response({"error": str(e)[:200]}, status=500)
    
    async def memory_stats_handler(request):
        try:
            active = query("SELECT count(*) as n FROM memories WHERE archived=false")[0]["n"]
            archived = query("SELECT count(*) as n FROM memories WHERE archived=true")[0]["n"]
            return web.json_response({"active": active, "archived": archived, "total": active + archived})
        except Exception as e:
            return web.json_response({"error": str(e)[:200]}, status=500)
    
    from aiohttp import web
    app_ref.router.add_get("/v1/memory/search", memory_search_handler)
    app_ref.router.add_post("/v1/memory/add", memory_add_handler)
    app_ref.router.add_get("/v1/memory/stats", memory_stats_handler)
    logger.info("Pi-Memory Bridge: /v1/memory/search, /v1/memory/add, /v1/memory/stats")
