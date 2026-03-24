"""Settings API router — view and update agent configuration."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMSettingsResponse(BaseModel):
    provider: str
    model: str
    api_url: str
    temperature: float
    max_tokens: int


class LLMSettingsUpdate(BaseModel):
    provider: str = Field(..., description="LLM provider: anthropic, openai, ollama")
    model: str = Field(..., description="Model ID")
    api_key: str = Field("", description="API key (empty for Ollama)")
    api_url: str = Field("", description="Custom API URL (empty for defaults)")
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=256, le=32768)


class AgentSettingsResponse(BaseModel):
    max_steps: int
    auto_approve_reads: bool
    auto_approve_writes: bool


class AgentSettingsUpdate(BaseModel):
    max_steps: int = Field(20, ge=5, le=50)
    auto_approve_reads: bool = True
    auto_approve_writes: bool = False


@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(user: CurrentUser):
    """Get current LLM provider settings."""
    return LLMSettingsResponse(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_url=settings.llm_api_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


@router.put("/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(update: LLMSettingsUpdate, user: CurrentUser):
    """Update LLM provider settings and reinitialize the provider."""
    settings.llm_provider = update.provider
    settings.llm_model = update.model
    settings.llm_api_key = update.api_key
    settings.llm_api_url = update.api_url
    settings.llm_temperature = update.temperature
    settings.llm_max_tokens = update.max_tokens

    # Reinitialize the provider
    from app.llm.registry import initialize_provider

    try:
        await initialize_provider(
            provider_type=update.provider,
            model_id=update.model,
            api_key=update.api_key,
            api_url=update.api_url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize provider: {e}")

    logger.info("LLM settings updated: %s / %s", update.provider, update.model)
    return LLMSettingsResponse(
        provider=update.provider,
        model=update.model,
        api_url=update.api_url,
        temperature=update.temperature,
        max_tokens=update.max_tokens,
    )


@router.get("/agent", response_model=AgentSettingsResponse)
async def get_agent_settings(user: CurrentUser):
    """Get current agent behavior settings."""
    return AgentSettingsResponse(
        max_steps=settings.agent_max_steps,
        auto_approve_reads=settings.agent_auto_approve_reads,
        auto_approve_writes=settings.agent_auto_approve_writes,
    )


@router.put("/agent", response_model=AgentSettingsResponse)
async def update_agent_settings(update: AgentSettingsUpdate, user: CurrentUser):
    """Update agent behavior settings."""
    settings.agent_max_steps = update.max_steps
    settings.agent_auto_approve_reads = update.auto_approve_reads
    settings.agent_auto_approve_writes = update.auto_approve_writes
    logger.info("Agent settings updated: max_steps=%d", update.max_steps)
    return AgentSettingsResponse(
        max_steps=update.max_steps,
        auto_approve_reads=update.auto_approve_reads,
        auto_approve_writes=update.auto_approve_writes,
    )
