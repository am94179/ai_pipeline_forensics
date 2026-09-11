"""Credential-free model doubles for Phase 3 workflow tests."""

from __future__ import annotations


class FakeStructuredModel:
    """Capture one prompt and return a configured response or error."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> object:
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeChatModel:
    """Minimal stand-in for LangChain's structured-output model interface."""

    def __init__(self, structured_model: FakeStructuredModel) -> None:
        self.structured_model = structured_model
        self.output_schema: object | None = None

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        self.output_schema = schema
        return self.structured_model
