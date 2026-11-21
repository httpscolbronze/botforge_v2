import { useState } from 'react';
import {
  AlertTriangle,
  Check,
  Copy,
  FileText,
  Loader2,
  Sparkles,
  Volume2,
} from 'lucide-react';
import Markdown from '../shared/Markdown.jsx';
import { formatClock, initials } from '../../services/format.js';

export default function MessageBubble({
  message,
  personaName,
  onSpeak,
  speaking = false,
  voiceAvailable = true,
}) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const pending = message.pending && !message.content;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard can be blocked; no need to surface */
    }
  };

  return (
    <div className={`flex gap-3 animate-fade-up ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-[11px] font-semibold ${
          isUser
            ? 'border-white/10 bg-white/[0.06] text-slate-300'
            : 'border-electric-500/30 bg-gradient-to-br from-electric-600/25 to-violet-600/25 text-indigo-200'
        }`}
      >
        {isUser ? 'You' : initials(personaName)}
      </div>

      <div className={`min-w-0 max-w-[85%] ${isUser ? 'items-end' : ''}`}>
        <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-slate-500">
          <span>{isUser ? 'You' : personaName || 'Assistant'}</span>
          <span>{formatClock(message.created_at)}</span>
        </div>

        <div
          className={`rounded-2xl border px-4 py-3 ${
            isUser
              ? 'rounded-tr-sm border-white/[0.08] bg-white/[0.05] text-slate-100'
              : message.error
                ? 'rounded-tl-sm border-rose-500/25 bg-rose-500/[0.07]'
                : 'rounded-tl-sm border-white/[0.06] bg-forge-850/90'
          }`}
        >
          {pending ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 size={14} className="animate-spin text-electric-400" />
              Thinking locally…
            </div>
          ) : message.error ? (
            <div className="flex items-start gap-2.5 text-sm text-rose-200">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Could not complete this request</p>
                <p className="mt-1 text-rose-200/80">{message.content}</p>
              </div>
            </div>
          ) : isUser ? (
            <p className="whitespace-pre-wrap break-words text-[14.5px] leading-relaxed">
              {message.content}
            </p>
          ) : (
            <Markdown content={message.content} />
          )}

          {message.pending && message.content && (
            <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse-soft bg-electric-400 align-middle" />
          )}
        </div>

        {!pending && message.sources?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.sources.map((source, index) => (
              <span
                key={`${source.document_id}-${source.page}-${index}`}
                className="chip border-electric-500/20 bg-electric-500/[0.06] text-electric-200"
                title={source.preview}
              >
                <FileText size={11} />
                {source.document_name}
                {source.page ? ` · p.${source.page}` : ''}
                {typeof source.score === 'number' && (
                  <span className="text-[10px] text-slate-500">{source.score.toFixed(2)}</span>
                )}
              </span>
            ))}
          </div>
        )}

        {!isUser && !pending && !message.error && message.content && (
          <div className="mt-1.5 flex items-center gap-1 opacity-60 transition hover:opacity-100">
            <button
              type="button"
              onClick={copy}
              className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-300"
              aria-label="Copy answer"
            >
              {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
            </button>
            {onSpeak && (
              <button
                type="button"
                onClick={() => onSpeak(message)}
                disabled={!voiceAvailable || speaking}
                className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-300 disabled:opacity-40"
                aria-label="Read answer aloud"
                title={voiceAvailable ? 'Generate voice (external service)' : 'Voice is not configured'}
              >
                {speaking ? (
                  <Sparkles size={13} className="animate-pulse text-violet-300" />
                ) : (
                  <Volume2 size={13} />
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
