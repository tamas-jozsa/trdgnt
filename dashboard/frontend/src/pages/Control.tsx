import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import LiveFeed from '../components/LiveFeed';
import { Play, Pause, RefreshCw, Download, Plus, X, Circle, Target, TrendingUp, TrendingDown } from 'lucide-react';
import type { DeploymentConfig } from '../types';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

// Deployment Status Badge
function DeploymentStatusBadge({ status, message }: { status: string; message: string }) {
  const styles: Record<string, string> = {
    significantly_under_deployed: 'bg-red-500/20 text-red-400 border-red-500/30',
    under_deployed: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    on_target: 'bg-green-500/20 text-green-400 border-green-500/30',
    over_deployed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    unknown: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  const icons: Record<string, React.ReactNode> = {
    significantly_under_deployed: <TrendingUp size={14} className="text-red-400" />,
    under_deployed: <TrendingUp size={14} className="text-yellow-400" />,
    on_target: <Target size={14} className="text-green-400" />,
    over_deployed: <TrendingDown size={14} className="text-blue-400" />,
    unknown: <Circle size={14} className="text-gray-400" />,
    error: <Circle size={14} className="text-red-400" />,
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${styles[status] || styles.unknown}`}>
      {icons[status] || icons.unknown}
      <span className="font-medium">{message}</span>
    </div>
  );
}

export default function Control() {
  const queryClient = useQueryClient();
  const [addTicker, setAddTicker] = useState('');
  const [addTier, setAddTier] = useState('TACTICAL');
  const [toast, setToast] = useState('');
  const [targetValue, setTargetValue] = useState(50);

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
  });

  const { data: watchlist, refetch: refetchWatchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: api.getWatchlist,
  });

  // TICKET-078: Deployment config query
  const { data: deploymentConfig, refetch: refetchDeploymentConfig } = useQuery({
    queryKey: ['deployment-config'],
    queryFn: api.getDeploymentConfig,
  });

  // Sync slider with loaded config
  useEffect(() => {
    if (deploymentConfig) {
      setTargetValue(Math.round(deploymentConfig.target_deployment_pct * 100));
    }
  }, [deploymentConfig]);

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

  // TICKET-078: Deployment config mutation
  const deploymentMutation = useMutation({
    mutationFn: (target_pct: number) => api.setDeploymentConfig(target_pct / 100),
    onSuccess: (data: DeploymentConfig) => {
      refetchDeploymentConfig();
      showToast(`Target deployment set to ${(data.target_deployment_pct * 100).toFixed(0)}%`);
    },
    onError: (e) => showToast(`Error: ${e.message}`),
  });

  const dynamicTickers = watchlist?.tickers?.filter(t => t.source === 'dynamic') ?? [];

  // Format percentage for display
  const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

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
                {status?.today_trades.buy ?? 0}B / {status?.today_trades.sell ?? 0}S / {status?.today_trades.hold ?? 0}H / {status?.today_trades.na ?? 0}NA
              </span>
            </div>
          </div>
        </Card>

        {/* TICKET-078: Capital Deployment Target */}
        <Card>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Target size={18} className="text-[var(--accent)]" />
            Capital Deployment Target
          </h2>

          {deploymentConfig && (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex justify-center">
                <DeploymentStatusBadge
                  status={deploymentConfig.status}
                  message={deploymentConfig.message}
                />
              </div>

              {/* Slider */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-secondary)]">Conservative</span>
                  <span className="text-2xl font-bold text-[var(--accent)]">{targetValue}%</span>
                  <span className="text-xs text-[var(--text-secondary)]">Aggressive</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="95"
                  value={targetValue}
                  onChange={(e) => setTargetValue(parseInt(e.target.value))}
                  className="w-full h-2 bg-[var(--bg)] rounded-lg appearance-none cursor-pointer accent-[var(--accent)]"
                />
                <div className="flex justify-between text-xs text-[var(--text-secondary)]">
                  <span>10%</span>
                  <span>50%</span>
                  <span>95%</span>
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[var(--border)]">
                <div className="text-center">
                  <div className="text-xs text-[var(--text-secondary)]">Current</div>
                  <div className="text-lg font-medium">{fmtPct(deploymentConfig.current_deployment_pct)}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-[var(--text-secondary)]">Target</div>
                  <div className="text-lg font-medium">{fmtPct(deploymentConfig.target_deployment_pct)}</div>
                </div>
              </div>

              {/* Gap */}
              <div className="text-center text-sm">
                <span className="text-[var(--text-secondary)]">Gap: </span>
                <span className={deploymentConfig.gap > 0 ? 'text-[var(--profit)]' : deploymentConfig.gap < 0 ? 'text-[var(--loss)]' : 'text-[var(--hold)]'}>
                  {deploymentConfig.gap > 0 ? '+' : ''}{fmtPct(deploymentConfig.gap)}
                </span>
              </div>

              {/* Save Button */}
              <button
                onClick={() => deploymentMutation.mutate(targetValue)}
                disabled={deploymentMutation.isPending || targetValue === Math.round((deploymentConfig.target_deployment_pct ?? 0.5) * 100)}
                className="w-full bg-[var(--accent)] hover:bg-blue-600 disabled:bg-[var(--border)] disabled:cursor-not-allowed text-white py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {deploymentMutation.isPending ? 'Saving...' : 'Save Target'}
              </button>
            </div>
          )}

          {!deploymentConfig && (
            <div className="text-center text-sm text-[var(--text-secondary)] py-8">
              Loading deployment config...
            </div>
          )}
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
      </div>

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

      {/* Live Feed */}
      <LiveFeed />
    </div>
  );
}
