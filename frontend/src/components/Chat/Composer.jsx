import { useRef, useState } from 'react';
import {
  ArrowUp,
  FileText,
  Loader2,
  Monitor,
  Paperclip,
  Square,
  Wand2,
} from 'lucide-react';

export default function Composer({
  onSend,
  onStop,
  disabled,
  streaming,
  useDocuments,
  onToggleDocuments,
  documentCount,
  onOpenDocuments,
  onOpenScreen,
  onOpenPersona,
  model,
  modelOnline,
}) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled || streaming) return;
    onSend(text);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const handleChange = (event) => {
    setValue(event.target.value);
    const element = event.target;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  };

  return (
    <div className="border-t border-white/[0.06] bg-forge-950/60 px-4 py-4 backdrop-blur sm:px-8">
      <div className="mx-auto max-w-3xl">
        <div className="rounded-2xl border border-white/[0.08] bg-forge-900/90 p-2.5 shadow-panel transition focus-within:border-electric-500/40">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Message your assistant…  (Enter to send, Shift+Enter for a new line)"
            className="max-h-[200px] w-full resize-none bg-transparent px-2 py-2 text-[14.5px] text-slate-100 placeholder:text-slate-500 focus:outline-none"
            aria-label="Message"
          />

          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={onOpenDocuments}
              className="btn-ghost px-2 py-1.5 text-[11px]"
              title="Upload and manage documents"
            >
              <Paperclip size={13} />
              Attach
            </button>
            <button
              type="button"
              onClick={onToggleDocuments}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium transition ${
                useDocuments && documentCount > 0
                  ? 'bg-electric-500/10 text-electric-200 ring-1 ring-inset ring-electric-500/25'
                  : 'text-slate-500 hover:bg-white/5 hover:text-slate-300'
              }`}
              title="Include retrieved document context in the next answer"
            >
              <FileText size={13} />
              {useDocuments ? `Documents (${documentCount})` : 'Documents off'}
            </button>
            <button
              type="button"
              onClick={onOpenScreen}
              className="btn-ghost px-2 py-1.5 text-[11px]"
              title="Analyse a screenshot with the local vision model"
            >
              <Monitor size={13} />
              Screen
            </button>
            <button
              type="button"
              onClick={onOpenPersona}
              className="btn-ghost px-2 py-1.5 text-[11px]"
              title="Customise the assistant persona"
            >
              <Wand2 size={13} />
              Persona
            </button>

            <span className="ml-auto hidden items-center gap-1.5 pr-1 text-[10.5px] text-slate-500 sm:flex">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  modelOnline ? 'bg-emerald-400' : 'bg-rose-400'
                }`}
              />
              {model || 'no model'}
            </span>

            {streaming ? (
              <button
                type="button"
                onClick={onStop}
                className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.08] px-2.5 py-1.5 text-[11px] font-medium text-slate-200 hover:bg-white/[0.12]"
              >
                <Square size={12} /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!value.trim() || disabled}
                className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-electric-600 to-violet-600 p-2 text-white transition hover:from-electric-500 hover:to-violet-500 disabled:opacity-40"
                aria-label="Send message"
              >
                {disabled ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
              </button>
            )}
          </div>
        </div>
        <p className="mt-2 text-center text-[10.5px] text-slate-600">
          Local inference via Ollama · Responses may be inaccurate, verify important answers.
        </p>
      </div>
    </div>
  );
}
