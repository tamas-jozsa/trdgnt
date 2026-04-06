import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import { Link } from 'react-router-dom';
import {
  Power, Zap, Clock, TrendingUp, TrendingDown, Minus,
  CheckCircle, Circle, Play, Newspaper, X
} from 'lucide-react';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

function UrgencyBadge({ urgency }: { urgency: 'HIGH' | 'MEDIUM' | 'LOW' }) {
  const colors = {
    HIGH: 'bg-red-500/20 text-red-400 border-red-500/30',
    MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    LOW: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${colors[urgency]}`}>
      {urgency}
    </span>
  );
}

function SentimentBadge({ sentiment }: { sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL' }) {
  const icons = {
    BULLISH: <TrendingUp size={12} className="text-[var(--profit)]" />,
    BEARISH: <TrendingDown size={12} className="text-[var(--loss)]" />,
    NEUTRAL: <Minus size={12} className="text-[var(--text-secondary)]" />,
  };
  const colors = {
    BULLISH: 'text-[var(--profit)]',
    BEARISH: 'text-[var(--loss)]',
    NEUTRAL: 'text-[var(--text-secondary)]',
  };
  return (
    <span className={`flex items-center gap-1 text-xs ${colors[sentiment]}`}>
      {icons[sentiment]}
      {sentiment}
    </span>
  );
}

function StatusBadge({ enabled, polling }: { enabled: boolean; polling: boolean }) {
  if (!enabled) {
    return (
      <span className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
        <Circle size={8} className="fill-gray-500" />
        Disabled
      </span>
    );
  }
  if (polling) {
    return (
      <span className="flex items-center gap-1.5 text-sm text-[var(--profit)]">
        <Circle size={8} className="fill-[var(--profit)] animate-pulse" />
        Active
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-sm text-[var(--hold)]">
      <Circle size={8} className="fill-[var(--hold)]" />
      Paused
    </span>
  );
}

function MarketStateBadge({ state }: { state: 'open' | 'extended' | 'closed' }) {
  const colors = {
    open: 'bg-[var(--profit)]/20 text-[var(--profit)]',
    extended: 'bg-[var(--hold)]/20 text-[var(--hold)]',
    closed: 'bg-[var(--loss)]/20 text-[var(--loss)]',
  };
  const labels = {
    open: 'Market Open',
    extended: 'Extended Hours',
    closed: 'Market Closed',
  };
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[state]}`}>
      {labels[state]}
    </span>
  );
}

