"""Hermes Chat — Home Assistant Custom Component."""
import logging
from homeassistant.core import HomeAssistant

DOMAIN = "hermes_chat"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Hermes Chat component."""
    conf = config.get(DOMAIN, {})
    api_url = conf.get("api_url", "http://192.168.2.150:9119")
    
    hass.data[DOMAIN] = {
        "api_url": api_url,
        "ha_chat_path": "/local/community/hermes-chat/ha_chat.html",
    }
    
    # Register panel_iframe
    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        "hermes_chat",
        "Hermes",
        require_admin=False,
        config={"url": f"{api_url}/ha-chat.html"},
    )
    
    _LOGGER.info("Hermes Chat component initialized")
    return True

async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    return True
