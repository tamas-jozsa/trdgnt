// API client for the dashboard backend

const BASE = '';  // Vite proxy handles /api -> backend

export async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export async function postApi<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

// Typed API functions
import type {
  PortfolioResponse, EquityPoint, TradeEntry, PerformanceResponse,
  ReportListEntry, AgentReport, SignalOverride, ResearchFindings,
  WatchlistEntry, SystemStatus, NewsMonitorStatus, NewsEvent, TriggerItem, QueueItem,
  DeploymentConfig, PollIntervalResponse,
} from '../types';

export const api = {
  // Portfolio
  getPortfolio: () => fetchApi<PortfolioResponse>('/api/portfolio'),
  getEquityHistory: (days = 30) => fetchApi<{ data: EquityPoint[] }>(`/api/portfolio/equity-history?days=${days}`),

  // Trades
  getTrades: (params?: { limit?: number; ticker?: string; action?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.ticker) qs.set('ticker', params.ticker);
    if (params?.action) qs.set('action', params.action);
    return fetchApi<{ total: number; trades: TradeEntry[] }>(`/api/trades?${qs}`);
  },
  getPerformance: (days = 30) => fetchApi<PerformanceResponse>(`/api/trades/performance?days=${days}`),

  // Agents
  getReports: (params?: { ticker?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.ticker) qs.set('ticker', params.ticker);
    if (params?.limit) qs.set('limit', String(params.limit));
    return fetchApi<{ reports: ReportListEntry[] }>(`/api/agents/reports?${qs}`);
  },
  getReport: (ticker: string, date: string) => fetchApi<AgentReport>(`/api/agents/report/${ticker}/${date}`),
  getOverrides: (days = 7) => fetchApi<{ total: number; by_severity: Record<string, number>; overrides: SignalOverride[] }>(`/api/agents/overrides?days=${days}`),
  getMemory: (ticker: string) => fetchApi<{ ticker: string; agents: Record<string, { count: number; latest: unknown[] }> }>(`/api/agents/memory/${ticker}`),

  // Research
  getFindings: (date?: string) => fetchApi<ResearchFindings>(`/api/research/findings${date ? `?date=${date}` : ''}`),
  getWatchlist: () => fetchApi<{ static_count: number; effective_count: number; tickers: WatchlistEntry[] }>('/api/research/watchlist'),
  getQuota: () => fetchApi<{ total_misses: number; recent: unknown[] }>('/api/research/quota'),

  // Control
  getStatus: () => fetchApi<SystemStatus>('/api/control/status'),
  runCycle: (dryRun = false) => postApi<{ status: string; pid: number }>('/api/control/run', { mode: dryRun ? 'dry_run' : 'normal', dry_run: dryRun }),
  runResearch: () => postApi<{ status: string }>('/api/control/research'),
  syncPositions: () => postApi<{ status: string; positions: number }>('/api/control/sync-positions'),
  modifyWatchlist: (action: 'add' | 'remove', ticker: string, tier = 'TACTICAL', sector = '', note = '') =>
    postApi('/api/control/watchlist', { action, ticker, tier, sector, note }),

  // News Monitor
  getNewsMonitorStatus: () => fetchApi<NewsMonitorStatus>('/api/news-monitor/status'),
  startNewsMonitor: () => postApi<{ status: string; enabled: boolean }>('/api/news-monitor/start'),
  stopNewsMonitor: () => postApi<{ status: string; enabled: boolean }>('/api/news-monitor/stop'),
  getNewsFeed: (limit = 50) => fetchApi<{ events: NewsEvent[]; total: number }>(`/api/news-monitor/feed?limit=${limit}`),
  getTriggers: (limit = 50) => fetchApi<{ triggers: TriggerItem[]; active: TriggerItem[]; total: number }>(`/api/news-monitor/triggers?limit=${limit}`),
  getQueue: () => fetchApi<{ items: QueueItem[]; count: number }>('/api/news-monitor/queue'),
  drainQueue: () => postApi<{ status: string; processed: number }>('/api/news-monitor/drain'),
  
  // Log files
  getScheduledLogs: (lines = 2000) => fetchApi<{ lines: string[]; count: number }>(`/api/control/logs/scheduled?lines=${lines}`),
  getManualLogs: (lines = 2000) => fetchApi<{ lines: string[]; count: number; file: string | null }>(`/api/control/logs/manual?lines=${lines}`),

  // TICKET-078: Deployment config
  getDeploymentConfig: () => fetchApi<DeploymentConfig>('/api/control/deployment-config'),
  setDeploymentConfig: (target_deployment_pct: number) =>
    postApi<DeploymentConfig>('/api/control/deployment-config', { target_deployment_pct }),

  // TICKET-079: News Monitor poll interval
  getPollInterval: () => fetchApi<PollIntervalResponse>('/api/news-monitor/poll-interval'),
  setPollInterval: (interval_seconds: number) =>
    postApi<PollIntervalResponse>('/api/news-monitor/poll-interval', { interval_seconds }),
};
