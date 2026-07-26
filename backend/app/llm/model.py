from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


class ModelConfigurationError(RuntimeError):
    """Raised when no usable chat-model configuration exists."""


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Create the configured SafeOps chat model."""

    settings = get_settings()

    api_key = (
        settings.llm_api_key.get_secret_value()
        if settings.llm_api_key
        else None
    )

    if not api_key and not settings.llm_base_url:
        raise ModelConfigurationError(
            "No LLM API key or compatible base URL is configured."
        )

    if not api_key:
        api_key = "local-development-key"

    model_options: dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": api_key,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }

    if settings.llm_base_url:
        model_options["base_url"] = settings.llm_base_url

    return ChatOpenAI(**model_options)