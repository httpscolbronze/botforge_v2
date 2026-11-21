import { useEffect, useRef } from 'react';
import { Lock, Sparkles, Database, ShieldCheck } from 'lucide-react';
import MessageBubble from './MessageBubble.jsx';

const SUGGESTIONS = [
  'Summarise the documents I uploaded.',
  'Draft a concise project brief for a new internal tool.',
  'What are the key risks in our current architecture?',
];

export default function ChatWindow({
  messages,
  streaming,
  persona,
  onSuggestion,
  onSpeak,
  speakingId,
  voiceAvailable,
  documentCount,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, streaming]);

  if (!messages.length) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="w-full max-w-2xl text-center">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-electric-600/30 via-indigo-600/20 to-violet-600/30 shadow-glow">
            <Sparkles size={24} className="text-indigo-200" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
            Ask <span className="gradient-text">{persona?.name || 'Alex'}</span> anything
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
            {persona?.persona || 'Your assistant'} · {persona?.tone || 'Professional'} tone
            {documentCount > 0
              ? ` · ${documentCount} document${documentCount === 1 ? '' : 's'} indexed`
              : ''}
          </p>

          <div className="mt-7 grid gap-2 text-left sm:grid-cols-3">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onSuggestion(suggestion)}
                className="panel-soft group rounded-xl p-3.5 text-left transition hover:border-electric-500/30 hover:bg-white/[0.04]"
              >
                <p className="text-[12.5px] leading-snug text-slate-300 group-hover:text-slate-100">
                  {suggestion}
                </p>
              </button>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Lock size={11} /> Inference runs on your machine
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Database size={11} /> Documents stay local
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck size={11} /> Host policy enforced server-side
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="scroll-region flex-1 overflow-y-auto px-4 py-6 sm:px-8">
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        {messages.map((message) => (
          <MessageBubble
            key={message.id || `${message.role}-${message.created_at}`}
            message={message}
            personaName={persona?.name}
            onSpeak={onSpeak}
            speaking={speakingId === message.id}
            voiceAvailable={voiceAvailable}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
