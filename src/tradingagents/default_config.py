import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional

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
    # TICKET-078: Target capital deployment configuration
    "target_deployment_pct": 0.50,  # Default: 50% deployed, 50% cash
    # =========================================================================
    # v2: Three-Process Architecture (TICKET-105 through TICKET-113)
    # =========================================================================
    # --- Discovery Pipeline ---
    "discovery": {
        "screener_source": "finviz",  # finviz | yfinance | composite
        "max_raw_candidates": 100,
        "max_debate_candidates": 15,
        "min_market_cap": 500_000_000,  # $500M
        "min_price": 5.00,
        "min_volume_ratio": 2.0,  # vs 20-day average
        "lookback_days": 7,  # don't re-debate within N days
        "run_hour": 9,
        "run_minute": 0,
        "timezone": "US/Eastern",
    },
    # --- Portfolio Review ---
    "review": {
        "window_days": 10,  # spread all reviews over N trading days
        "core_interval_days": 14,  # CORE reviewed every 2 weeks
        "tactical_interval_days": 7,  # TACTICAL reviewed weekly
        "weakening_recheck_days": 3,  # weakening thesis rechecked in 3 days
        "max_reviews_per_day": 4,  # cap daily reviews
        "escalation_threshold": 2,  # consecutive weakening before full debate
        "run_hour": 8,
        "run_minute": 0,
        "timezone": "US/Eastern",
    },
    # --- News Reaction ---
    "news_reaction": {
        "poll_interval_seconds": 300,  # 5 min during market hours
        "off_hours_interval_seconds": 900,  # 15 min outside hours
        "conviction_threshold": 8,  # minimum to execute a trade
        "dedup_window_hours": 24,
        "sources": {
            "reuters": True,
            "finnhub": True,
            "reddit": True,
        },
    },
    # --- Position Categories ---
    "categories": {
        "CORE": {
            "hold_months": (6, 12),
            "base_multiplier": 2.0,
            "size_limits": {"min": 0.5, "max": 2.0},
            "review_interval_days": 14,
            "debate_rounds": 2,
        },
        "TACTICAL": {
            "hold_months": (1, 3),
            "base_multiplier": 1.0,
            "size_limits": {"min": 0.25, "max": 1.5},
            "review_interval_days": 7,
            "debate_rounds": 1,
        },
    },
    # --- Redis ---
    "redis": {
        "url": "redis://localhost:6379/0",  # overridden by REDIS_URL env var
        "key_prefix": "trdagnt:",
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


def get_dynamic_max_positions(cash_ratio: float, target_deployment_pct: float | None = None) -> int:
    """Return max positions based on cash deployment level.

    Args:
        cash_ratio: Percentage of portfolio in cash (0.0-1.0)
        target_deployment_pct: Optional target deployment percentage (0.0-1.0).
            If provided, thresholds are computed relative to target.
            If None, falls back to legacy behavior.

    Returns:
        int: Maximum number of positions to hold
    """
    if target_deployment_pct is not None:
        # New parametric behavior: thresholds relative to target
        target_cash = 1.0 - target_deployment_pct
        
        if cash_ratio > target_cash + 0.10:
            return 28  # Deploy aggressively when cash is 10%+ above target
        elif cash_ratio > target_cash:
            return 25  # Moderate deployment when above target
        else:
            return 20  # Conservative when at or below target
    
    # Legacy behavior: hardcoded thresholds
    if cash_ratio > 0.80:
        return 28  # Deploy aggressively when cash is high
    elif cash_ratio > 0.50:
        return 25  # Moderate deployment
    else:
        return 20  # Conservative when fully invested


# TICKET-070: Position size boost when cash is high
def get_position_size_boost(cash_ratio: float, target_deployment_pct: float | None = None) -> float:
    """Return position size multiplier based on cash deployment.

    When cash is high, boost position sizes to deploy capital faster.

    Args:
        cash_ratio: Percentage of portfolio in cash (0.0-1.0)
        target_deployment_pct: Optional target deployment percentage (0.0-1.0).
            If provided, thresholds are computed relative to target.
            If None, falls back to legacy behavior.

    Returns:
        Multiplier to apply to position size (1.0 = no boost)
    """
    if target_deployment_pct is not None:
        # New parametric behavior: thresholds relative to target
        target_cash = 1.0 - target_deployment_pct
        
        if cash_ratio > target_cash + 0.15:
            return 1.50  # 50% larger positions when 15%+ above target
        elif cash_ratio > target_cash + 0.10:
            return 1.25  # 25% larger positions when 10%+ above target
        elif cash_ratio > target_cash + 0.05:
            return 1.10  # 10% larger positions when 5%+ above target
        return 1.0
    
    # Legacy behavior: hardcoded thresholds
    if cash_ratio > 0.85:
        return 1.50  # 50% larger positions
    elif cash_ratio > 0.80:
        return 1.25  # 25% larger positions
    elif cash_ratio > 0.70:
        return 1.10  # 10% larger positions
    return 1.0


def get_aggressive_deployment_threshold(target_deployment_pct: float | None = None) -> float:
    """Get the cash ratio threshold for triggering aggressive deployment.
    
    Args:
        target_deployment_pct: Optional target deployment percentage.
            If None, loads from deployment config.
            
    Returns:
        float: Cash ratio above which aggressive deployment kicks in
    """
    if target_deployment_pct is None:
        # Try to load from deployment config
        try:
            from .deployment_config import get_target_deployment_pct
            target_deployment_pct = get_target_deployment_pct()
        except ImportError:
            # Fallback to legacy threshold
            return 0.80
    
    return 1.0 - target_deployment_pct
