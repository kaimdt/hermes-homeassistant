"""HA Chat Backend — PostgreSQL-persistente Multi-Chat API.

Endpoints:
  GET  /ha/chat/list          → alle Chats des Users
  POST /ha/chat/create        → neuen Chat erstellen
  GET  /ha/chat/{id}/messages → Nachrichten eines Chats
  POST /ha/chat/{id}/send     → Nachricht senden + Antwort
  DELETE /ha/chat/{id}        → Chat löschen
"""
import json, os, sys
from pathlib import Path
from datetime import datetime

HOME = Path(os.path.expanduser("~"))
sys.path.insert(0, str(HOME / ".hermes" / "plugins" / "hermes-remote"))
from hermes_db import query, execute, execute_returning

# API Key check
def _check_key(request):
    """Simple API key auth for HA."""
    key = request.headers.get("X-HA-API-Key", "")
    if not key:
        key = request.headers.get("Authorization", "").replace("Bearer ", "")
    # Accept Hermes API keys from api_keys table
    if key:
        rows = query("SELECT id FROM api_keys WHERE key_hash = encode(sha256(%s::bytea),'hex') AND active=true", (key.encode(),))
        if rows:
            return rows[0]["ha_user"] if "ha_user" in rows[0] else "default"
    return None


def list_chats(ha_user: str = "default") -> str:
    rows = query(
        "SELECT id, title, model, created_at, updated_at FROM ha_chats WHERE ha_user=%s AND active=true ORDER BY updated_at DESC LIMIT 50",
        (ha_user,)
    )
    chats = [{
        "id": r["id"],
        "title": r["title"],
        "model": r["model"],
        "created": str(r["created_at"])[:19],
        "updated": str(r["updated_at"])[:19],
    } for r in rows]
    return json.dumps({"chats": chats})


def create_chat(ha_user: str = "default", title: str = "New Chat", model: str = "deepseek-v4-pro") -> str:
    row = execute_returning(
        "INSERT INTO ha_chats (title, ha_user, model) VALUES (%s,%s,%s) RETURNING id,created_at",
        (title, ha_user, model)
    )
    return json.dumps({"id": row["id"], "title": title, "model": model, "created": str(row["created_at"])[:19]})


def get_messages(chat_id: int) -> str:
    rows = query(
        "SELECT id, role, content, created_at FROM ha_messages WHERE chat_id=%s ORDER BY created_at ASC",
        (chat_id,)
    )
    msgs = [{
        "id": r["id"],
        "role": r["role"],
        "content": r["content"],
        "time": str(r["created_at"])[11:19],
    } for r in rows]
    return json.dumps({"messages": msgs, "chat_id": chat_id})


def send_message(chat_id: int, content: str, ha_user: str = "default") -> str:
    # Save user message
    execute(
        "INSERT INTO ha_messages (chat_id, role, content) VALUES (%s,'user',%s)",
        (chat_id, content)
    )
    execute(
        "UPDATE ha_chats SET updated_at=now() WHERE id=%s",
        (chat_id,)
    )
    
    # Auto-title: first message
    chat_info = query("SELECT title FROM ha_chats WHERE id=%s", (chat_id,))
    if chat_info and chat_info[0]["title"] == "New Chat":
        title = content[:60] + ("..." if len(content) > 60 else "")
        execute("UPDATE ha_chats SET title=%s WHERE id=%s", (title, chat_id))
    
    # Get response from Hermes via OpenAI API
    try:
        import requests
        # Get chat history for context
        history = query(
            "SELECT role, content FROM ha_messages WHERE chat_id=%s ORDER BY created_at ASC LIMIT 50",
            (chat_id,)
        )
        messages = [{"role": r["role"], "content": r["content"]} for r in history]
        
        # Call Hermes API server
        api_url = "http://127.0.0.1:8642/v1/chat/completions"
        api_key = os.environ.get("HERMES_HA_KEY", os.environ.get("API_SERVER_KEY", ""))
        
        r = requests.post(api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": chat_info[0].get("model", "deepseek-v4-pro") if chat_info else "deepseek-v4-pro",
                  "messages": [{"role":"system","content":"Du bist Hermes, ein hilfreicher AI Assistant. Antworte auf Deutsch. Halte Antworten präzise."}] + messages},
            timeout=120)
        
        if r.status_code == 200:
            response = r.json()["choices"][0]["message"]["content"]
        else:
            response = f"Error: Hermes API returned {r.status_code}"
    except Exception as e:
        response = f"Hallo! Hermes ist bereit. Was kann ich für dich tun?\n\n(API-Fehler: {str(e)[:100]})"
    
    # Save assistant message
    execute(
        "INSERT INTO ha_messages (chat_id, role, content) VALUES (%s,'assistant',%s)",
        (chat_id, response)
    )
    
    return json.dumps({"response": response, "chat_id": chat_id})


def delete_chat(chat_id: int) -> str:
    execute("UPDATE ha_chats SET active=false WHERE id=%s", (chat_id,))
    return json.dumps({"status": "deleted", "chat_id": chat_id})
