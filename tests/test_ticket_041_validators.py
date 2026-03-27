"""
Tests for TICKET-041: validators.py OpenAI model allowlist.

Verifies that the production models (gpt-4o, gpt-4o-mini) and
current reasoning models are valid, and that fake model names are rejected.
"""

import pytest


class TestValidateModel:

    def test_gpt4o_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "gpt-4o") is True

    def test_gpt4o_mini_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "gpt-4o-mini") is True

    def test_o1_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "o1") is True

    def test_o3_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "o3") is True

    def test_o4_mini_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "o4-mini") is True

    def test_gpt41_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "gpt-4.1") is True

    def test_gpt41_mini_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "gpt-4.1-mini") is True

    def test_fake_model_is_invalid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openai", "definitely-not-real-model-xyz") is False

    def test_ollama_accepts_any_model(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("ollama", "llama3:latest") is True
        assert validate_model("ollama", "any-arbitrary-name") is True

    def test_openrouter_accepts_any_model(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("openrouter", "openai/gpt-4o") is True

    def test_unknown_provider_accepts_any_model(self):
        """Providers not in VALID_MODELS should pass through."""
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("unknown_provider", "some-model") is True

    def test_anthropic_claude_sonnet_is_valid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("anthropic", "claude-sonnet-4-6") is True

    def test_anthropic_fake_model_is_invalid(self):
        from tradingagents.llm_clients.validators import validate_model
        assert validate_model("anthropic", "claude-fake-999") is False
