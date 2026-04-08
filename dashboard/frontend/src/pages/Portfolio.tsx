import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import { Shield, Zap, AlertTriangle, BarChart3, Info, TrendingUp, TrendingDown, Wallet } from 'lucide-react';
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

function HelperLabel({ label, text }: { label: string; text: string }) {
  return (
    <div className="flex items-center gap-1">
      <span>{label}</span>
      <button
        type="button"
        className="group relative inline-flex items-center text-[var(--text-secondary)] transition-colors hover:text-[var(--text)] focus:text-[var(--text)] focus:outline-none"
        aria-label={`${label}: ${text}`}
      >
        <Info size={12} />
        <span className="pointer-events-none absolute left-1/2 top-0 z-20 hidden w-64 -translate-x-1/2 -translate-y-[calc(100%+0.65rem)] rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left text-xs leading-relaxed text-[var(--text-secondary)] shadow-xl group-hover:block group-focus:block">
          {text}
        </span>
      </button>
    </div>
  );
}

function EnforcementCard({
  icon: Icon,
  iconColor,
  label,
  value,
  helpText,
}: {
  icon: React.ElementType;
  iconColor: string;
  label: string;
  value: number;
  helpText: string;
}) {
  return (
    <Card className="flex items-center gap-3">
      <Icon size={20} className={iconColor} />
      <div>
        <div className="text-xs text-[var(--text-secondary)]">
          <HelperLabel label={label} text={helpText} />
        </div>
        <div className="text-lg font-bold mono">{value}</div>
      </div>
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

      {/* Enforcement Status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <EnforcementCard
          icon={Zap}
          iconColor="text-[var(--enforce)]"
          label="Bypasses Today"
          value={enforcement.bypasses_today}
          helpText="High-conviction trades that skipped the normal Risk Judge step and went straight to execution."
        />
        <EnforcementCard
          icon={Shield}
          iconColor="text-[var(--accent)]"
          label="Overrides Reverted"
          value={enforcement.overrides_reverted_today}
          helpText="Signals that were previously overridden, then later switched back after conditions changed."
        />
        <EnforcementCard
          icon={BarChart3}
          iconColor="text-[var(--profit)]"
          label="Quota Force-Buys"
          value={enforcement.quota_force_buys_today}
          helpText="Forced BUYs used to deploy excess cash when the strategy's minimum buy quota was missed."
        />
        <EnforcementCard
          icon={AlertTriangle}
          iconColor="text-[var(--loss)]"
          label="Stop-Losses"
          value={enforcement.stop_losses_today}
          helpText="Positions exited because an agent stop or a hard stop-loss threshold was triggered."
        />
      </div>
      <div className="text-xs text-[var(--text-secondary)]">
        These counters reset daily. A value of 0 means that event has not been recorded today.
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
