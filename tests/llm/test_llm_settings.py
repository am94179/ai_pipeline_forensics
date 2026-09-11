"""Credential-free tests for lazy LLM configuration validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.config.llm_settings import LLMConfigurationError, LLMSettings


@pytest.fixture(autouse=True)
def clear_llm_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_PROVIDER",
        "LLM_URL",
        "LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_loads_required_settings_with_default_endpoint_and_temperature(tmp_path: Path) -> None:
    dotenv_path = _write_dotenv(
        tmp_path,
        "LLM_API_KEY=test-key\nLLM_PROVIDER=OPENAI\nLLM_MODEL=test-model\n",
    )

    settings = LLMSettings.from_environment_for_invocation(dotenv_path)

    assert settings.provider == "openai"
    assert settings.model == "test-model"
    assert settings.api_key == "test-key"
    assert settings.llm_url is None
    assert settings.temperature == 0.0
    assert "test-key" not in repr(settings)


def test_loads_optional_custom_endpoint_and_temperature(tmp_path: Path) -> None:
    dotenv_path = _write_dotenv(
        tmp_path,
        "\n".join(
            (
                "LLM_API_KEY=test-key",
                "LLM_PROVIDER=openai",
                "LLM_MODEL=test-model",
                "LLM_URL=https://llm.example.test/v1",
                "LLM_TEMPERATURE=0.25",
            )
        ),
    )

    settings = LLMSettings.from_environment_for_invocation(dotenv_path)

    assert settings.llm_url == "https://llm.example.test/v1"
    assert settings.temperature == 0.25


def test_rejects_missing_required_values(tmp_path: Path) -> None:
    dotenv_path = _write_dotenv(tmp_path, "LLM_PROVIDER=openai\nLLM_MODEL=test-model\n")

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        LLMSettings.from_environment_for_invocation(dotenv_path)


def test_rejects_unsupported_provider(tmp_path: Path) -> None:
    dotenv_path = _write_dotenv(
        tmp_path,
        "LLM_API_KEY=test-key\nLLM_PROVIDER=local\nLLM_MODEL=test-model\n",
    )

    with pytest.raises(LLMConfigurationError, match="Unsupported LLM_PROVIDER"):
        LLMSettings.from_environment_for_invocation(dotenv_path)


def test_rejects_non_numeric_temperature(tmp_path: Path) -> None:
    dotenv_path = _write_dotenv(
        tmp_path,
        "LLM_API_KEY=test-key\nLLM_PROVIDER=openai\nLLM_MODEL=test-model\nLLM_TEMPERATURE=warm\n",
    )

    with pytest.raises(LLMConfigurationError, match="LLM_TEMPERATURE must be a number"):
        LLMSettings.from_environment_for_invocation(dotenv_path)


def test_environment_values_override_dotenv_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv_path = _write_dotenv(
        tmp_path,
        "LLM_API_KEY=file-key\nLLM_PROVIDER=openai\nLLM_MODEL=file-model\n",
    )
    monkeypatch.setenv("LLM_API_KEY", "environment-key")

    settings = LLMSettings.from_environment_for_invocation(dotenv_path)

    assert settings.api_key == "environment-key"


def _write_dotenv(tmp_path: Path, content: str) -> Path:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(content, encoding="utf-8")
    return dotenv_path
