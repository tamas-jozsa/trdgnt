import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useNavigate } from 'react-router-dom';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

export default function Research() {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState<string>('');

  const { data: findings } = useQuery({
    queryKey: ['findings', selectedDate],
    queryFn: () => api.getFindings(selectedDate || undefined),
  });

  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: api.getWatchlist,
  });

  const { data: quota } = useQuery({
    queryKey: ['quota'],
    queryFn: api.getQuota,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-bold">Research Findings</h1>
        {findings?.available_dates && (
          <select
            value={selectedDate || findings.date}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          >
            {findings.available_dates.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        )}
        {findings && (
          <div className="ml-auto flex items-center gap-3">
            <span className={`px-3 py-1 rounded-lg text-sm font-medium ${
              findings.sentiment === 'BULLISH' ? 'bg-green-900/40 text-[var(--profit)]' :
              findings.sentiment === 'BEARISH' ? 'bg-red-900/40 text-[var(--loss)]' :
              'bg-yellow-900/30 text-[var(--hold)]'
            }`}>{findings.sentiment}</span>
            <span className="mono text-sm">VIX: {findings.vix}</span>
            <span className="text-xs text-[var(--text-secondary)]">{findings.vix_trend}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signals Table */}
        <Card className="lg:col-span-2 overflow-x-auto">
          <h2 className="text-lg font-semibold mb-4">Ticker Signals</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--text-secondary)] text-xs border-b border-[var(--border)]">
                <th className="text-left py-2 px-2">Ticker</th>
                <th className="text-left py-2 px-2">Tier</th>
                <th className="text-center py-2 px-2">Decision</th>
                <th className="text-center py-2 px-2">Conviction</th>
                <th className="text-left py-2 px-2">Reason</th>
              </tr>
            </thead>
            <tbody>
              {findings?.signals?.map((s) => (
                <tr
                  key={s.ticker}
                  className="border-b border-[var(--border)] hover:bg-white/5 cursor-pointer"
                  onClick={() => navigate(`/agents/${s.ticker}/${findings.date}`)}
                >
                  <td className="py-2 px-2 font-semibold">{s.ticker}</td>
                  <td className="py-2 px-2 text-xs text-[var(--text-secondary)]">{s.tier}</td>
                  <td className="py-2 px-2 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      s.decision === 'BUY' ? 'bg-green-900/40 text-[var(--profit)]' :
                      s.decision === 'SELL' || s.decision === 'REDUCE' ? 'bg-red-900/40 text-[var(--loss)]' :
                      'bg-yellow-900/30 text-[var(--hold)]'
                    }`}>{s.decision}</span>
                  </td>
                  <td className="py-2 px-2 text-center text-xs">{s.conviction}</td>
                  <td className="py-2 px-2 text-xs text-[var(--text-secondary)]">{s.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Sector Signals */}
          {findings?.sector_signals && Object.keys(findings.sector_signals).length > 0 && (
            <Card>
              <h2 className="text-lg font-semibold mb-3">Sector Signals</h2>
              <div className="space-y-2">
                {Object.entries(findings.sector_signals).map(([sector, signal]) => (
                  <div key={sector} className="flex items-center justify-between text-sm">
                    <span>{sector}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      signal === 'FAVOR' ? 'bg-green-900/40 text-[var(--profit)]' :
                      signal === 'AVOID' ? 'bg-red-900/40 text-[var(--loss)]' :
                      'text-[var(--text-secondary)]'
                    }`}>{signal}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Watchlist */}
          <Card>
            <h2 className="text-lg font-semibold mb-3">
              Watchlist ({watchlist?.effective_count ?? 0} tickers)
            </h2>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {watchlist?.tickers?.map((t) => (
                <div key={t.ticker} className="flex items-center justify-between text-xs py-1 border-b border-[var(--border)]">
                  <span className="font-medium">{t.ticker}</span>
                  <span className={`px-1.5 py-0.5 rounded ${
                    t.tier === 'CORE' ? 'bg-blue-900/30 text-[var(--accent)]' :
                    t.tier === 'TACTICAL' ? 'bg-purple-900/30 text-[var(--enforce)]' :
                    t.tier === 'SPECULATIVE' ? 'bg-orange-900/30 text-orange-400' :
                    'bg-yellow-900/30 text-[var(--hold)]'
                  }`}>{t.tier}</span>
                  {t.source === 'dynamic' && <span className="text-[var(--enforce)]">+new</span>}
                </div>
              ))}
            </div>
          </Card>

          {/* Quota History */}
          {quota && quota.total_misses > 0 && (
            <Card>
              <h2 className="text-lg font-semibold mb-3">Buy Quota Audit</h2>
              <div className="text-sm text-[var(--text-secondary)] mb-2">
                {quota.total_misses} quota misses total
              </div>
              {(quota.recent as { timestamp: string; buys_executed: number; high_conviction_signals: number; force_buy_tickers?: string[] }[]).slice(0, 5).map((m, i) => (
                <div key={i} className="text-xs border-b border-[var(--border)] py-2">
                  <div className="flex justify-between">
                    <span>{m.timestamp.slice(0, 10)}</span>
                    <span className="text-[var(--loss)]">{m.buys_executed}/{m.high_conviction_signals} executed</span>
                  </div>
                  {m.force_buy_tickers && m.force_buy_tickers.length > 0 && (
                    <div className="text-[var(--enforce)] mt-1">
                      Force-bought: {m.force_buy_tickers.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </Card>
          )}
        </div>
      </div>

      {/* Full Findings Markdown */}
      {findings?.markdown && (
        <Card>
          <h2 className="text-lg font-semibold mb-4">Full Research Document</h2>
          <div className="prose prose-invert prose-sm max-w-none text-[var(--text-secondary)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{findings.markdown}</ReactMarkdown>
          </div>
        </Card>
      )}
    </div>
  );
}
