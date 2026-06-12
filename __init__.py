"""Hermes ↔ Home Assistant Plugin.
Notification tools + bidirectional chat.
"""
from tools.registry import registry
from .ha_notify import ha_notify, ha_notify_bot, ha_send_message

def _check() -> bool:
    try:
        from .ha_notify import _get_ha_config
        url, token = _get_ha_config()
        return bool(url and token)
    except:
        return False

T = [
    ("ha_notify", "Send notification via Home Assistant to all your devices.", ["message"],
     lambda a,k: ha_notify(message=a.get("message",""), title=a.get("title","Hermes"), service=a.get("service","notify"), entity=a.get("entity","notify"), task_id=k.get("task_id",""))),
    ("ha_notify_bot", "Bot notification — sends to HA with PR context.", ["message"],
     lambda a,k: ha_notify_bot(message=a.get("message",""), pr=a.get("pr",""), title=a.get("title","Hermes Bot"), task_id=k.get("task_id",""))),
    ("ha_send_message", "Send message to Home Assistant conversation (bidirectional).", ["message"],
     lambda a,k: ha_send_message(message=a.get("message",""), task_id=k.get("task_id",""))),
]

for name, desc, req, handler_fn in T:
    props = {r: {"type": "string", "description": r} for r in req}
    registry.register(name=name, toolset="homeassistant",
        schema={"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": req}},
        handler=handler_fn, check_fn=_check)
