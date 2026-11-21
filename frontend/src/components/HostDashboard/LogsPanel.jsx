import { useState } from 'react';
import { Loader2, RefreshCw, ScrollText } from 'lucide-react';

const LEVEL_STYLES = {
  ERROR: 'text-rose-300',
  CRITICAL: 'text-rose-300',
  WARNING: 'text-amber-300',
  INFO: 'text-slate-300',
  DEBUG: 'text-slate-500',
};

export default function LogsPanel({ logs, loading, onRefresh }) {
  const [level, setLevel] = useState('');
  const [query, setQuery] = useState('');

  const filtered = logs.filter((entry) => {
    if (level && entry.level !== level) return false;
    if (query && !entry.message.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-3">
      <div className="panel flex flex-wrap items-center gap-2 p-3">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <ScrollText size={13} /> {filtered.length} entries
        </div>
        <input
          className="input ml-auto max-w-[220px] py-1.5 text-[11px]"
          placeholder="Filter messages…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Filter logs"
        />
        <select
          className="input w-auto py-1.5 text-[11px]"
          value={level}
          onChange={(event) => setLevel(event.target.value)}
          aria-label="Log level"
        >
          <option value="">All levels</option>
          <option value="INFO">Info</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
        </select>
        <button type="button" onClick={onRefresh} className="btn-secondary px-2.5 py-1.5 text-[11px]">
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Refresh
        </button>
      </div>

      <div className="panel overflow-hidden">
        <div className="max-h-[62vh] overflow-y-auto bg-forge-950/70 p-3 font-mono text-[10.5px] leading-relaxed">
          {filtered.length === 0 ? (
            <p className="py-8 text-center text-slate-600">No log entries match this filter.</p>
          ) : (
            filtered
              .slice()
              .reverse()
              .map((entry, index) => (
                <div
                  key={`${entry.time}-${index}`}
                  className="flex gap-2 border-b border-white/[0.03] py-1 last:border-0"
                >
                  <span className="shrink-0 text-slate-600">{entry.time}</span>
                  <span className={`w-14 shrink-0 ${LEVEL_STYLES[entry.level] || 'text-slate-400'}`}>
                    {entry.level}
                  </span>
                  <span className="min-w-0 flex-1 break-words text-slate-400">{entry.message}</span>
                </div>
              ))
          )}
        </div>
      </div>

      <p className="text-[10px] text-slate-600">
        The last 400 backend log lines are kept in memory. Restarting the server clears them.
      </p>
    </div>
  );
}
