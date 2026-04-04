import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import { Play, Pause, RefreshCw, Download, Plus, X, Circle } from 'lucide-react';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

export default function Control() {
  const queryClient = useQueryClient();
  const { messages, connected } = useWebSocket();
  const feedRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [addTicker, setAddTicker] = useState('');
  const [addTier, setAddTier] = useState('TACTICAL');
  const [toast, setToast] = useState('');

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 10000,
  });

  const { data: watchlist, refetch: refetchWatchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: api.getWatchlist,
  });

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  };

  const runMutation = useMutation({
    mutationFn: (dryRun: boolean) => api.runCycle(dryRun),
    onSuccess: (data) => showToast(`Cycle started (PID: ${data.pid})`),
    onError: (e) => showToast(`Error: ${e.message}`),
  });

  const researchMutation = useMutation({
    mutationFn: api.runResearch,
    onSuccess: () => showToast('Research started'),
  });

  const syncMutation = useMutation({
    mutationFn: api.syncPositions,
    onSuccess: (data) => {
      showToast(`Synced ${data.positions} positions`);
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });

  const watchlistMutation = useMutation({
    mutationFn: ({ action, ticker }: { action: 'add' | 'remove'; ticker: string }) =>
      api.modifyWatchlist(action, ticker, addTier),
    onSuccess: () => {
      refetchWatchlist();
      setAddTicker('');
      showToast('Watchlist updated');
    },
  });

  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  const getLineColor = (type: string, text?: string) => {
    if (type === 'trade' || text?.includes('BUY')) return 'text-[var(--profit)]';
    if (type === 'stop_loss' || text?.includes('SELL')) return 'text-[var(--loss)]';
    if (type === 'override' || type === 'bypass' || type === 'quota') return 'text-[var(--enforce)]';
    if (type === 'wait') return 'text-[var(--text-secondary)] opacity-50';
    return 'text-[var(--text-secondary)]';
  };

  const dynamicTickers = watchlist?.tickers?.filter(t => t.source === 'dynamic') ?? [];

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 bg-[var(--accent)] text-white px-4 py-2 rounded-lg text-sm shadow-lg z-50">
          {toast}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Status */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">System Status</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Agent</span>
              <span className={`flex items-center gap-2 text-sm ${status?.agent_running ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}`}>
                <Circle size={8} fill="currentColor" />
                {status?.agent_running ? `Running (PID ${status.agent_pid})` : 'Stopped'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Tickers</span>
              <span className="text-sm mono">{status?.tickers}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Cash Ratio</span>
              <span className="text-sm mono">{((status?.cash_ratio ?? 0) * 100).toFixed(1)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Positions</span>
              <span className="text-sm mono">{status?.open_positions}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Research</span>
              <span className={`text-sm ${status?.today_research_done ? 'text-[var(--profit)]' : 'text-[var(--hold)]'}`}>
                {status?.today_research_done ? 'Done' : 'Pending'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-secondary)]">Today</span>
              <span className="text-sm mono">
                {status?.today_trades.buy ?? 0}B / {status?.today_trades.sell ?? 0}S / {status?.today_trades.hold ?? 0}H
              </span>
            </div>
          </div>
        </Card>

        {/* Actions */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Actions</h2>
          <div className="space-y-3">
            <button
              onClick={() => runMutation.mutate(false)}
              disabled={runMutation.isPending}
              className="w-full flex items-center justify-center gap-2 bg-[var(--accent)] hover:bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Play size={16} /> Run Cycle Now
            </button>
            <button
              onClick={() => runMutation.mutate(true)}
              disabled={runMutation.isPending}
              className="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              <Pause size={16} /> Dry Run
            </button>
            <button
              onClick={() => researchMutation.mutate()}
              disabled={researchMutation.isPending}
              className="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} /> Force Research
            </button>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="w-full flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              <Download size={16} /> Sync Positions
            </button>
          </div>
        </Card>

        {/* Watchlist Editor */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Watchlist Editor</h2>
          <div className="flex gap-2 mb-4">
            <input
              value={addTicker}
              onChange={(e) => setAddTicker(e.target.value.toUpperCase())}
              placeholder="TICKER"
              className="flex-1 bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
            />
            <select
              value={addTier}
              onChange={(e) => setAddTier(e.target.value)}
              className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-2 py-2 text-sm"
            >
              <option>CORE</option>
              <option>TACTICAL</option>
              <option>SPECULATIVE</option>
              <option>HEDGE</option>
            </select>
            <button
              onClick={() => addTicker && watchlistMutation.mutate({ action: 'add', ticker: addTicker })}
              disabled={!addTicker}
              className="bg-[var(--profit)] hover:bg-green-600 text-white px-3 rounded-lg disabled:opacity-50"
            >
              <Plus size={16} />
            </button>
          </div>
          {dynamicTickers.length > 0 && (
            <>
              <div className="text-xs text-[var(--text-secondary)] mb-2">Dynamic overrides:</div>
              <div className="space-y-1">
                {dynamicTickers.map(t => (
                  <div key={t.ticker} className="flex items-center justify-between text-sm py-1 px-2 rounded bg-white/5">
                    <span>{t.ticker} <span className="text-xs text-[var(--text-secondary)]">({t.tier})</span></span>
                    <button
                      onClick={() => watchlistMutation.mutate({ action: 'remove', ticker: t.ticker })}
                      className="text-[var(--loss)] hover:text-red-400"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Live Feed */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            Live Feed
            <Circle size={8} fill={connected ? '#22c55e' : '#ef4444'} className={connected ? 'text-[var(--profit)]' : 'text-[var(--loss)]'} />
          </h2>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--text)]"
          >
            {autoScroll ? 'Pause' : 'Resume'} auto-scroll
          </button>
        </div>
        <div
          ref={feedRef}
          className="bg-[var(--bg)] rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs space-y-0.5"
        >
          {messages.length === 0 ? (
            <div className="text-[var(--text-secondary)]">Waiting for log output...</div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={getLineColor(m.type, m.text)}>
                {m.text || `[${m.type}] ${m.ticker || ''} ${m.decision || m.action || ''}`}
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
