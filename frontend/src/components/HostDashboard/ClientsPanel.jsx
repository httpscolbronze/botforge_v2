import { RefreshCw, Users } from 'lucide-react';
import { formatRelative } from '../../services/format.js';

export default function ClientsPanel({ clients, onRefresh }) {
  const items = clients?.clients || [];

  return (
    <div className="space-y-4">
      <div className="panel flex flex-wrap items-center gap-3 p-4">
        <div className="rounded-xl border border-white/10 bg-white/[0.04] p-2 text-electric-300">
          <Users size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-medium text-slate-100">
            {items.length} active workspace{items.length === 1 ? '' : 's'}
          </p>
          <p className="text-[10.5px] text-slate-500">
            Presence window: {clients?.window_seconds ?? 90}s. Clients send a heartbeat every 30s.
          </p>
        </div>
        <button type="button" onClick={onRefresh} className="btn-secondary px-2.5 py-1.5 text-[11px]">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <div className="panel overflow-hidden">
        {items.length === 0 ? (
          <div className="p-10 text-center">
            <Users size={24} className="mx-auto mb-2 text-slate-600" />
            <p className="text-[12px] text-slate-400">No clients are online right now.</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Open the client workspace in another tab and it will appear here.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-[11.5px]">
            <thead className="border-b border-white/[0.06] text-[9.5px] uppercase tracking-[0.1em] text-slate-500">
              <tr>
                <th className="px-4 py-2.5 font-medium">Workspace</th>
                <th className="px-4 py-2.5 font-medium">Mode</th>
                <th className="px-4 py-2.5 font-medium">First seen</th>
                <th className="px-4 py-2.5 font-medium">Last heartbeat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {items.map((client) => (
                <tr key={client.client_id} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-slate-200">{client.name || 'Workspace'}</p>
                    <p className="font-mono text-[10px] text-slate-500">{client.client_id}</p>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="chip text-[10px]">{client.mode || 'client'}</span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">{formatRelative(client.first_seen)}</td>
                  <td className="px-4 py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-emerald-300">
                      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-emerald-400" />
                      {formatRelative(client.last_seen)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-[10px] leading-relaxed text-slate-600">
        Presence is informational. Documents and personas are scoped by workspace id, but this is
        not multi-tenant authentication — see the security notes in the README.
      </p>
    </div>
  );
}
