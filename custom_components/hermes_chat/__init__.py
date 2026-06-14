"""Hermes Chat HA Component — with Sensors + Dashboard.

Features:
  - HermesChatProxyView: API proxy (mobile-safe)
  - Sensors: status, active_tasks, messages
  - Panel: embedded chat UI
  - Lovelace Card: hermes-chat-card
"""
import logging
from datetime import timedelta
import aiohttp
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

DOMAIN = "hermes_chat"
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


class HermesChatProxyView(HomeAssistantView):
    """Proxy HA Chat API requests to Hermes."""
    url = "/api/hermes-chat/{path:.*}"
    name = "api:hermes_chat"
    requires_auth = True
    
    def __init__(self, api_url: str):
        self._api_url = api_url.rstrip("/")
    
    async def get(self, request, path=""):
        return await self._proxy(request, path)
    
    async def post(self, request, path=""):
        return await self._proxy(request, path)
    
    async def delete(self, request, path=""):
        return await self._proxy(request, path)
    
    async def _proxy(self, request, path):
        url = f"{self._api_url}/api/plugins/github-bot/ha/chat/{path}"
        headers = {"X-HA-User": request.remote or "ha"}
        async with aiohttp.ClientSession() as session:
            if request.method == "GET":
                async with session.get(url, headers=headers) as resp:
                    return web.Response(body=await resp.read(), status=resp.status)
            else:
                data = await request.json()
                async with session.request(request.method, url, json=data, headers=headers) as resp:
                    return web.Response(body=await resp.read(), status=resp.status)


class HermesStatusSensor(Entity):
    """Sensor for Hermes system status."""
    _attr_icon = "mdi:robot"
    
    def __init__(self, api_url, sensor_type):
        self._api_url = api_url
        self._type = sensor_type
        self._state = "unknown"
        self._attrs = {}
        if sensor_type == "status":
            self._attr_name = "Hermes Status"
        elif sensor_type == "active_tasks":
            self._attr_name = "Hermes Active Tasks"
            self._attr_icon = "mdi:progress-clock"
        elif sensor_type == "sessions":
            self._attr_name = "Hermes Active Sessions"
            self._attr_icon = "mdi:account-group"
    
    @property
    def state(self):
        return self._state
    
    @property
    def extra_state_attributes(self):
        return self._attrs
    
    async def async_update(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._api_url}/api/plugins/github-bot/system/status",
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if self._type == "status":
                            self._state = "online" if data.get("gateway_running") else "offline"
                            self._attrs = {
                                "cpu": data.get("cpu_usage"),
                                "ram": data.get("ram_usage"),
                                "memories": data.get("pg_memories"),
                                "knowledge": data.get("pg_knowledge"),
                            }
                        elif self._type == "active_tasks":
                            active = len(data.get("plugin_list", []))
                            self._state = active
                            self._attrs = {"plugins": data.get("plugin_list", [])}
                        elif self._type == "sessions":
                            self._state = data.get("active_sessions", 0)
                    else:
                        self._state = "error"
        except Exception as e:
            self._state = "unavailable"
            self._attrs = {"error": str(e)[:100]}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Hermes Chat with sensors and dashboard."""
    conf = config.get(DOMAIN, {})
    api_url = conf.get("api_url", "http://192.168.2.150:9119")
    
    # Proxy
    hass.http.register_view(HermesChatProxyView(api_url))
    
    # Sensors
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {"api_url": api_url}, config)
    
    # Dashboard panel
    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        "hermes_chat",
        "Hermes",
        "mdi:robot",
        require_admin=False,
        config={"url": "/local/community/hermes-chat/ha_chat.html?v=2.0"},
    )
    
    # Register Lovelace resources
    hass.http.register_static_path(
        "/local/community/hermes-chat",
        hass.config.path("www/community/hermes-chat"),
        cache_headers=False,
    )
    
    _LOGGER.info(f"Hermes Chat ready: proxy + sensors + panel")
    return True


async def async_setup_entry(hass, entry):
    hass.async_create_task(hass.config_entries.async_forward_entry_setups(entry, ["sensor"]))
    return True
