import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

export default function Trades() {
  const [filter, setFilter] = useState<string>('');

  // Always fetch ALL trades, filter client-side for instant response
  const { data: tradesData, isLoading, error } = useQuery({
    queryKey: ['trades'],
    queryFn: () => api.getTrades({ limit: 500 }),
    retry: 2,
  });
  const { data: perf } = useQuery({
    queryKey: ['performance'],
    queryFn: () => api.getPerformance(30),
    retry: 2,
  });

  const allTrades = tradesData?.trades ?? [];
  const trades = filter
    ? allTrades.filter(t => t.decision.toUpperCase() === filter)
    : allTrades;
  const byTicker = perf?.by_ticker ?? [];

  return (
    <div className="space-y-6">
      {/* Performance Metrics */}
      {perf && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <div className="text-xs text-[var(--text-secondary)]">Total Trades</div>
            <div className="text-2xl font-bold mono">{perf.total_trades}</div>
            <div className="text-xs text-[var(--text-secondary)]">{perf.buys}B / {perf.sells}S / {perf.holds}H</div>
          </Card>
          <Card>
            <div className="text-xs text-[var(--text-secondary)]">Win Rate</div>
            <div className={`text-2xl font-bold mono ${perf.win_rate >= 0.5 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}`}>
              {(perf.win_rate * 100).toFixed(0)}%
            </div>
          </Card>
          <Card>
            <div className="text-xs text-[var(--text-secondary)]">Total P&L</div>
            <div className={`text-2xl font-bold mono ${perf.total_pnl >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}`}>
              {perf.total_pnl >= 0 ? '+' : ''}${perf.total_pnl.toFixed(0)}
            </div>
          </Card>
          <Card>
            <div className="text-xs text-[var(--text-secondary)]">Best Trade</div>
            <div className="text-lg font-bold text-[var(--profit)]">{perf.best_trade?.ticker}</div>
            <div className="text-xs mono text-[var(--profit)]">+${perf.best_trade?.pnl.toFixed(0)}</div>
          </Card>
          <Card>
            <div className="text-xs text-[var(--text-secondary)]">Worst Trade</div>
            <div className="text-lg font-bold text-[var(--loss)]">{perf.worst_trade?.ticker}</div>
            <div className="text-xs mono text-[var(--loss)]">${perf.worst_trade?.pnl.toFixed(0)}</div>
          </Card>
        </div>
      )}

      {/* P&L by Ticker Chart */}
      {byTicker.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold mb-4">P&L by Ticker</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={byTicker.slice(0, 20)} layout="vertical" margin={{ left: 50 }}>
              <XAxis type="number" tick={{ fill: '#8b8fa3', fontSize: 12 }} />
              <YAxis type="category" dataKey="ticker" tick={{ fill: '#e1e4eb', fontSize: 12 }} width={50} />
              <Tooltip contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }} />
              <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                {byTicker.slice(0, 20).map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Trade Log */}
      <Card className="overflow-x-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Trade Log</h2>
          <div className="flex gap-2">
            {['', 'BUY', 'SELL', 'HOLD'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                  filter === f
                    ? 'bg-[var(--accent)] text-white'
                    : 'bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
              >
                {f || 'ALL'}
              </button>
            ))}
          </div>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--text-secondary)] text-xs border-b border-[var(--border)]">
              <th className="text-left py-2 px-2">Date</th>
              <th className="text-left py-2 px-2">Ticker</th>
              <th className="text-left py-2 px-2">Tier</th>
              <th className="text-center py-2 px-2">Decision</th>
              <th className="text-right py-2 px-2">Conv</th>
              <th className="text-right py-2 px-2">Size</th>
              <th className="text-left py-2 px-2">Status</th>
              <th className="text-left py-2 px-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i} className="border-b border-[var(--border)] hover:bg-white/5">
                <td className="py-2 px-2 mono text-xs">{t.date}</td>
                <td className="py-2 px-2 font-semibold">{t.ticker}</td>
                <td className="py-2 px-2 text-xs text-[var(--text-secondary)]">{t.tier}</td>
                <td className="py-2 px-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    t.decision === 'BUY' ? 'bg-green-900/40 text-[var(--profit)]' :
                    t.decision === 'SELL' ? 'bg-red-900/40 text-[var(--loss)]' :
                    'bg-yellow-900/30 text-[var(--hold)]'
                  }`}>{t.decision}</span>
                </td>
                <td className="py-2 px-2 text-right mono">{t.conviction || '-'}</td>
                <td className="py-2 px-2 text-right mono">{t.size_multiplier ? `${t.size_multiplier}x` : '-'}</td>
                <td className="py-2 px-2 text-xs">{t.status}</td>
                <td className="py-2 px-2 text-xs text-[var(--text-secondary)]">{t.source !== 'normal' ? t.source : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {isLoading && <p className="text-center py-8 text-[var(--text-secondary)]">Loading trades...</p>}
        {error && <p className="text-center py-8 text-[var(--loss)]">Error loading trades: {(error as Error).message}</p>}
        {!isLoading && !error && trades.length === 0 && <p className="text-center py-8 text-[var(--text-secondary)]">No trades found for filter "{filter || 'ALL'}"</p>}
      </Card>
    </div>
  );
}
