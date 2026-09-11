import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED_PROVIDERS = frozenset({"openai"})


class LLMConfigurationError(ValueError):
    """Raised when the selected LLM cannot be configured safely."""





@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str = field(repr=False)
    llm_url: str | None
    temperature: float = 0.0

    @classmethod
    def from_environment_for_invocation(
        cls, dotenv_path: str | Path | None = None
    ) -> "LLMSettings":
        load_dotenv(dotenv_path=dotenv_path or PROJECT_ROOT / ".env", override=False)
        values = {
            "LLM_API_KEY": os.getenv("LLM_API_KEY", "").strip(),
            "LLM_MODEL": os.getenv("LLM_MODEL", "").strip(),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "").strip(),
        }
        llm_url = os.getenv("LLM_URL", "").strip() or None
        temperature_value = os.getenv("LLM_TEMPERATURE", "0.0").strip() or "0.0"
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise LLMConfigurationError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        provider = values["LLM_PROVIDER"].lower()
        if provider not in SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
            raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {provider}. Supported: {supported}.")
        try:
            temperature = float(temperature_value)
        except ValueError as error:
            raise LLMConfigurationError("LLM_TEMPERATURE must be a number.") from error
        return cls(
            provider=provider,
            model=values["LLM_MODEL"],
            api_key=values["LLM_API_KEY"],
            llm_url=llm_url,
            temperature=temperature,
        )
