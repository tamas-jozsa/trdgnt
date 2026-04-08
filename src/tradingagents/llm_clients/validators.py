"""Model name validators for each provider.

Only validates model names - does NOT enforce limits.
Let LLM providers use their own defaults for unspecified params.
"""

VALID_MODELS = {
    "openai": [
        # GPT-4o series (current production defaults)
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4o-realtime-preview",
        "gpt-4o-audio-preview",
        # GPT-4.1 series
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        # Reasoning models
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o4-mini",
        # GPT-5 series (forward-compat)
        "gpt-5",
        "gpt-5-mini",
    ],
    "anthropic": [
        # Claude 4.6 series (latest)
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        # Claude 4.5 series
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    ],
    "google": [
        # Gemini 3.1 series (preview)
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite-preview",
        # Gemini 3 series (preview)
        "gemini-3-flash-preview",
        # Gemini 2.5 series
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ],
    "xai": [
        # Grok 4.1 series
        "grok-4-1-fast-reasoning",
        "grok-4-1-fast-non-reasoning",
        # Grok 4 series
        "grok-4-0709",
        "grok-4-fast-reasoning",
        "grok-4-fast-non-reasoning",
    ],
}


def validate_model(provider: str, model: str) -> bool:
    """Check if model name is valid for the given provider.

    For ollama, openrouter - any model is accepted.
    """
    provider_lower = provider.lower()

    if provider_lower in ("ollama", "openrouter"):
        return True

    if provider_lower not in VALID_MODELS:
        return True

    return model in VALID_MODELS[provider_lower]
