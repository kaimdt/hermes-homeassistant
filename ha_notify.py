"""Hermes ↔ Home Assistant Notification Tools."""
import json, os, requests
from pathlib import Path


def _get_ha_config():
    """Get HA URL + Token from config."""
    try:
        import yaml
        cfg_path = Path.home() / ".hermes" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            ha = cfg.get("homeassistant", {})
            if ha.get("url") and ha.get("token"):
                return ha["url"], ha["token"]
    except:
        pass
    
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        url, token = "", ""
        for line in env.read_text().split("\n"):
            if line.startswith("HASS_URL=***                url = line.split("=", 1)[1].strip().strip('"\''')
            if line.startswith("HASS_TOKEN=***                token = line.split("=", 1)[1].strip().strip('"\''')
        if url and token:
            return url, token
    return "", ""


def _auth_header(token):
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}


def ha_notify(message, title="Hermes", service="notify", entity="notify", task_id=""):
    if not message.strip():
        return json.dumps({"error": "message required"})
    url, token = _get_ha_config()
    if not url or not token:
        return json.dumps({"error": "HA not configured"})
    try:
        r = requests.post(
            f"{url}/api/services/{service}/{entity}",
            headers=_auth_header(token),
            json={"message": message, "title": title},
            timeout=10,
        )
        return json.dumps({"status": "sent" if r.status_code == 200 else f"error {r.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)[:200]})


def ha_notify_bot(message, pr="", title="Hermes Bot", task_id=""):
    extra = f" (PR #{pr})" if pr else ""
    return ha_notify(f"{message}{extra}", title=title)


def ha_send_message(message, task_id=""):
    url, token = _get_ha_config()
    if not url or not token:
        return json.dumps({"error": "HA not configured"})
    try:
        r = requests.post(
            f"{url}/api/conversation/process",
            headers=_auth_header(token),
            json={"text": message},
            timeout=30,
        )
        if r.status_code == 200:
            resp = r.json()
            speech = resp.get("response", {}).get("speech", {}).get("plain", {}).get("speech", "?")
            return json.dumps({"response": speech})
        return json.dumps({"error": f"HA returned {r.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)[:200]})
