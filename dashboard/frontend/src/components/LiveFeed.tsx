import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

function getLineColor(line: string): string {
  if (line.includes('BUY') || line.includes('profit') || line.includes('+')) return 'text-[var(--profit)]';
  if (line.includes('SELL') || line.includes('loss') || line.includes('-')) return 'text-[var(--loss)]';
  if (line.includes('[WAIT]')) return 'text-[var(--text-secondary)] opacity-50';
  if (line.includes('[SYNC]')) return 'text-[var(--accent)]';
  if (line.includes('[AGENT]')) return 'text-blue-400';
  if (line.includes('[TRADINGAGENTS]')) return 'text-purple-400';
  return 'text-[var(--text-secondary)]';
}

export default function LiveFeed() {
  const [activeTab, setActiveTab] = useState<'scheduled' | 'manual'>('scheduled');
  const [scheduledLines, setScheduledLines] = useState<string[]>([]);
  const [manualLines, setManualLines] = useState<string[]>([]);
  const [manualFile, setManualFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const [scheduled, manual] = await Promise.all([
        api.getScheduledLogs(2000),
        api.getManualLogs(2000),
      ]);
      setScheduledLines(scheduled.lines);
      setManualLines(manual.lines);
      setManualFile(manual.file);
    } finally {
      setLoading(false);
    }
  };

  // Fetch on mount only - no auto-refresh
  useEffect(() => {
    fetchLogs();
  }, []);

  // Scroll to bottom when tab changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeTab]);

  const lines = activeTab === 'scheduled' ? scheduledLines : manualLines;

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Live Feed</h2>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="text-xs text-[var(--text-secondary)] hover:text-[var(--text)] disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border)] mb-3">
        <button
          onClick={() => setActiveTab('scheduled')}
          className={`px-4 py-2 text-sm transition-colors relative ${
            activeTab === 'scheduled'
              ? 'text-[var(--text)]'
              : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
          }`}
        >
          Scheduled
          {activeTab === 'scheduled' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent)]" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('manual')}
          className={`px-4 py-2 text-sm transition-colors relative ${
            activeTab === 'manual'
              ? 'text-[var(--text)]'
              : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
          }`}
        >
          Manual
          {activeTab === 'manual' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent)]" />
          )}
        </button>
      </div>

      {/* Info line */}
      <div className="text-xs text-[var(--text-secondary)] mb-2">
        {activeTab === 'scheduled' ? (
          <span>Background daemon logs (last {scheduledLines.length} lines)</span>
        ) : manualFile ? (
          <span>Latest manual run: {manualFile}</span>
        ) : (
          <span>No manual runs found</span>
        )}
      </div>

      {/* Log display */}
      <div ref={scrollRef} className="bg-[var(--bg)] rounded-lg p-4 h-96 overflow-y-auto font-mono text-xs space-y-0.5">
        {lines.length === 0 ? (
          <div className="text-[var(--text-secondary)]">
            {activeTab === 'scheduled' ? 'No scheduled logs available' : 'No manual runs found'}
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className={getLineColor(line)}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
