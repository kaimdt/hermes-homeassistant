"""Hermes Chat Sensor Platform."""
from homeassistant.helpers.entity import Entity
from . import DOMAIN, HermesStatusSensor

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    api_url = discovery_info.get("api_url", "http://192.168.2.150:9119")
    async_add_entities([
        HermesStatusSensor(api_url, "status"),
        HermesStatusSensor(api_url, "active_tasks"),
        HermesStatusSensor(api_url, "sessions"),
    ])
