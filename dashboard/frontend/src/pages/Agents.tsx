import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronDown, ChevronRight } from 'lucide-react';

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${className}`}>{children}</div>;
}

function Section({ title, content, defaultOpen = false }: { title: string; content: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-[var(--border)]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 py-3 px-2 text-left hover:bg-white/5 transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span className="font-semibold text-sm">{title}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 prose prose-invert prose-sm max-w-none text-[var(--text-secondary)]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

const SECTION_LABELS: Record<string, string> = {
  research_manager: 'Research Manager',
  trader: 'Trader Proposal',
  risk_judge: 'Risk Judge Decision',
  bull_case: 'Bull Case',
  bear_case: 'Bear Case',
  market_analyst: 'Market Analyst',
  social_analyst: 'Social Analyst',
  news_analyst: 'News Analyst',
  fundamentals_analyst: 'Fundamentals Analyst',
};

export default function Agents() {
  const { ticker: paramTicker, date: paramDate } = useParams();
  const [selectedTicker, setSelectedTicker] = useState(paramTicker || '');
  const [selectedDate, setSelectedDate] = useState(paramDate || '');

  const { data: reportList } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.getReports({ limit: 200 }),
  });

  const { data: overrides } = useQuery({
    queryKey: ['overrides'],
    queryFn: () => api.getOverrides(30),
  });

  // Get unique dates and tickers (filtered by selected date)
  const dates = [...new Set(reportList?.reports?.map(r => r.date) ?? [])].sort().reverse();
  const tickers = [...new Set(reportList?.reports?.filter(r => !selectedDate || r.date === selectedDate).map(r => r.ticker) ?? [])];

  // Auto-select first date and ticker on initial load
  useEffect(() => {
    if (!selectedDate && dates.length > 0) {
      const latestDate = dates[0];
      setSelectedDate(latestDate);
      // Find first ticker for this date
      const firstTicker = reportList?.reports?.find(r => r.date === latestDate)?.ticker;
      if (firstTicker) setSelectedTicker(firstTicker);
    }
  }, [reportList, dates, selectedDate]);

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', selectedTicker, selectedDate],
    queryFn: () => api.getReport(selectedTicker, selectedDate),
    enabled: !!selectedTicker && !!selectedDate,
  });

  const tickerOverrides = overrides?.overrides?.filter(o => o.ticker === selectedTicker) ?? [];

  return (
    <div className="space-y-6">
      {/* Selector */}
      <Card className="flex items-center gap-4 flex-wrap">
        <div>
          <label className="text-xs text-[var(--text-secondary)] block mb-1">Date</label>
          <select
            value={selectedDate}
            onChange={(e) => {
              const newDate = e.target.value;
              setSelectedDate(newDate);
              // Reset ticker to first available for this date
              const firstTicker = reportList?.reports?.find(r => r.date === newDate)?.ticker;
              if (firstTicker) setSelectedTicker(firstTicker);
            }}
            className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          >
            {dates.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-[var(--text-secondary)] block mb-1">Ticker</label>
          <select
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
          >
            {tickers.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        {report && (
          <div className="ml-auto flex items-center gap-4">
            <span className={`text-2xl font-bold ${
              report.decision === 'BUY' ? 'text-[var(--profit)]' :
              report.decision === 'SELL' ? 'text-[var(--loss)]' : 'text-[var(--hold)]'
            }`}>{report.decision}</span>
            <span className="text-lg mono text-[var(--text-secondary)]">
              Conv: {report.conviction}/10
            </span>
            {report.bypass && (
              <span className="px-2 py-1 rounded text-xs bg-purple-900/40 text-[var(--enforce)]">BYPASS</span>
            )}
            {report.override && (
              <span className="px-2 py-1 rounded text-xs bg-orange-900/40 text-[var(--hold)]">OVERRIDE</span>
            )}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Report Viewer */}
        <Card className="lg:col-span-2">
          <h2 className="text-lg font-semibold mb-4">Agent Analysis Report</h2>
          {isLoading ? (
            <p className="text-[var(--text-secondary)]">Loading...</p>
          ) : report ? (
            <div>
              {Object.entries(report.sections).map(([key, content]) => (
                <Section
                  key={key}
                  title={SECTION_LABELS[key] || key}
                  content={content}
                  defaultOpen={key === 'research_manager' || key === 'risk_judge'}
                />
              ))}
              {Object.keys(report.sections).length === 0 && (
                <div className="prose prose-invert prose-sm max-w-none text-[var(--text-secondary)]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report_markdown}</ReactMarkdown>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[var(--text-secondary)]">Select a date and ticker</p>
          )}
        </Card>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Override Log */}
          <Card>
            <h2 className="text-lg font-semibold mb-3">Signal Overrides</h2>
            {tickerOverrides.length === 0 ? (
              <p className="text-sm text-[var(--text-secondary)]">No overrides for {selectedTicker}</p>
            ) : (
              <div className="space-y-3">
                {tickerOverrides.map((o, i) => (
                  <div key={i} className="text-sm border-b border-[var(--border)] pb-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        o.severity === 'critical' ? 'bg-red-900/40 text-[var(--loss)]' :
                        o.severity === 'high' ? 'bg-orange-900/40 text-[var(--hold)]' :
                        'bg-blue-900/30 text-[var(--accent)]'
                      }`}>{o.severity}</span>
                      <span className="mono">{o.upstream_signal} {'→'} {o.final_signal}</span>
                      {o.reverted && <span className="text-[var(--enforce)] text-xs">REVERTED</span>}
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] mt-1">{o.timestamp.slice(0, 10)}</div>
                    <div className="text-xs text-[var(--text-secondary)] mt-1 truncate">{o.reason}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Recent Reports for All Tickers */}
          <Card>
            <h2 className="text-lg font-semibold mb-3">Recent Reports</h2>
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {reportList?.reports?.slice(0, 30).map((r, i) => (
                <button
                  key={i}
                  onClick={() => { setSelectedTicker(r.ticker); setSelectedDate(r.date); }}
                  className={`w-full flex items-center justify-between px-2 py-1.5 rounded text-sm hover:bg-white/5 ${
                    r.ticker === selectedTicker && r.date === selectedDate ? 'bg-white/10' : ''
                  }`}
                >
                  <span className="font-medium">{r.ticker}</span>
                  <span className={`text-xs ${
                    r.decision === 'BUY' ? 'text-[var(--profit)]' :
                    r.decision === 'SELL' ? 'text-[var(--loss)]' : 'text-[var(--text-secondary)]'
                  }`}>{r.decision} ({r.conviction})</span>
                  <span className="text-xs text-[var(--text-secondary)]">{r.date}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
