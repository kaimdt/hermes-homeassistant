"""Hermes Multi-Model Router Plugin.

Registers OpenAI-compatible endpoints on Hermes Gateway (8644):
  GET  /v1/models          → list ALL configured models from ALL providers
  POST /v1/chat/completions → route to correct provider based on model name

Reads Hermes config.yaml to discover providers and their models.
Supports: DeepSeek, OpenRouter, OpenAI, Anthropic, Google, custom.

Each provider needs API key in ~/.hermes/.env
"""
import json, os, sys, yaml, re
from pathlib import Path
from aiohttp import web

HOME = Path(os.path.expanduser("~"))
CONFIG_FILE = HOME / ".hermes" / "config.yaml"
ENV_FILE = HOME / ".hermes" / ".env"

# ── Config Loading ─────────────────────────────────────

def load_config() -> dict:
    """Load Hermes config.yaml."""
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def load_env() -> dict:
    """Load .env file."""
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    # Merge with os.environ
    env.update(os.environ)
    return env


def discover_models() -> list:
    """Discover all models from all configured providers."""
    try:
        cfg = load_config()
        env = load_env()
    except:
        cfg, env = {}, {}

    models = []
    providers = cfg.get("provider", cfg.get("providers", {}))

    # DeepSeek models (always available if key exists)
    if "DEEPSEEK_API_KEY" in env:
        models.extend([
            {"id": "deepseek-v4-pro", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-v4-flash", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-reasoner", "object": "model", "owned_by": "deepseek"},
        ])

    # OpenRouter models (proxy to 200+ models)
    if "OPENROUTER_API_KEY" in env:
        models.extend([
            {"id": "deepseek/deepseek-chat", "object": "model", "owned_by": "openrouter"},
            {"id": "anthropic/claude-sonnet-4", "object": "model", "owned_by": "openrouter"},
            {"id": "anthropic/claude-3-opus", "object": "model", "owned_by": "openrouter"},
            {"id": "openai/gpt-4o", "object": "model", "owned_by": "openrouter"},
            {"id": "openai/gpt-4o-mini", "object": "model", "owned_by": "openrouter"},
            {"id": "google/gemini-2.5-pro", "object": "model", "owned_by": "openrouter"},
            {"id": "google/gemini-2.5-flash", "object": "model", "owned_by": "openrouter"},
            {"id": "meta-llama/llama-4-maverick", "object": "model", "owned_by": "openrouter"},
            {"id": "mistral/mistral-large", "object": "model", "owned_by": "openrouter"},
            {"id": "microsoft/phi-4", "object": "model", "owned_by": "openrouter"},
        ])

    # NVIDIA models
    if "NVIDIA_API_KEY" in env:
        models.append({"id": "nvidia/nemotron", "object": "model", "owned_by": "nvidia"})

    # Configured provider models from config
    for provider_name, provider_cfg in providers.items():
        if isinstance(provider_cfg, dict):
            provider_models = provider_cfg.get("models", [])
            if isinstance(provider_models, str):
                provider_models = [provider_models]
            for m in provider_models:
                models.append({"id": m, "object": "model", "owned_by": provider_name})

    # Default model from config
    default_model = cfg.get("model", {})
    if isinstance(default_model, dict) and default_model.get("default"):
        mid = default_model["default"]
        if not any(m["id"] == mid for m in models):
            models.insert(0, {"id": mid, "object": "model", "owned_by": default_model.get("provider", "hermes")})

    # Always add hermes-agent
    models.insert(0, {"id": "hermes-agent", "object": "model", "owned_by": "hermes"})

    return models


def resolve_model(model_name: str) -> dict:
    """Resolve model name to provider + API key + base URL."""
    env = load_env()
    models = discover_models()

    # Check if it's in our known models
    model_ids = {m["id"]: m["owned_by"] for m in models}
    provider = model_ids.get(model_name, "deepseek")

    # Route to the right API
    routes = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": env.get("DEEPSEEK_API_KEY", ""),
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": env.get("OPENROUTER_API_KEY", ""),
        },
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": env.get("NVIDIA_API_KEY", ""),
        },
    }

    # DeepSeek models (direct, not via OpenRouter)
    if model_name.startswith("deepseek-v"):
        return routes["deepseek"]

    # OpenRouter models
    if model_name.startswith(("deepseek/", "anthropic/", "openai/", "google/", "meta-llama/", "mistral/", "microsoft/")):
        return routes["openrouter"]

    # Default: use Hermes API server
    # For models configured through Hermes (single-model mode), proxy to Hermes
    return {
        "base_url": "http://127.0.0.1:8642/v1",
        "api_key": env.get("API_SERVER_KEY", ""),
    }


# ── Gateway Hook ──────────────────────────────────────

async def handle(request: web.Request) -> web.Response:
    """Handle /v1/* requests on Hermes Gateway."""
    path = request.path

    # Models list
    if path == "/v1/models":
        models = discover_models()
        return web.json_response({"object": "list", "data": models})

    # Chat completions — route to correct provider
    if path == "/v1/chat/completions":
        return await handle_chat(request)

    return web.json_response({"error": "not found"}, status=404)


async def handle_chat(request: web.Request) -> web.Response:
    """Proxy chat request to correct provider."""
    import aiohttp

    try:
        body = await request.json()
        model_name = body.get("model", "hermes-agent")
    except:
        return web.json_response({"error": {"message": "Invalid JSON", "type": "invalid_request_error"}}, status=400)

    # Get routing info
    route = resolve_model(model_name)
    target_url = f"{route['base_url']}/chat/completions"
    api_key = route["api_key"]

    if not api_key:
        return web.json_response(
            {"error": {"message": f"No API key for model '{model_name}'", "type": "invalid_request_error"}},
            status=401
        )

    # Forward to provider
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # Map our model name to the provider's model name
    body["model"] = model_name  # Keep as-is for direct API

    async with aiohttp.ClientSession() as session:
        async with session.post(target_url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            response_body = await resp.read()
            return web.Response(body=response_body, status=resp.status, content_type="application/json")


# ── Gateway Hook Registration ──────────────────────────

def register(app_ref, gateway_ref):
    """Register /v1/models and /v1/chat/completions on Hermes Gateway."""
    import logging
    logger = logging.getLogger(__name__)

    async def v1_models(request):
        models = discover_models()
        return web.json_response({"object": "list", "data": models})

    async def v1_chat(request):
        return await handle_chat(request)

    app_ref.router.add_get("/v1/models", v1_models)
    app_ref.router.add_post("/v1/chat/completions", v1_chat)
    logger.info("Multi-Model Router: /v1/models + /v1/chat/completions registered")
