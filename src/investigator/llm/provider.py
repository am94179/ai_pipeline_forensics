"""Lazy construction of the workflow's OpenAI-compatible chat model."""

from langchain_openai import ChatOpenAI

from investigator.config.llm_settings import LLMSettings


def build_chat_model() -> ChatOpenAI:
    """Build the configured model without invoking it.

    Settings validation occurs here, rather than at module import time, so
    deterministic tools and credential-free tests remain usable without LLM
    environment variables.
    """
    settings = LLMSettings.from_environment_for_invocation()
    model_kwargs = {
        "model": settings.model,
        "api_key": settings.api_key,
        "temperature": settings.temperature,
    }
    if settings.llm_url is not None:
        model_kwargs["base_url"] = settings.llm_url

    return ChatOpenAI(**model_kwargs)
