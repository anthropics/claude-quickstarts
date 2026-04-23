"""REST endpoints for runtime system settings (API key, system prompt, defaults)."""

from fastapi import APIRouter

from computer_use_demo.api.system.schemas import (
    ApiKeyIn,
    ApiKeyOut,
    BaseUrlIn,
    BaseUrlOut,
    SystemInfoOut,
    SystemPromptIn,
    SystemPromptOut,
)
from computer_use_demo.api.system.services import config_store
from computer_use_demo.settings import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_TOOL_VERSION,
    NOVNC_URL,
)
from computer_use_demo.tools.groups import TOOL_GROUPS

router = APIRouter(prefix="/api/system", tags=["system"])


AVAILABLE_MODELS = [
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5-20251001",
]


@router.get("", response_model=SystemInfoOut)
async def get_system_info() -> SystemInfoOut:
    return SystemInfoOut(
        providers=["anthropic", "bedrock", "vertex"],
        models=AVAILABLE_MODELS,
        tool_versions=[g.version for g in TOOL_GROUPS],
        default_provider=DEFAULT_PROVIDER,
        default_model=DEFAULT_MODEL,
        default_tool_version=DEFAULT_TOOL_VERSION,
        has_api_key=config_store.has_api_key(),
        base_url=config_store.get_base_url(),
        system_prompt_suffix=config_store.get_system_prompt(),
        novnc_url=NOVNC_URL,
    )


@router.get("/api-key", response_model=ApiKeyOut)
async def get_api_key() -> ApiKeyOut:
    return ApiKeyOut(has_key=config_store.has_api_key())


@router.put("/api-key", response_model=ApiKeyOut)
async def put_api_key(body: ApiKeyIn) -> ApiKeyOut:
    config_store.set_api_key(body.api_key)
    return ApiKeyOut(has_key=config_store.has_api_key())


@router.get("/base-url", response_model=BaseUrlOut)
async def get_base_url() -> BaseUrlOut:
    return BaseUrlOut(base_url=config_store.get_base_url())


@router.put("/base-url", response_model=BaseUrlOut)
async def put_base_url(body: BaseUrlIn) -> BaseUrlOut:
    config_store.set_base_url(body.base_url)
    return BaseUrlOut(base_url=config_store.get_base_url())


@router.get("/system-prompt", response_model=SystemPromptOut)
async def get_system_prompt() -> SystemPromptOut:
    return SystemPromptOut(suffix=config_store.get_system_prompt())


@router.put("/system-prompt", response_model=SystemPromptOut)
async def put_system_prompt(body: SystemPromptIn) -> SystemPromptOut:
    config_store.set_system_prompt(body.suffix)
    return SystemPromptOut(suffix=config_store.get_system_prompt())