export default function NewsMonitor() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState('');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  // Status polling
  const { data: status } = useQuery({
    queryKey: ['news-monitor-status'],
    queryFn: api.getNewsMonitorStatus,
    refetchInterval: 10000,
  });

  // News feed
  const { data: feed } = useQuery({
    queryKey: ['news-feed'],
    queryFn: () => api.getNewsFeed(30),
    refetchInterval: 10000,
  });

  // Triggers
  const { data: triggers } = useQuery({
    queryKey: ['news-triggers'],
    queryFn: () => api.getTriggers(20),
    refetchInterval: 15000,
  });

  // Queue
  const { data: queue } = useQuery({
    queryKey: ['news-queue'],
    queryFn: api.getQueue,
    refetchInterval: 15000,
  });

  // Mutations
  const startMutation = useMutation({
    mutationFn: api.startNewsMonitor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-monitor-status'] });
      showToast('News monitor started');
    },
    onError: (e) => showToast(`Error: ${e.message}`),
  });

  const stopMutation = useMutation({
    mutationFn: api.stopNewsMonitor,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-monitor-status'] });
      showToast('News monitor stopped');
    },
    onError: (e) => showToast(`Error: ${e.message}`),
  });

  const drainMutation = useMutation({
    mutationFn: api.drainQueue,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['news-queue'] });
      showToast(`Drained ${data.processed} queued items`);
    },
    onError: (e) => showToast(`Error: ${e.message}`),
  });

  const isEnabled = status?.enabled ?? false;
  const highUrgencyCount = feed?.events.filter(e => e.urgency === 'HIGH').length ?? 0;

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 bg-[var(--accent)] text-white px-4 py-2 rounded-lg text-sm shadow-lg z-50">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Newspaper size={24} className="text-[var(--accent)]" />
            News Monitor
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Real-time news analysis & trading triggers
          </p>
        </div>
        <div className="flex items-center gap-4">
          <StatusBadge enabled={status?.enabled ?? false} polling={status?.polling ?? false} />
          <MarketStateBadge state={status?.market_state ?? 'closed'} />
        </div>
      </div>

      {/* Top Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Card */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Status</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Last poll</span>
              <span className="text-sm mono">
                {status?.last_poll_at
                  ? new Date(status.last_poll_at).toLocaleTimeString()
                  : 'Never'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Articles today</span>
              <span className="text-sm mono">{status?.articles_today ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">New articles</span>
              <span className="text-sm mono">{status?.new_articles_today ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Triggers today</span>
              <span className="text-sm mono text-[var(--accent)]">{status?.triggers_today ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Active analyses</span>
              <span className="text-sm mono">{status?.active_analyses ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Queued</span>
              <span className="text-sm mono">{status?.queued_triggers ?? 0}</span>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <span className="text-sm text-[var(--text-secondary)]">Cost today</span>
              <span className="text-sm mono">${(status?.estimated_cost_today_usd ?? 0).toFixed(2)}</span>
            </div>
          </div>
        </Card>

        {/* Controls Card */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Controls</h2>
          <div className="space-y-3">
            <button
              onClick={() => isEnabled ? stopMutation.mutate() : startMutation.mutate()}
              disabled={startMutation.isPending || stopMutation.isPending}
              className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                isEnabled
                  ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                  : 'bg-[var(--profit)]/20 text-[var(--profit)] hover:bg-[var(--profit)]/30'
              }`}
            >
              <Power size={16} />
              {isEnabled ? 'Stop Monitor' : 'Start Monitor'}
            </button>

            {status?.queued_triggers ? (
              <button
                onClick={() => drainMutation.mutate()}
                disabled={drainMutation.isPending}
                className="w-full flex items-center justify-center gap-2 bg-[var(--accent)]/20 text-[var(--accent)] hover:bg-[var(--accent)]/30 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                <Play size={16} />
                Drain Queue ({status.queued_triggers} items)
              </button>
            ) : null}

            <div className="text-xs text-[var(--text-secondary)] pt-2">
              Polls every 5 min from Reuters, Finnhub, Reddit
            </div>
          </div>
        </Card>

        {/* Stats Card */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Today's Activity</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">High urgency events</span>
              <span className="text-sm font-medium text-red-400">{highUrgencyCount}</span>
            </div>
            <div className="h-px bg-[var(--border)]" />
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-[var(--bg)] rounded p-2">
                <div className="text-lg font-bold text-[var(--profit)]">
                  {triggers?.triggers.filter(t => t.status === 'completed').length ?? 0}
                </div>
                <div className="text-xs text-[var(--text-secondary)]">Completed</div>
              </div>
              <div className="bg-[var(--bg)] rounded p-2">
                <div className="text-lg font-bold text-[var(--accent)]">
                  {triggers?.active.length ?? 0}
                </div>
                <div className="text-xs text-[var(--text-secondary)]">Running</div>
              </div>
              <div className="bg-[var(--bg)] rounded p-2">
                <div className="text-lg font-bold text-[var(--loss)]">
                  {triggers?.triggers.filter(t => t.status === 'failed').length ?? 0}
                </div>
                <div className="text-xs text-[var(--text-secondary)]">Failed</div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* News Feed */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Live News Feed</h2>
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <Zap size={12} className="text-[var(--hold)]" />
            Auto-refresh every 10s
          </div>
        </div>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {feed?.events.length === 0 ? (
            <div className="text-center py-8 text-[var(--text-secondary)]">
              No news events yet. Monitor will poll every 5 minutes.
            </div>
          ) : (
            feed?.events.map((event) => (
              <div
                key={event.news_hash}
                className="bg-[var(--bg)] rounded-lg p-4 border border-[var(--border)] hover:border-[var(--accent)]/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <UrgencyBadge urgency={event.urgency} />
                      <span className="text-xs text-[var(--text-secondary)] uppercase tracking-wide">
                        {event.source.replace('reddit_', 'r/')}
                      </span>
                      <span className="text-xs text-[var(--text-secondary)]">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm font-medium">{event.title}</p>
                  </div>
                  <SentimentBadge sentiment={event.sentiment} />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--text-secondary)]">Tickers:</span>
                    <div className="flex gap-1">
                      {event.affected_tickers.map(ticker => (
                        <Link
                          key={ticker}
                          to={`/agents/${ticker}/${new Date().toISOString().split('T')[0]}`}
                          className="px-1.5 py-0.5 bg-[var(--surface)] rounded text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors"
                        >
                          {ticker}
                        </Link>
                      ))}
                    </div>
                  </div>
                  {event.action_recommended ? (
                    <span className="flex items-center gap-1 text-[var(--profit)]">
                      <CheckCircle size={12} />
                      Triggered analysis
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[var(--text-secondary)]">
                      <Minus size={12} />
                      No action
                    </span>
                  )}
                </div>
                {event.reasoning && (
                  <p className="text-xs text-[var(--text-secondary)] mt-2">
                    {event.reasoning}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Bottom Row: Triggers & Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trigger History */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Trigger History</h2>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {triggers?.triggers.length === 0 && triggers?.active.length === 0 ? (
              <div className="text-center py-8 text-[var(--text-secondary)]">
                No triggers yet
              </div>
            ) : (
              <>
                {/* Active first */}
                {triggers?.active.map((trigger) => (
                  <div
                    key={trigger.trigger_id}
                    className="flex items-center justify-between bg-[var(--bg)] rounded-lg p-3 border border-[var(--accent)]/30"
                  >
                    <div className="flex items-center gap-3">
                      <Circle size={10} className="fill-[var(--accent)] animate-pulse" />
                      <div>
                        <div className="flex items-center gap-2">
                          {trigger.tickers.map(t => (
                            <span key={t} className="font-mono text-sm">{t}</span>
                          ))}
                        </div>
                        <div className="text-xs text-[var(--text-secondary)]">
                          PID {trigger.pid} • {new Date(trigger.started_at).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                    <span className="text-xs px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)]">
                      Running
                    </span>
                  </div>
                ))}
                {/* Then completed */}
                {triggers?.triggers.map((trigger) => (
                  <div
                    key={trigger.trigger_id}
                    className="flex items-center justify-between bg-[var(--bg)] rounded-lg p-3"
                  >
                    <div className="flex items-center gap-3">
                      {trigger.status === 'completed' ? (
                        <CheckCircle size={16} className="text-[var(--profit)]" />
                      ) : trigger.status === 'failed' ? (
                        <X size={16} className="text-[var(--loss)]" />
                      ) : (
                        <Clock size={16} className="text-[var(--text-secondary)]" />
                      )}
                      <div>
                        <div className="flex items-center gap-2">
                          {trigger.tickers.map(t => (
                            <span key={t} className="font-mono text-sm">{t}</span>
                          ))}
                        </div>
                        <div className="text-xs text-[var(--text-secondary)] truncate max-w-xs">
                          {trigger.reason}
                        </div>
                      </div>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded ${
                      trigger.status === 'completed'
                        ? 'bg-[var(--profit)]/20 text-[var(--profit)]'
                        : trigger.status === 'failed'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-gray-500/20 text-gray-400'
                    }`}>
                      {trigger.status}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        </Card>

        {/* Queue */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Queue</h2>
            {queue?.count ? (
              <span className="text-xs px-2 py-1 rounded bg-[var(--hold)]/20 text-[var(--hold)]">
                {queue.count} pending
              </span>
            ) : null}
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {queue?.items.length === 0 ? (
              <div className="text-center py-8 text-[var(--text-secondary)]">
                {status?.market_state === 'closed'
                  ? 'Market closed. Triggers will queue and run at next open.'
                  : 'Queue is empty'}
              </div>
            ) : (
              queue?.items.map((item, idx) => (
                <div
                  key={`${item.ticker}-${idx}`}
                  className="flex items-center justify-between bg-[var(--bg)] rounded-lg p-3"
                >
                  <div className="flex items-center gap-3">
                    <Clock size={16} className="text-[var(--hold)]" />
                    <div>
                      <span className="font-mono text-sm">{item.ticker}</span>
                      <div className="text-xs text-[var(--text-secondary)] truncate max-w-xs">
                        {item.reason}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {new Date(item.queued_at).toLocaleTimeString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
