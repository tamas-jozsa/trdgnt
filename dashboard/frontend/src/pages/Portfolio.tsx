import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Shield, Zap, AlertTriangle, BarChart3 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const COLORS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#a855f7', '#06b6d4', '#f97316'];

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>
      {children}
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <Card>
      <div className="text-xs text-[var(--text-secondary)] mb-1">{label}</div>
      <div className={`text-2xl font-bold mono ${color || 'text-[var(--text)]'}`}>{value}</div>
      {sub && <div className="text-xs text-[var(--text-secondary)] mt-1">{sub}</div>}
    </Card>
  );
}

export default function Portfolio() {
  const navigate = useNavigate();
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: api.getPortfolio,
  });

  if (isLoading || !portfolio) {
    return <div className="text-[var(--text-secondary)]">Loading portfolio...</div>;
  }

  const { account, positions, sector_exposure, enforcement } = portfolio;
  const pieData = Object.entries(sector_exposure).map(([name, value]) => ({
    name,
    value: Math.round(value * 100),
  }));

  return (
    <div className="space-y-6">
      {/* Account Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Equity"
          value={`$${account.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
        />
        <StatCard
          label="Cash"
          value={`$${account.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          sub={`${(account.cash_ratio * 100).toFixed(1)}% of equity`}
        />
        <StatCard
          label="Total P&L"
          value={`${account.total_pnl >= 0 ? '+' : ''}$${account.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          sub={`${account.total_pnl_pct >= 0 ? '+' : ''}${account.total_pnl_pct.toFixed(2)}%`}
          color={account.total_pnl >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}
        />
        <StatCard
          label="Open Positions"
          value={String(positions.length)}
          sub={`of ${Math.round(positions.length + account.cash / 2000)} capacity`}
        />
      </div>

      {/* Enforcement Status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="flex items-center gap-3">
          <Zap size={20} className="text-[var(--enforce)]" />
          <div>
            <div className="text-xs text-[var(--text-secondary)]">Bypasses Today</div>
            <div className="text-lg font-bold mono">{enforcement.bypasses_today}</div>
          </div>
        </Card>
        <Card className="flex items-center gap-3">
          <Shield size={20} className="text-[var(--accent)]" />
          <div>
            <div className="text-xs text-[var(--text-secondary)]">Overrides Reverted</div>
            <div className="text-lg font-bold mono">{enforcement.overrides_reverted_today}</div>
          </div>
        </Card>
        <Card className="flex items-center gap-3">
          <BarChart3 size={20} className="text-[var(--profit)]" />
          <div>
            <div className="text-xs text-[var(--text-secondary)]">Quota Force-Buys</div>
            <div className="text-lg font-bold mono">{enforcement.quota_force_buys_today}</div>
          </div>
        </Card>
        <Card className="flex items-center gap-3">
          <AlertTriangle size={20} className="text-[var(--loss)]" />
          <div>
            <div className="text-xs text-[var(--text-secondary)]">Stop-Losses</div>
            <div className="text-lg font-bold mono">{enforcement.stop_losses_today}</div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Positions Table */}
        <Card className="lg:col-span-2 overflow-x-auto">
          <h2 className="text-lg font-semibold mb-4">Open Positions</h2>
          {positions.length === 0 ? (
            <p className="text-[var(--text-secondary)]">No open positions</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[var(--text-secondary)] text-xs border-b border-[var(--border)]">
                  <th className="text-left py-2 px-2">Ticker</th>
                  <th className="text-left py-2 px-2">Tier</th>
                  <th className="text-right py-2 px-2">Qty</th>
                  <th className="text-right py-2 px-2">Entry</th>
                  <th className="text-right py-2 px-2">Mkt Value</th>
                  <th className="text-right py-2 px-2">P&L</th>
                  <th className="text-right py-2 px-2">P&L %</th>
                  <th className="text-right py-2 px-2">Stop</th>
                  <th className="text-right py-2 px-2">Target</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr
                    key={p.ticker}
                    className="border-b border-[var(--border)] hover:bg-white/5 cursor-pointer"
                    onClick={() => navigate(`/agents/${p.ticker}/${new Date().toISOString().slice(0, 10)}`)}
                  >
                    <td className="py-2 px-2 font-semibold">{p.ticker}</td>
                    <td className="py-2 px-2 text-xs text-[var(--text-secondary)]">{p.tier}</td>
                    <td className="py-2 px-2 text-right mono">{p.qty.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right mono">${p.avg_entry_price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right mono">${p.market_value.toFixed(0)}</td>
                    <td className={`py-2 px-2 text-right mono ${p.unrealized_pl >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}`}>
                      {p.unrealized_pl >= 0 ? '+' : ''}${p.unrealized_pl.toFixed(2)}
                    </td>
                    <td className={`py-2 px-2 text-right mono ${p.unrealized_pl_pct >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}`}>
                      {p.unrealized_pl_pct >= 0 ? '+' : ''}{p.unrealized_pl_pct.toFixed(1)}%
                    </td>
                    <td className="py-2 px-2 text-right mono text-[var(--text-secondary)]">
                      {p.agent_stop ? `$${p.agent_stop.toFixed(0)}` : '-'}
                    </td>
                    <td className="py-2 px-2 text-right mono text-[var(--text-secondary)]">
                      {p.agent_target ? `$${p.agent_target.toFixed(0)}` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Sector Exposure */}
        <Card>
          <h2 className="text-lg font-semibold mb-4">Sector Exposure</h2>
          {pieData.length === 0 ? (
            <p className="text-[var(--text-secondary)]">No positions</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value}%`}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-3 space-y-1">
                {pieData.map((d, i) => (
                  <div key={d.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{ background: COLORS[i % COLORS.length] }} />
                      <span>{d.name}</span>
                    </div>
                    <span className="mono">{d.value}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
