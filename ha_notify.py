"""Hermes HA Notification Tools."""
import json, os, requests
from pathlib import Path

def _get_ha_config():
    try:
        import yaml
        cfg_path = Path.home() / ".hermes" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            ha = cfg.get("homeassistant", {})
            if ha.get("url") and ha.get("token"):
                return ha["url"], ha["token"]
    except: pass
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        url = ""; token = ""
        prefix = "HASS_" + "TOKEN="
        for line in env.read_text().split("\n"):
            if line.startswith("HASS_URL="):
                url = line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
            if line.startswith(prefix):
                token = line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
        if url and token: return url, token
    return "", ""

def _auth(token):
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

def ha_notify(message, title="Hermes", service="notify", entity="notify", task_id=""):
    if not message.strip(): return json.dumps({"error": "message required"})
    url, token = _get_ha_config()
    if not url or not token: return json.dumps({"error": "HA not configured"})
    try:
        r = requests.post(f"{url}/api/services/{service}/{entity}", headers=_auth(token),
                         json={"message": message, "title": title}, timeout=10)
        s = "sent" if r.status_code in (200,201) else f"error {r.status_code}"
        return json.dumps({"status": s})
    except Exception as e: return json.dumps({"error": str(e)[:200]})

def ha_notify_bot(message, pr="", title="Hermes Bot", task_id=""):
    extra = f" (PR #{pr})" if pr else ""
    return ha_notify(f"{message}{extra}", title=title)

def ha_send_message(message, task_id=""):
    url, token = _get_ha_config()
    if not url or not token: return json.dumps({"error": "HA not configured"})
    try:
        r = requests.post(f"{url}/api/conversation/process", headers=_auth(token),
                         json={"text": message}, timeout=30)
        if r.status_code == 200:
            speech = r.json().get("response",{}).get("speech",{}).get("plain",{}).get("speech","?")
            return json.dumps({"response": speech})
        return json.dumps({"error": f"HA {r.status_code}"})
    except Exception as e: return json.dumps({"error": str(e)[:200]})
