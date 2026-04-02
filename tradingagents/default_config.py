import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    # Debate and discussion settings
    "max_debate_rounds": 2,
    "max_risk_discuss_rounds": 2,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # TICKET-063: Portfolio position limits with dynamic adjustment
    "max_positions": 28,  # Maximum positions (full watchlist coverage)
    "max_positions_conservative": 20,  # Conservative limit when fully invested
    "capital_deployment_cash_threshold": 0.80,  # 80% cash triggers aggressive deployment
    # TICKET-058: Tier-based position sizing limits
    "tier_position_limits": {
        "CORE": {"min": 0.5, "max": 2.0, "description": "High conviction, macro-aligned"},
        "TACTICAL": {"min": 0.25, "max": 1.5, "description": "Momentum/catalyst-driven"},
        "SPECULATIVE": {"min": 0.1, "max": 0.75, "description": "Squeeze/biotech/meme, max 2-3% portfolio"},
        "HEDGE": {"min": 0.25, "max": 1.0, "description": "Geopolitical/volatility buffer"},
    },
    # TICKET-062: Time-based exit rules
    "exit_rules": {
        "profit_taking_50": {
            "enabled": True,
            "trigger": "position_pnl_pct >= target_profit_pct * 0.5",
            "action": "sell_half_position",
            "description": "Take profits on half position at 50% of target",
        },
        "time_stop": {
            "enabled": True,
            "days_held": 30,
            "action": "force_re_evaluation",
            "description": "Force full re-analysis after 30 days",
        },
        "trailing_stop": {
            "enabled": True,
            "activation_profit_pct": 10,
            "trailing_pct": 15,
            "description": "Protect profits with trailing stop once +10%",
        },
    },
}


def get_tier_position_limits(tier: str) -> dict:
    """Get min/max position multipliers for a tier.

    Args:
        tier: Tier name (CORE, TACTICAL, SPECULATIVE, HEDGE)

    Returns:
        dict with min, max, description
    """
    limits = DEFAULT_CONFIG.get("tier_position_limits", {})
    return limits.get(tier.upper(), limits.get("CORE", {"min": 0.25, "max": 2.0}))


def get_dynamic_max_positions(cash_ratio: float) -> int:
    """Return max positions based on cash deployment level.

    Args:
        cash_ratio: Percentage of portfolio in cash (0.0-1.0)

    Returns:
        int: Maximum number of positions to hold
    """
    if cash_ratio > 0.80:
        return 28  # Deploy aggressively when cash is high
    elif cash_ratio > 0.50:
        return 25  # Moderate deployment
    else:
        return 20  # Conservative when fully invested


# TICKET-070: Position size boost when cash is high
def get_position_size_boost(cash_ratio: float) -> float:
    """Return position size multiplier based on cash deployment.

    When cash is high, boost position sizes to deploy capital faster.

    Args:
        cash_ratio: Percentage of portfolio in cash (0.0-1.0)

    Returns:
        Multiplier to apply to position size (1.0 = no boost)
    """
    if cash_ratio > 0.85:
        return 1.50  # 50% larger positions
    elif cash_ratio > 0.80:
        return 1.25  # 25% larger positions
    elif cash_ratio > 0.70:
        return 1.10  # 10% larger positions
    return 1.0
