from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


class ModelConfigurationError(RuntimeError):
    """Raised when no usable chat-model configuration exists."""


def _build_model_options() -> dict[str, Any]:
    """Build common chat-model configuration."""

    settings = get_settings()

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None

    if not api_key and not settings.llm_base_url:
        raise ModelConfigurationError("No LLM API key or compatible base URL is configured.")

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

    return model_options


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Create the general SafeOps planning/chat model."""

    settings = get_settings()
    model_options = _build_model_options()

    base_url = str(settings.llm_base_url) if settings.llm_base_url else ""

    if "groq.com" in base_url.lower():
        # Incident planning is primarily tool routing and
        # evidence selection, not deep chain-of-thought reasoning.
        # Non-thinking mode reduces unnecessary generation latency.
        model_options["extra_body"] = {
            "reasoning_effort": "none",
        }

    return ChatOpenAI(
        **model_options,
    )


@lru_cache(maxsize=1)
def get_report_chat_model() -> BaseChatModel:
    """Create the model used for structured incident reports."""

    settings = get_settings()

    model_options = _build_model_options()

    # Stable report generation is preferable to creative sampling.
    model_options["temperature"] = 0

    base_url = str(settings.llm_base_url) if settings.llm_base_url else ""

    if "groq.com" in base_url.lower():
        # JSON Object Mode forces syntactically valid JSON.
        # response_format is a standard Chat Completions parameter.
        model_options["model_kwargs"] = {
            "response_format": {
                "type": "json_object",
            }
        }

        # Groq-specific Qwen parameter. Report synthesis does
        # not need the reasoning trace used for agent planning.
        model_options["extra_body"] = {
            "reasoning_effort": "none",
        }

    return ChatOpenAI(
        **model_options,
    )
