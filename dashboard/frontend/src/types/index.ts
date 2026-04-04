// Types matching backend Pydantic schemas

export interface AccountSummary {
  equity: number;
  cash: number;
  buying_power: number;
  cash_ratio: number;
  day_pnl: number;
  day_pnl_pct: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface Position {
  ticker: string;
  sector: string;
  tier: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_pl_pct: number;
  agent_stop: number | null;
  agent_target: number | null;
  entry_date: string | null;
}

export interface EnforcementStatus {
  bypasses_today: number;
  overrides_reverted_today: number;
  quota_force_buys_today: number;
  stop_losses_today: number;
}

export interface PortfolioResponse {
  updated_at: string;
  account: AccountSummary;
  positions: Position[];
  sector_exposure: Record<string, number>;
  enforcement: EnforcementStatus;
}

export interface EquityPoint {
  date: string;
  equity: number;
  cash: number;
  invested: number;
}

export interface TradeEntry {
  date: string;
  time: string;
  ticker: string;
  tier: string;
  decision: string;
  conviction: number;
  size_multiplier: number;
  amount_usd: number;
  qty: number;
  price: number;
  agent_stop: number | null;
  agent_target: number | null;
  order_id: string;
  status: string;
  source: string;
  error: string | null;
}

export interface TickerPerformance {
  ticker: string;
  trades: number;
  pnl: number;
  win_rate: number;
}

export interface PerformanceResponse {
  period_days: number;
  total_trades: number;
  buys: number;
  sells: number;
  holds: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  best_trade: TickerPerformance | null;
  worst_trade: TickerPerformance | null;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_pnl: number;
  by_ticker: TickerPerformance[];
  by_tier: { tier: string; trades: number; pnl: number; win_rate: number }[];
}

export interface ReportListEntry {
  ticker: string;
  date: string;
  decision: string;
  conviction: number;
}

export interface AgentReport {
  ticker: string;
  date: string;
  decision: string;
  conviction: number;
  report_markdown: string;
  sections: Record<string, string>;
  bypass: Record<string, unknown> | null;
  override: Record<string, unknown> | null;
}

export interface SignalOverride {
  timestamp: string;
  ticker: string;
  upstream_signal: string;
  upstream_conviction: number;
  final_signal: string;
  final_conviction: number;
  cash_ratio: number;
  severity: string;
  reverted: boolean;
  reason: string;
}

export interface ResearchFindings {
  date: string;
  markdown: string;
  sentiment: string;
  vix: number;
  vix_trend: string;
  signals: { ticker: string; decision: string; conviction: string; reason: string; tier: string }[];
  sector_signals: Record<string, string>;
  new_picks: string[];
  available_dates: string[];
}

export interface WatchlistEntry {
  ticker: string;
  sector: string;
  tier: string;
  note: string;
  source: string;
  added_on: string | null;
}

export interface SystemStatus {
  agent_running: boolean;
  agent_pid: number | null;
  last_cycle: string | null;
  next_cycle: string | null;
  cycle_in_progress: boolean;
  tickers: number;
  cash_ratio: number;
  open_positions: number;
  today_trades: Record<string, number>;
  today_research_done: boolean;
}

export interface LiveMessage {
  type: string;
  text?: string;
  ticker?: string;
  decision?: string;
  action?: string;
}
