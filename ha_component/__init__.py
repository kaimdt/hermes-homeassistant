"""Hermes Chat — Home Assistant Custom Component.

INSTALLATION:
  cp -r ha_component/ /config/custom_components/hermes_chat/

CONFIGURATION (configuration.yaml):
  hermes_chat:
    api_url: "http://192.168.2.150:9119/api/plugins/github-bot/ha/chat"
    api_token: "your-secret-token"

USAGE:
  Add to any Lovelace dashboard:
    type: custom:hermes-chat-card
"""
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import logging

DOMAIN = "hermes_chat"
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    cfg = config.get(DOMAIN, {})
    api_url = cfg.get("api_url", "http://192.168.2.150:9119/api/plugins/github-bot/ha/chat")
    api_token = cfg.get("api_token", "")

    hass.data[DOMAIN] = {"api_url": api_url, "api_token": api_token}
    
    # Register Lovelace resource
    hass.http.register_static_path(
        "/hermes-chat-card.js",
        hass.config.path("custom_components/hermes_chat/hermes-chat-card.js"),
        cache_headers=False,
    )
    
    # Register frontend
    try:
        hass.components.frontend.add_extra_js_url(hass, "/hermes-chat-card.js")
    except Exception:
        pass
    
    _LOGGER.info(f"Hermes Chat ready — {api_url}")
    return True


async def async_setup_entry(hass, entry):
    return True
