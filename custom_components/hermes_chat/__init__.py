"""Hermes Chat HA Component — with Proxy.

INSTALLATION: Copy custom_components/hermes_chat/ to /config/custom_components/

CONFIGURATION (configuration.yaml):
  hermes_chat:
    api_url: "http://192.168.2.150:9119"

Then HA registers:
  - Panel: /hermes-chat → proxied Chat UI
  - API Proxy: HA forwards all /api/hermes-chat/* → Hermes
"""
import logging
import aiohttp
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

DOMAIN = "hermes_chat"
_LOGGER = logging.getLogger(__name__)


class HermesChatProxyView(HomeAssistantView):
    """Proxy HA Chat API requests to Hermes."""
    url = "/api/hermes-chat/{path:.*}"
    name = "api:hermes_chat"
    requires_auth = True  # Only authenticated HA users
    
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
                async with session.post(url, json=data, headers=headers) as resp:
                    return web.Response(body=await resp.read(), status=resp.status)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Hermes Chat with proxy."""
    conf = config.get(DOMAIN, {})
    api_url = conf.get("api_url", "http://192.168.2.150:9119")
    
    # Register API proxy
    hass.http.register_view(HermesChatProxyView(api_url))
    
    # Register panel with local HTML (proxy-safe)
    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        "hermes_chat",
        "Hermes",
        require_admin=False,
        config={
            "url": "/local/community/hermes-chat/ha_chat.html?v=" + "1.0"
        },
    )
    
    _LOGGER.info(f"Hermes Chat initialized with proxy to {api_url}")
    return True
