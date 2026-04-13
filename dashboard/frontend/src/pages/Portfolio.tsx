import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import { TrendingUp, TrendingDown, Wallet, BarChart3 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const COLORS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#a855f7', '#06b6d4', '#f97316'];

const MONEY_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const PERCENT_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatSignedCurrency(value: number) {
  return `${value >= 0 ? '+' : '-'}${MONEY_FORMATTER.format(Math.abs(value))}`;
}

function formatSignedPercent(value: number) {
  return `${value >= 0 ? '+' : ''}${PERCENT_FORMATTER.format(value)}%`;
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>
      {children}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  color,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  icon?: React.ElementType;
}) {
  return (
    <Card>
      <div className="mb-1 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
        {Icon ? <Icon size={14} /> : null}
        <span>{label}</span>
      </div>
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

  const { account, positions, sector_exposure } = portfolio;
  const pieData = Object.entries(sector_exposure).map(([name, value]) => ({
    name,
    value: Math.round(value * 100),
  }));
  const updatedAt = portfolio.updated_at ? new Date(portfolio.updated_at) : null;
  const isUpdatedToday = updatedAt ? updatedAt.toISOString().slice(0, 10) === new Date().toISOString().slice(0, 10) : false;
  const hasDayChange = isUpdatedToday || account.day_pnl !== 0 || account.day_pnl_pct !== 0;
  const dayChangeColor = account.day_pnl >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]';
  const DayChangeIcon = account.day_pnl >= 0 ? TrendingUp : TrendingDown;

  return (
    <div className="space-y-6">
      {/* Account Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          label="Equity"
          value={MONEY_FORMATTER.format(account.equity)}
          icon={Wallet}
        />
        <StatCard
          label="Invested"
          value={MONEY_FORMATTER.format(account.total_invested)}
          sub={`${(account.total_invested / Math.max(account.equity, 1) * 100).toFixed(1)}% deployed`}
          icon={BarChart3}
        />
        <StatCard
          label="Cash"
          value={MONEY_FORMATTER.format(account.cash)}
          sub={`${(account.cash_ratio * 100).toFixed(1)}% of equity`}
        />
        <StatCard
          label="Day Change"
          value={hasDayChange ? formatSignedCurrency(account.day_pnl) : 'n/a'}
          sub={hasDayChange ? formatSignedPercent(account.day_pnl_pct) : 'Waiting for a prior-day equity snapshot'}
          color={hasDayChange ? dayChangeColor : 'text-[var(--text-secondary)]'}
          icon={DayChangeIcon}
        />
        <StatCard
          label="Total P&L"
          value={formatSignedCurrency(account.total_pnl)}
          sub={formatSignedPercent(account.total_pnl_pct)}
          color={account.total_pnl >= 0 ? 'text-[var(--profit)]' : 'text-[var(--loss)]'}
        />
        <StatCard
          label="Open Positions"
          value={String(positions.length)}
          sub={`of ${Math.round(positions.length + account.cash / 2000)} capacity`}
        />
      </div>
      {updatedAt ? (
        <div className="text-xs text-[var(--text-secondary)]">
          Portfolio snapshot updated {updatedAt.toLocaleString()}.
        </div>
      ) : null}

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
                {[...positions].sort((a, b) => b.unrealized_pl - a.unrealized_pl).map((p) => (
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
                  <RechartsTooltip />
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
