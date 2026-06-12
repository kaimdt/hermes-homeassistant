"""Home Assistant Gateway Platform — Bidirectional Chat.

HOW TO SET UP (Home Assistant side):

1. Add to configuration.yaml:
```yaml
rest_command:
  hermes_message:
    url: "http://192.168.2.150:8644/ha/message"
    method: POST
    content_type: "application/json"
    payload: '{"message":"{{ message }}","user":"{{ user }}"}'

input_text:
  hermes_chat_input:
    name: Hermes Chat
    max: 255

automation:
  - alias: "Send to Hermes"
    trigger:
      platform: state
      entity_id: input_text.hermes_chat_input
    action:
      - service: rest_command.hermes_message
        data:
          message: "{{ states('input_text.hermes_chat_input') }}"
          user: "kaimdt"
      - service: input_text.set_value
        data:
          value: ""
        target:
          entity_id: input_text.hermes_chat_input
```

2. Restart Home Assistant.
3. Hermes Gateway auto-detects incoming messages on /ha/message.
4. Hermes responds via ha_notify back to HA.

ABRUF VON HA: Hermes sendet Updates per ha_notify()
"""

# This file registers a gateway webhook route when loaded by Hermes Gateway.
# The actual platform adapter is auto-discovered from plugins/gateway/ directory.


def register_gateway_routes(app, gateway):
    """Register HA-specific routes on the Hermes Gateway."""
    import json, logging
    from aiohttp import web

    logger = logging.getLogger(__name__)

    async def ha_message_handler(request):
        """Receive message from Home Assistant."""
        try:
            data = await request.json()
            message = data.get("message", "").strip()
            user = data.get("user", "kaimdt")

            if not message:
                return web.json_response({"status": "error", "error": "empty message"}, status=400)

            # Route to Hermes
            response = await gateway.send_message(
                platform="homeassistant",
                chat_id="ha-home",
                thread_id=None,
                text=message,
                user_name=user,
            )

            logger.info(f"HA → Hermes: '{message[:80]}' from {user}")
            return web.json_response({"status": "ok", "response": str(response)[:200]})

        except Exception as e:
            logger.error(f"HA message error: {e}")
            return web.json_response({"status": "error", "error": str(e)[:200]}, status=500)

    app.router.add_post("/ha/message", ha_message_handler)
    logger.info("Home Assistant gateway route registered: POST /ha/message")
