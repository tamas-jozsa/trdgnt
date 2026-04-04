"""
Pydantic v2 response models for all dashboard API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Portfolio
# ============================================================================

class AccountSummary(BaseModel):
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    cash_ratio: float = 0.0
    day_pnl: float = 0.0
    day_pnl_pct: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0


class Position(BaseModel):
    ticker: str
    sector: str = ""
    tier: str = "TACTICAL"
    qty: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    agent_stop: Optional[float] = None
    agent_target: Optional[float] = None
    entry_date: Optional[str] = None


class EnforcementStatus(BaseModel):
    bypasses_today: int = 0
    overrides_reverted_today: int = 0
    quota_force_buys_today: int = 0
    stop_losses_today: int = 0


class PortfolioResponse(BaseModel):
    updated_at: str = ""
    account: AccountSummary = Field(default_factory=AccountSummary)
    positions: list[Position] = Field(default_factory=list)
    sector_exposure: dict[str, float] = Field(default_factory=dict)
    enforcement: EnforcementStatus = Field(default_factory=EnforcementStatus)


class EquityPoint(BaseModel):
    date: str
    equity: float
    cash: float
    invested: float


class EquityHistoryResponse(BaseModel):
    data: list[EquityPoint] = Field(default_factory=list)


# ============================================================================
# Trades
# ============================================================================

class TradeEntry(BaseModel):
    date: str
    time: str = ""
    ticker: str
    tier: str = ""
    decision: str
    conviction: int = 0
    size_multiplier: float = 1.0
    amount_usd: float = 0.0
    qty: float = 0.0
    price: float = 0.0
    agent_stop: Optional[float] = None
    agent_target: Optional[float] = None
    order_id: str = ""
    status: str = ""
    source: str = "normal"
    error: Optional[str] = None


class TradeListResponse(BaseModel):
    total: int = 0
    trades: list[TradeEntry] = Field(default_factory=list)


class TickerPerformance(BaseModel):
    ticker: str
    trades: int = 0
    pnl: float = 0.0
    win_rate: float = 0.0


class TierPerformance(BaseModel):
    tier: str
    trades: int = 0
    pnl: float = 0.0
    win_rate: float = 0.0


class PerformanceResponse(BaseModel):
    period_days: int = 30
    total_trades: int = 0
    buys: int = 0
    sells: int = 0
    holds: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    total_pnl: float = 0.0
    by_ticker: list[TickerPerformance] = Field(default_factory=list)
    by_tier: list[TierPerformance] = Field(default_factory=list)


# ============================================================================
# Agents
# ============================================================================

class ReportListEntry(BaseModel):
    ticker: str
    date: str
    decision: str = ""
    conviction: int = 0


class AgentReportResponse(BaseModel):
    ticker: str
    date: str
    decision: str = ""
    conviction: int = 0
    report_markdown: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    bypass: Optional[dict] = None
    override: Optional[dict] = None


class ReportListResponse(BaseModel):
    reports: list[ReportListEntry] = Field(default_factory=list)


class SignalOverride(BaseModel):
    timestamp: str
    ticker: str
    upstream_signal: str
    upstream_conviction: int = 0
    final_signal: str
    final_conviction: int = 0
    cash_ratio: float = 0.0
    severity: str = ""
    reverted: bool = False
    reason: str = ""
    research_signal: Optional[str] = None


class OverrideListResponse(BaseModel):
    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    overrides: list[SignalOverride] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    situation: str = ""
    recommendation: str = ""


class AgentMemoryResponse(BaseModel):
    ticker: str
    agents: dict[str, dict] = Field(default_factory=dict)


# ============================================================================
# Research
# ============================================================================

class ResearchSignal(BaseModel):
    ticker: str
    decision: str
    conviction: str
    reason: str = ""
    tier: str = ""


class ResearchFindingsResponse(BaseModel):
    date: str
    markdown: str = ""
    sentiment: str = ""
    vix: float = 0.0
    vix_trend: str = ""
    signals: list[ResearchSignal] = Field(default_factory=list)
    sector_signals: dict[str, str] = Field(default_factory=dict)
    new_picks: list[str] = Field(default_factory=list)
    available_dates: list[str] = Field(default_factory=list)


class WatchlistEntry(BaseModel):
    ticker: str
    sector: str = ""
    tier: str = ""
    note: str = ""
    source: str = "static"  # "static" or "dynamic"
    added_on: Optional[str] = None


class WatchlistResponse(BaseModel):
    static_count: int = 0
    effective_count: int = 0
    tickers: list[WatchlistEntry] = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)


class QuotaEvent(BaseModel):
    timestamp: str
    cash_ratio: float = 0.0
    high_conviction_signals: int = 0
    buys_executed: int = 0
    quota_met: bool = True
    missed_opportunities: list[str] = Field(default_factory=list)
    force_buy_tickers: list[str] = Field(default_factory=list)


class QuotaResponse(BaseModel):
    total_misses: int = 0
    recent: list[QuotaEvent] = Field(default_factory=list)


# ============================================================================
# Control
# ============================================================================

class SystemStatus(BaseModel):
    agent_running: bool = False
    agent_pid: Optional[int] = None
    last_cycle: Optional[str] = None
    next_cycle: Optional[str] = None
    cycle_in_progress: bool = False
    tickers: int = 0
    cash_ratio: float = 0.0
    open_positions: int = 0
    today_trades: dict[str, int] = Field(default_factory=dict)
    today_research_done: bool = False


class RunRequest(BaseModel):
    mode: str = "normal"  # "normal", "single", "dry_run"
    tickers: Optional[list[str]] = None
    dry_run: bool = False


class RunResponse(BaseModel):
    status: str
    pid: Optional[int] = None
    mode: str = "normal"
    tickers: int = 0


class WatchlistAction(BaseModel):
    action: str  # "add" or "remove"
    ticker: str
    tier: str = "TACTICAL"
    sector: str = ""
    note: str = ""
