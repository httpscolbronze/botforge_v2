import { MessageSquare, Trash2 } from 'lucide-react';
import { formatRelative } from '../../services/format.js';

export default function ConversationList({ items, activeId, onSelect, onDelete, loading }) {
  if (loading && !items.length) {
    return (
      <div className="space-y-2 px-2">
        {[0, 1, 2].map((key) => (
          <div key={key} className="h-9 animate-pulse rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="px-3 py-6 text-center">
        <MessageSquare size={18} className="mx-auto mb-2 text-slate-600" />
        <p className="text-xs text-slate-500">No conversations yet. Start a new chat.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-1 px-2">
      {items.map((item) => {
        const active = item.id === activeId;
        return (
          <li key={item.id} className="group relative">
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition ${
                active
                  ? 'bg-white/[0.07] text-slate-100 ring-1 ring-inset ring-white/[0.08]'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`}
            >
              <MessageSquare
                size={14}
                className={active ? 'text-electric-400' : 'text-slate-500'}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">
                  {item.title || 'Untitled'}
                </span>
                <span className="block text-[10px] text-slate-500">
                  {formatRelative(item.updated_at)} · {item.message_count || 0} messages
                </span>
              </span>
            </button>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onDelete(item.id);
              }}
              className="absolute right-1.5 top-1/2 hidden -translate-y-1/2 rounded-md p-1.5 text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-300 group-hover:block"
              aria-label={`Delete ${item.title}`}
            >
              <Trash2 size={13} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
