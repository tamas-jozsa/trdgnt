import { NavLink, Outlet } from 'react-router-dom';
import { BarChart3, Brain, LineChart, Newspaper, Search, Settings } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

const navItems = [
  { to: '/', label: 'Portfolio', icon: LineChart },
  { to: '/trades', label: 'Trades', icon: BarChart3 },
  { to: '/agents', label: 'Agents', icon: Brain },
  { to: '/research', label: 'Research', icon: Search },
  { to: '/news-monitor', label: 'News', icon: Newspaper },
  { to: '/control', label: 'Control', icon: Settings },
];

function NewsStatusDot() {
  const { data: status } = useQuery({
    queryKey: ['news-monitor-status'],
    queryFn: api.getNewsMonitorStatus,
  });

  if (!status?.enabled) return null;

  return (
    <span
      className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${
        status?.polling ? 'bg-[var(--profit)]' : 'bg-[var(--hold)]'
      }`}
    />
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="border-b border-[var(--border)] bg-[var(--surface)] px-6 py-3 flex items-center gap-8">
        <span className="font-bold text-lg tracking-tight text-[var(--accent)]">trdagnt</span>
        <div className="flex gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-white'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-white/5'
                }`
              }
              end={to === '/'}
            >
              <Icon size={16} />
              {label}
              {label === 'News' && <NewsStatusDot />}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
