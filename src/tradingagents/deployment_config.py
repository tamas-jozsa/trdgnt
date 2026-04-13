"""
Deployment configuration management for target capital deployment percentage.

This module provides a single "knob" to control how aggressively the trading
system deploys cash into the market. Instead of hardcoded thresholds,
all capital deployment mechanisms scale parametrically based on the target.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Default target: 50% deployed (50% cash) - conservative middle ground
DEFAULT_TARGET_DEPLOYMENT_PCT = 0.50

# Valid range for target deployment
MIN_TARGET_DEPLOYMENT_PCT = 0.10
MAX_TARGET_DEPLOYMENT_PCT = 0.95

# Config file path (relative to project root)
CONFIG_FILENAME = "trading_loop_logs/deployment_config.json"


def _get_config_path() -> Path:
    """Get the absolute path to the deployment config file."""
    # Find project root by looking for the config file location
    # Default to current working directory if not found
    cwd = Path.cwd()
    
    # Try to find the trading_loop_logs directory
    potential_paths = [
        cwd / CONFIG_FILENAME,
        cwd / ".." / CONFIG_FILENAME,
        cwd / ".." / ".." / CONFIG_FILENAME,
    ]
    
    for path in potential_paths:
        resolved = path.resolve()
        if resolved.parent.exists() or resolved.parent.parent.exists():
            return resolved
    
    # Fallback: create in current working directory
    return (cwd / CONFIG_FILENAME).resolve()


def load_deployment_config() -> dict[str, Any]:
    """
    Load the deployment configuration from disk.
    
    Returns:
        dict with at least 'target_deployment_pct' and 'updated_at' keys.
        Returns defaults if file doesn't exist or is corrupted.
    """
    config_path = _get_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Validate and clamp target value
            target = config.get("target_deployment_pct", DEFAULT_TARGET_DEPLOYMENT_PCT)
            target = max(MIN_TARGET_DEPLOYMENT_PCT, min(MAX_TARGET_DEPLOYMENT_PCT, target))
            config["target_deployment_pct"] = target
            
            return config
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Fall through to default
    
    # Return default config
    return {
        "target_deployment_pct": DEFAULT_TARGET_DEPLOYMENT_PCT,
        "updated_at": datetime.now().isoformat(),
    }


def save_deployment_config(target_deployment_pct: float) -> dict[str, Any]:
    """
    Save a new target deployment percentage to disk.
    
    Args:
        target_deployment_pct: Desired percentage of portfolio to deploy (0.10-0.95)
        
    Returns:
        The saved config dict
    """
    config_path = _get_config_path()
    
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Validate and clamp
    target = max(MIN_TARGET_DEPLOYMENT_PCT, min(MAX_TARGET_DEPLOYMENT_PCT, target_deployment_pct))
    
    config = {
        "target_deployment_pct": target,
        "updated_at": datetime.now().isoformat(),
    }
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    return config


def get_target_deployment_pct() -> float:
    """
    Get the current target deployment percentage.
    
    Returns:
        float between 0.10 and 0.95 (10% to 95%)
    """
    return load_deployment_config().get("target_deployment_pct", DEFAULT_TARGET_DEPLOYMENT_PCT)


def get_effective_thresholds(target_pct: float | None = None) -> dict[str, float]:
    """
    Compute effective thresholds for all capital deployment mechanisms.
    
    Given a target deployment percentage, this computes the cash ratio
    thresholds that trigger various aggressive deployment behaviors.
    
    Args:
        target_pct: Target deployment percentage (0.0-1.0). If None, loads from config.
        
    Returns:
        dict with threshold names and their effective cash ratio values
    """
    if target_pct is None:
        target_pct = get_target_deployment_pct()
    
    # Target cash ratio = 1 - target deployment
    target_cash = 1.0 - target_pct
    
    return {
        # When we start considering aggressive deployment
        "aggressive_threshold": target_cash,
        
        # Position size boost thresholds (relative to target)
        "boost_10": target_cash + 0.05,    # 10% boost when cash is 5% above target
        "boost_25": target_cash + 0.10,    # 25% boost when cash is 10% above target  
        "boost_50": target_cash + 0.15,    # 50% boost when cash is 15% above target
        
        # Conviction bypass extra-aggressive threshold
        "conviction_bypass": target_cash + 0.20,  # Extra boost at 20% above target
        
        # Max positions thresholds
        "max_positions_aggressive": target_cash + 0.10,  # 28 positions
        "max_positions_moderate": target_cash + 0.05,    # 25 positions
        "max_positions_conservative": target_cash,        # 20 positions
    }


def format_deployment_status(current_cash_ratio: float, target_pct: float | None = None) -> dict[str, Any]:
    """
    Format a human-readable status of current vs target deployment.
    
    Args:
        current_cash_ratio: Current percentage of portfolio in cash (0.0-1.0)
        target_pct: Target deployment percentage. If None, loads from config.
        
    Returns:
        dict with formatted status information
    """
    if target_pct is None:
        target_pct = get_target_deployment_pct()
    
    target_cash = 1.0 - target_pct
    gap = current_cash_ratio - target_cash  # Positive = under-deployed
    
    if gap > 0.15:
        status = "significantly_under_deployed"
        message = f"{gap*100:.1f}% below target - aggressive deployment recommended"
    elif gap > 0.05:
        status = "under_deployed"
        message = f"{gap*100:.1f}% below target - moderate deployment"
    elif gap > -0.05:
        status = "on_target"
        message = "Within target range"
    else:
        status = "over_deployed"
        message = f"{abs(gap)*100:.1f}% above target - holding pattern"
    
    return {
        "current_cash_ratio": current_cash_ratio,
        "current_deployment_pct": 1.0 - current_cash_ratio,
        "target_deployment_pct": target_pct,
        "target_cash_ratio": target_cash,
        "gap": gap,
        "status": status,
        "message": message,
        "thresholds": get_effective_thresholds(target_pct),
    }
