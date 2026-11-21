import { useEffect, useState } from 'react';
import {
  Ban,
  CheckCircle2,
  FileText,
  Globe,
  Loader2,
  Monitor,
  Plus,
  Save,
  ShieldCheck,
  X,
} from 'lucide-react';
import { api } from '../../services/api.js';

function TagEditor({ label, hint, values, onChange, tone = 'default' }) {
  const [draft, setDraft] = useState('');

  const add = () => {
    const value = draft.trim().replace(/\s+/g, ' ');
    if (!value) return;
    if (values.some((item) => item.toLowerCase() === value.toLowerCase())) {
      setDraft('');
      return;
    }
    onChange([...values, value]);
    setDraft('');
  };

  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex gap-2">
        <input
          className="input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault();
              add();
            }
          }}
          placeholder={hint}
          maxLength={120}
        />
        <button type="button" onClick={add} className="btn-secondary shrink-0 px-3">
          <Plus size={14} /> Add
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {values.length === 0 && <span className="text-[11px] text-slate-600">None configured.</span>}
        {values.map((value) => (
          <span
            key={value}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] ${
              tone === 'danger'
                ? 'border-rose-500/25 bg-rose-500/[0.08] text-rose-200'
                : 'border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-200'
            }`}
          >
            {value}
            <button
              type="button"
              onClick={() => onChange(values.filter((item) => item !== value))}
              className="opacity-60 hover:opacity-100"
              aria-label={`Remove ${value}`}
            >
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function Toggle({ checked, onChange, title, description, icon: Icon, tone = 'default' }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`flex w-full items-start gap-3 rounded-xl border p-3.5 text-left transition ${
        checked
          ? 'border-electric-500/25 bg-electric-500/[0.05]'
          : 'border-white/[0.07] bg-white/[0.02] hover:border-white/15'
      }`}
    >
      <div
        className={`mt-0.5 rounded-lg p-1.5 ${
          checked ? 'bg-electric-500/15 text-electric-300' : 'bg-white/[0.04] text-slate-500'
        }`}
      >
        <Icon size={14} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-medium text-slate-200">{title}</p>
        <p className="mt-0.5 text-[10.5px] leading-relaxed text-slate-500">{description}</p>
      </div>
      <span
        className={`mt-1 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition ${
          checked ? 'bg-electric-500' : 'bg-white/10'
        }`}
      >
        <span
          className={`h-4 w-4 rounded-full bg-white transition ${checked ? 'translate-x-4' : ''}`}
        />
      </span>
    </button>
  );
}

const EMPTY = {
  org_purpose: '',
  allowed_topics: [],
  restricted_topics: [],
  document_access: true,
  screen_analysis: true,
  external_voice: true,
  system_rules: '',
  max_context_chunks: 4,
};

export default function PolicyManager({ policy, onSaved, notify }) {
  const [form, setForm] = useState(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!policy) return;
    setForm({
      org_purpose: policy.org_purpose || '',
      allowed_topics: policy.allowed_topics || [],
      restricted_topics: policy.restricted_topics || [],
      document_access: Boolean(policy.document_access),
      screen_analysis: Boolean(policy.screen_analysis),
      external_voice: Boolean(policy.external_voice),
      system_rules: policy.system_rules || '',
      max_context_chunks: policy.max_context_chunks || 4,
    });
    setDirty(false);
  }, [policy]);

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const data = await api.savePolicies(form);
      onSaved?.(data.policy);
      setDirty(false);
      notify('success', 'AI policy saved. It applies to the next request immediately.');
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="panel flex flex-wrap items-center gap-3 p-4">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.07] p-2 text-emerald-300">
          <ShieldCheck size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-medium text-slate-100">Host policy is authoritative</p>
          <p className="text-[10.5px] leading-relaxed text-slate-500">
            Stored on the server and prepended to every system prompt. Client personas and document
            content cannot override it.
          </p>
        </div>
        <button type="button" onClick={save} disabled={saving || !dirty} className="btn-primary text-[12px]">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {saving ? 'Saving…' : dirty ? 'Save policy' : 'Saved'}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel space-y-4 p-4">
          <div>
            <label className="label" htmlFor="org-purpose">
              Organisational purpose
            </label>
            <textarea
              id="org-purpose"
              className="input min-h-[92px] resize-y"
              value={form.org_purpose}
              maxLength={2000}
              onChange={(event) => update('org_purpose', event.target.value)}
              placeholder="What is the assistant for? Who does it serve?"
            />
            <p className="mt-1 text-[10px] text-slate-600">{form.org_purpose.length}/2000</p>
          </div>

          <TagEditor
            label="Allowed topics"
            hint="engineering, product, operations…"
            values={form.allowed_topics}
            onChange={(values) => update('allowed_topics', values)}
          />

          <TagEditor
            label="Restricted topics"
            hint="medical diagnosis, legal advice…"
            values={form.restricted_topics}
            onChange={(values) => update('restricted_topics', values)}
            tone="danger"
          />
          <p className="flex items-start gap-1.5 text-[10px] leading-relaxed text-slate-600">
            <Ban size={11} className="mt-0.5 shrink-0" />
            Restricted topics are blocked server-side before the model is called, not just
            discouraged in the prompt.
          </p>

          <div>
            <label className="label" htmlFor="system-rules">
              Additional mandatory rules
            </label>
            <textarea
              id="system-rules"
              className="input min-h-[100px] resize-y font-mono text-[11.5px]"
              value={form.system_rules}
              maxLength={4000}
              onChange={(event) => update('system_rules', event.target.value)}
            />
          </div>
        </div>

        <div className="space-y-4">
          <div className="panel space-y-2.5 p-4">
            <h3 className="section-title mb-1">Capabilities</h3>
            <Toggle
              icon={FileText}
              checked={form.document_access}
              onChange={(value) => update('document_access', value)}
              title="Document access"
              description="Allow uploads and retrieval-augmented answers from local files."
            />
            <Toggle
              icon={Monitor}
              checked={form.screen_analysis}
              onChange={(value) => update('screen_analysis', value)}
              title="Screen analysis"
              description="Allow screenshots to be analysed by the local vision model."
            />
            <Toggle
              icon={Globe}
              checked={form.external_voice}
              onChange={(value) => update('external_voice', value)}
              title="External voice generation"
              description="Allow ElevenLabs text-to-speech. This is the only external integration."
            />
          </div>

          <div className="panel p-4">
            <div className="flex items-center justify-between">
              <label className="label mb-0" htmlFor="chunks">
                Context chunks per answer
              </label>
              <span className="text-[12px] font-semibold text-electric-300">
                {form.max_context_chunks}
              </span>
            </div>
            <input
              id="chunks"
              type="range"
              min={1}
              max={12}
              value={form.max_context_chunks}
              onChange={(event) => update('max_context_chunks', Number(event.target.value))}
              className="mt-2 w-full accent-electric-500"
            />
            <p className="mt-1 text-[10px] text-slate-600">
              More chunks means more context and a slower, larger prompt. 4 is a good default for
              llama3.2:3b.
            </p>
          </div>

          <div className="panel p-4">
            <h3 className="section-title">Enforcement pipeline</h3>
            <ol className="mt-2 space-y-2 text-[11px] leading-relaxed text-slate-400">
              <li className="flex gap-2">
                <span className="text-electric-400">1.</span> Restricted-topic check runs before
                inference.
              </li>
              <li className="flex gap-2">
                <span className="text-electric-400">2.</span> Policy block is prepended ahead of the
                persona block.
              </li>
              <li className="flex gap-2">
                <span className="text-electric-400">3.</span> Document excerpts are wrapped as
                untrusted data.
              </li>
              <li className="flex gap-2">
                <span className="text-electric-400">4.</span> Disabled capabilities are refused by
                the API, not hidden in the UI.
              </li>
            </ol>
            <p className="mt-3 border-t border-white/[0.05] pt-2.5 text-[10px] text-slate-600">
              Last saved:{' '}
              {policy?.updated_at ? new Date(policy.updated_at).toLocaleString() : 'not yet'}
            </p>
          </div>
        </div>
      </div>

      {dirty && (
        <div className="sticky bottom-4 flex items-center gap-3 rounded-xl border border-electric-500/25 bg-forge-900/95 px-4 py-3 shadow-panel backdrop-blur">
          <p className="flex-1 text-[11.5px] text-slate-300">
            You have unsaved policy changes. Clients keep using the previous policy until you save.
          </p>
          <button type="button" onClick={save} disabled={saving} className="btn-primary text-[12px]">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save changes
          </button>
          {!saving && policy && (
            <button
              type="button"
              onClick={() => {
                setForm({ ...policy });
                setDirty(false);
              }}
              className="btn-ghost text-[11px]"
            >
              <X size={13} /> Discard
            </button>
          )}
        </div>
      )}

      {!dirty && policy?.updated_at && (
        <p className="flex items-center gap-1.5 text-[11px] text-emerald-300/80">
          <CheckCircle2 size={12} /> Policy is saved and active.
        </p>
      )}
    </div>
  );
}
