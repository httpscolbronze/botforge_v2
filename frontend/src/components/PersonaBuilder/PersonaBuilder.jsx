import { useEffect, useState } from 'react';
import { Check, Loader2, Plus, Sparkles, Trash2, Wand2 } from 'lucide-react';
import Modal from '../shared/Modal.jsx';

const EMPTY = {
  name: 'Alex',
  persona: 'Senior Software Engineer',
  tone: 'Professional',
  response_style: 'Detailed and explanatory',
  expertise: 'Python, APIs and System Design',
  language: 'English',
  additional_instructions: '',
  chat_model: '',
};

const TONES = ['Professional', 'Friendly', 'Direct', 'Formal', 'Witty', 'Empathetic'];
const STYLES = [
  'Concise',
  'Detailed and explanatory',
  'Bullet points',
  'Step-by-step',
  'Executive summary',
];

export default function PersonaBuilder({
  open,
  onClose,
  personas,
  activePersona,
  onSave,
  onDelete,
  saving,
  error,
  models = [],
  defaultModel = '',
}) {
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    if (!open) return;
    if (activePersona) {
      setForm({
        name: activePersona.name || '',
        persona: activePersona.persona || '',
        tone: activePersona.tone || '',
        response_style: activePersona.response_style || '',
        expertise: activePersona.expertise || '',
        language: activePersona.language || '',
        additional_instructions: activePersona.additional_instructions || '',
        chat_model: activePersona.chat_model || '',
      });
      setEditingId(activePersona.id || null);
    } else {
      setForm(EMPTY);
      setEditingId(null);
    }
  }, [open, activePersona]);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const loadPersona = (persona) => {
    setForm({
      name: persona.name || '',
      persona: persona.persona || '',
      tone: persona.tone || '',
      response_style: persona.response_style || '',
      expertise: persona.expertise || '',
      language: persona.language || '',
      additional_instructions: persona.additional_instructions || '',
      chat_model: persona.chat_model || '',
    });
    setEditingId(persona.id);
  };

  const startNew = () => {
    setForm(EMPTY);
    setEditingId(null);
  };

  const submit = (event) => {
    event.preventDefault();
    onSave({ ...form, ...(editingId ? { id: editingId } : {}) });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Persona builder"
      subtitle="Customise how your assistant introduces itself, writes and reasons."
      width="max-w-3xl"
    >
      <div className="grid gap-6 md:grid-cols-[210px_1fr]">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="label mb-0">Saved personas</span>
            <button
              type="button"
              onClick={startNew}
              className="rounded-md p-1 text-slate-400 hover:bg-white/5 hover:text-slate-200"
              aria-label="New persona"
            >
              <Plus size={14} />
            </button>
          </div>
          <div className="space-y-1">
            {personas.length === 0 && (
              <p className="rounded-lg border border-dashed border-white/10 p-3 text-[11px] text-slate-500">
                No personas saved yet. You are using the default assistant.
              </p>
            )}
            {personas.map((persona) => (
              <button
                key={persona.id}
                type="button"
                onClick={() => loadPersona(persona)}
                className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition ${
                  editingId === persona.id
                    ? 'bg-electric-500/10 text-electric-100 ring-1 ring-inset ring-electric-500/25'
                    : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                }`}
              >
                <Sparkles size={12} className="shrink-0 text-violet-300" />
                <span className="min-w-0 flex-1 truncate">{persona.name || 'Assistant'}</span>
              </button>
            ))}
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
            <p className="text-[11px] leading-relaxed text-slate-500">
              <span className="font-medium text-slate-400">Host policy wins.</span> Persona
              instructions are combined with administrator rules, but can never override them.
            </p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="persona-name">
                Assistant name
              </label>
              <input
                id="persona-name"
                className="input"
                value={form.name}
                onChange={update('name')}
                maxLength={120}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="persona-persona">
                Persona / role
              </label>
              <input
                id="persona-persona"
                className="input"
                value={form.persona}
                onChange={update('persona')}
                maxLength={600}
                placeholder="Senior Software Engineer"
              />
            </div>
            <div>
              <label className="label" htmlFor="persona-tone">
                Tone
              </label>
              <input
                id="persona-tone"
                className="input"
                list="tone-options"
                value={form.tone}
                onChange={update('tone')}
                maxLength={120}
              />
              <datalist id="tone-options">
                {TONES.map((tone) => (
                  <option key={tone} value={tone} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="label" htmlFor="persona-style">
                Response style
              </label>
              <input
                id="persona-style"
                className="input"
                list="style-options"
                value={form.response_style}
                onChange={update('response_style')}
                maxLength={120}
              />
              <datalist id="style-options">
                {STYLES.map((style) => (
                  <option key={style} value={style} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="persona-expertise">
                Expertise
              </label>
              <input
                id="persona-expertise"
                className="input"
                value={form.expertise}
                onChange={update('expertise')}
                maxLength={600}
                placeholder="Python, APIs and System Design"
              />
            </div>
            <div>
              <label className="label" htmlFor="persona-language">
                Language
              </label>
              <input
                id="persona-language"
                className="input"
                value={form.language}
                onChange={update('language')}
                maxLength={120}
                placeholder="English"
              />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="persona-model">
              Chat model for this agent
            </label>
            <select
              id="persona-model"
              className="input font-mono text-[12px]"
              value={form.chat_model || ''}
              onChange={update('chat_model')}
            >
              <option value="">
                Host default{defaultModel ? ` (${defaultModel})` : ''}
              </option>
              {models.map((model) => (
                <option key={model.name || model} value={model.name || model}>
                  {model.name || model}
                </option>
              ))}
              {form.chat_model && !models.some((model) => (model.name || model) === form.chat_model) && (
                <option value={form.chat_model}>{form.chat_model} (not installed)</option>
              )}
            </select>
            <p className="mt-1 text-[10.5px] text-slate-500">
              Saved in the agent configuration. Only affects this persona; the host default and
              embedding model are unchanged.
            </p>
          </div>

          <div>
            <label className="label" htmlFor="persona-instructions">
              Additional instructions <span className="normal-case text-slate-600">(optional)</span>
            </label>
            <textarea
              id="persona-instructions"
              className="input min-h-[96px] resize-y"
              value={form.additional_instructions}
              onChange={update('additional_instructions')}
              maxLength={2000}
              placeholder="E.g. Always show a short summary first, then the details."
            />
          </div>

          {error && (
            <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200">
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              Save &amp; use persona
            </button>
            {editingId && onDelete && (
              <button
                type="button"
                className="btn-danger"
                onClick={() => onDelete(editingId)}
                disabled={saving}
              >
                <Trash2 size={14} /> Delete
              </button>
            )}
            <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-slate-500">
              <Wand2 size={11} /> Stored locally
            </span>
          </div>
        </form>
      </div>
    </Modal>
  );
}
