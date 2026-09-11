"""Tests for lazy OpenAI-compatible model construction."""

from __future__ import annotations

import pytest

from investigator.config.llm_settings import LLMSettings
from investigator.llm import provider


class CapturingChatModel:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


@pytest.mark.parametrize(
    ("llm_url", "expected_base_url"),
    ((None, None), ("https://llm.example.test/v1", "https://llm.example.test/v1")),
)
def test_build_chat_model_uses_validated_settings(
    monkeypatch: pytest.MonkeyPatch,
    llm_url: str | None,
    expected_base_url: str | None,
) -> None:
    settings = LLMSettings(
        provider="openai",
        model="test-model",
        api_key="test-key",
        llm_url=llm_url,
        temperature=0.25,
    )
    monkeypatch.setattr(
        provider.LLMSettings,
        "from_environment_for_invocation",
        lambda: settings,
    )
    monkeypatch.setattr(provider, "ChatOpenAI", CapturingChatModel)

    model = provider.build_chat_model()

    assert isinstance(model, CapturingChatModel)
    assert model.kwargs["model"] == "test-model"
    assert model.kwargs["api_key"] == "test-key"
    assert model.kwargs["temperature"] == 0.25
    if expected_base_url is None:
        assert "base_url" not in model.kwargs
    else:
        assert model.kwargs["base_url"] == expected_base_url
