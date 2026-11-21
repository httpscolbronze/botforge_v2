import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownToLine,
  Boxes,
  CheckCircle2,
  Cpu,
  Loader2,
  Play,
  Power,
  RefreshCw,
  PlugZap,
} from 'lucide-react';
import { api } from '../../services/api.js';
import { formatBytes, formatRelative } from '../../services/format.js';
import StatusDot from '../shared/StatusDot.jsx';

const SUGGESTIONS = ['llama3.2:3b', 'llama3.2:1b', 'nomic-embed-text', 'llava'];

function describe(event) {
  if (!event) return '';
  if (event.status === 'error') return event.error || 'Pull failed.';
  if (event.status === 'success') return 'Download complete. Model is ready.';
  if (event.total) {
    const percent = Math.round((event.completed / event.total) * 100);
    return `${event.status || 'downloading'} · ${percent}% (${formatBytes(event.completed)} / ${formatBytes(event.total)})`;
  }
  return event.status || '';
}

function SelectRow({ label, hint, value, options, available, onChange, disabled }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <label className="text-[11px] font-medium text-slate-300">{label}</label>
        {available === true && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9.5px] text-emerald-300">
            <CheckCircle2 size={9} /> installed
          </span>
        )}
        {available === false && (
          <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[9.5px] text-amber-300">
            not installed
          </span>
        )}
      </div>
      <select
        className="input mt-1.5 font-mono text-[12px]"
        value={value || ''}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {value && !options.includes(value) && (
          <option value={value}>{value} (missing)</option>
        )}
        {options.length === 0 && <option value={value || ''}>{value || 'No models discovered'}</option>}
        {options.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      {hint && <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{hint}</p>}
    </div>
  );
}

export default function ModelManager({ models, onRefresh, notify }) {
  const [pullName, setPullName] = useState('llama3.2:3b');
  const [pulling, setPulling] = useState(false);
  const [pullLog, setPullLog] = useState([]);
  const [pullPercent, setPullPercent] = useState(0);
  const [confirmPull, setConfirmPull] = useState(false);
  const [busyModel, setBusyModel] = useState('');
  const [saving, setSaving] = useState('');
  const [selection, setSelection] = useState({
    chat_model: '',
    embedding_model: '',
    vision_model: '',
  });

  const connected = Boolean(models?.connected);
  const installed = models?.models || [];
  const running = new Set((models?.running || []).map((item) => item.name));
  const selected = models?.selected || {};
  const chatOptions = models?.chat_models || [];
  const embeddingOptions = models?.embedding_models || [];
  const visionOptions = models?.vision_models || [];

  useEffect(() => {
    setSelection({
      chat_model: selected.chat_model || '',
      embedding_model: selected.embedding_model || '',
      vision_model: selected.vision_model || '',
    });
  }, [selected.chat_model, selected.embedding_model, selected.vision_model]);

  const saveSelection = async (kind, value) => {
    if (!value) return;
    setSaving(kind);
    try {
      await api.saveSelectedModels({ [`${kind}_model`]: value });
      notify('success', `${kind === 'chat' ? 'Chat' : kind === 'embedding' ? 'Embedding' : 'Vision'} model set to ${value}.`);
      await onRefresh();
    } catch (error) {
      notify('error', error.message);
      setSelection((prev) => ({ ...prev, [`${kind}_model`]: selected[`${kind}_model`] || '' }));
    } finally {
      setSaving('');
    }
  };

  const retryConnection = async () => {
    setSaving('refresh');
    try {
      const result = await api.refreshModels();
      notify(
        result?.status?.connected ? 'success' : 'error',
        result?.status?.connected
          ? `Reconnected. ${result.status.counts.total} models installed.`
          : result?.status?.error || 'Ollama is still unreachable.',
      );
      await onRefresh();
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving('');
    }
  };

  const startPull = () => {
    const name = pullName.trim();
    if (!name || pulling) return;
    setConfirmPull(true);
  };

  const pull = async () => {
    const name = pullName.trim();
    if (!name || pulling) return;
    setConfirmPull(false);
    setPulling(true);
    setPullPercent(0);
    setPullLog([`Requesting ${name} from the Ollama registry…`]);
    try {
      await api.pullModel(name, (event) => {
        if (event.total && event.completed) {
          setPullPercent(Math.min(100, Math.round((event.completed / event.total) * 100)));
        }
        if (event.status === 'success') setPullPercent(100);
        const line = describe(event);
        if (line) setPullLog((prev) => [...prev.slice(-40), line]);
      });
      notify('success', `${name} is ready to use.`);
      await onRefresh();
    } catch (error) {
      setPullLog((prev) => [...prev, error.message]);
      notify('error', error.message);
    } finally {
      setPulling(false);
    }
  };

  const withModel = async (name, action, successMessage) => {
    setBusyModel(name);
    try {
      await action(name);
      notify('success', successMessage);
      await onRefresh();
    } catch (error) {
      notify('error', error.message);
    } finally {
      setBusyModel('');
    }
  };

  return (
    <div className="space-y-4">
      <div className="panel flex flex-wrap items-center gap-3 p-4">
        <StatusDot status={connected ? 'online' : 'offline'} />
        <div className="min-w-0">
          <p className="text-[12.5px] font-medium text-slate-100">
            {connected ? 'Ollama is reachable' : 'Ollama is not reachable'}
          </p>
          <p className="truncate text-[10.5px] text-slate-500">
            {models?.base_url || 'http://127.0.0.1:11434'}
            {models?.version ? ` · v${models.version}` : ''}
            {models?.discovered_at ? ` · scanned ${formatRelative(models.discovered_at)}` : ''}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="chip">{installed.length} installed</span>
          <button
            type="button"
            onClick={retryConnection}
            disabled={saving === 'refresh'}
            className="btn-secondary px-2.5 py-1.5 text-[11px]"
          >
            {saving === 'refresh' ? <Loader2 size={12} className="animate-spin" /> : <PlugZap size={12} />}
            Retry connection
          </button>
          <button type="button" onClick={onRefresh} className="btn-secondary px-2.5 py-1.5 text-[11px]">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {models?.error && (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-500/25 bg-rose-500/[0.08] px-3.5 py-3 text-[11.5px] leading-relaxed text-rose-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Model service error</p>
            <p className="mt-0.5 text-rose-200/80">{models.error}</p>
            <p className="mt-1 text-rose-200/60">
              Start Ollama with <span className="font-mono">ollama serve</span>, then click Retry
              connection. Chat is unavailable until a model is reachable.
            </p>
          </div>
        </div>
      )}

      {models?.warning && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-3.5 py-3 text-[11.5px] leading-relaxed text-amber-100/90">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Selected model is missing</p>
            <p className="mt-0.5 text-amber-100/80">{models.warning}</p>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
            <h3 className="section-title">Installed models</h3>
            <span className="text-[10px] text-slate-500">{running.size} loaded in memory</span>
          </div>
          {models === null ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2].map((key) => (
                <div key={key} className="h-14 animate-pulse rounded-xl bg-white/[0.04]" />
              ))}
            </div>
          ) : installed.length === 0 ? (
            <div className="p-8 text-center">
              <Boxes size={24} className="mx-auto mb-2 text-slate-600" />
              <p className="text-[12px] text-slate-400">No models installed yet.</p>
              <p className="mt-1 text-[11px] text-slate-500">
                Pull <span className="font-mono">llama3.2:3b</span> using the panel on the right.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-white/[0.05]">
              {installed.map((model) => {
                const active = model.name === selected.chat_model;
                const loaded = running.has(model.name);
                const busy = busyModel === model.name;
                return (
                  <li key={model.name} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-electric-300">
                      <Cpu size={15} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-[12.5px] font-medium text-slate-100">{model.name}</p>
                        <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[9.5px] text-slate-400">
                          {model.kind}
                        </span>
                        {active && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9.5px] text-emerald-300 ring-1 ring-inset ring-emerald-500/25">
                            <CheckCircle2 size={9} /> Chat default
                          </span>
                        )}
                        {model.name === selected.embedding_model && (
                          <span className="rounded-full bg-violet-500/10 px-2 py-0.5 text-[9.5px] text-violet-300">
                            Embeddings
                          </span>
                        )}
                        {model.name === selected.vision_model && (
                          <span className="rounded-full bg-electric-500/10 px-2 py-0.5 text-[9.5px] text-electric-300">
                            Vision
                          </span>
                        )}
                        {loaded && (
                          <span className="rounded-full bg-electric-500/10 px-2 py-0.5 text-[9.5px] text-electric-300">
                            Loaded
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        {[
                          model.parameter_size,
                          model.quantization_level,
                          model.size ? formatBytes(model.size) : null,
                          model.modified_at ? `updated ${formatRelative(model.modified_at)}` : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {model.kind === 'chat' && !active && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            withModel(
                              model.name,
                              api.setActiveModel,
                              `${model.name} is now the default chat model.`,
                            )
                          }
                          className="btn-secondary px-2.5 py-1.5 text-[10.5px]"
                        >
                          {busy ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
                          Use
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          withModel(model.name, api.loadModel, `${model.name} loaded into memory.`)
                        }
                        className="btn-ghost px-2 py-1.5 text-[10.5px]"
                        title="Warm the model so the first reply is fast"
                      >
                        <Play size={11} /> Load
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          withModel(model.name, api.unloadModel, `${model.name} unloaded.`)
                        }
                        className="btn-ghost px-2 py-1.5 text-[10.5px]"
                        title="Stop the model and free memory"
                      >
                        {busy ? <Loader2 size={11} className="animate-spin" /> : <Power size={11} />}
                        Unload
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="border-t border-white/[0.05] px-4 py-2.5 text-[10px] text-slate-600">
            Ollama loads models on demand. Load keeps one warm; unload frees memory immediately.
          </p>
        </div>

        <div className="space-y-4">
          <div className="panel p-4">
            <h3 className="section-title">Selected models</h3>
            <p className="mt-1 text-[10.5px] leading-relaxed text-slate-500">
              Saved in SQLite and restored on every restart. Each role is separate; changing chat
              never changes embeddings.
            </p>
            <div className="mt-3 space-y-2">
              <SelectRow
                label="Default chat model"
                value={selection.chat_model}
                options={chatOptions}
                available={selected.chat_available}
                disabled={saving === 'chat' || !connected}
                onChange={(value) => {
                  setSelection((prev) => ({ ...prev, chat_model: value }));
                  saveSelection('chat', value);
                }}
                hint="Used by clients whose agent has no model override."
              />
              <SelectRow
                label="Embedding model"
                value={selection.embedding_model}
                options={embeddingOptions}
                available={selected.embedding_available}
                disabled={saving === 'embedding' || !connected}
                onChange={(value) => {
                  setSelection((prev) => ({ ...prev, embedding_model: value }));
                  saveSelection('embedding', value);
                }}
                hint="Used for RAG. Re-upload documents after changing it (vectors must match)."
              />
              <SelectRow
                label="Vision model"
                value={selection.vision_model}
                options={visionOptions}
                available={selected.vision_available}
                disabled={saving === 'vision' || !connected}
                onChange={(value) => {
                  setSelection((prev) => ({ ...prev, vision_model: value }));
                  saveSelection('vision', value);
                }}
                hint="Used by screen analysis."
              />
            </div>
            {!connected && (
              <p className="mt-2 text-[10px] text-amber-300/80">
                Model selection is disabled while Ollama is offline so a missing model is never
                silently stored.
              </p>
            )}
            {selected.updated_at && (
              <p className="mt-2 text-[10px] text-slate-600">
                Last changed {new Date(selected.updated_at).toLocaleString()} by{' '}
                {selected.updated_by || 'admin'}
              </p>
            )}
          </div>

          <div className="panel p-4">
            <h3 className="section-title">Pull a model</h3>
            <p className="mt-1 text-[10.5px] leading-relaxed text-slate-500">
              Downloads from the Ollama registry to this machine. Nothing is sent anywhere else and
              nothing downloads without your confirmation.
            </p>
            <div className="mt-3 flex gap-2">
              <input
                className="input font-mono text-[12px]"
                value={pullName}
                onChange={(event) => setPullName(event.target.value)}
                placeholder="llama3.2:3b"
                disabled={pulling}
                aria-label="Model name to pull"
              />
              <button
                type="button"
                onClick={startPull}
                disabled={pulling || !pullName.trim()}
                className="btn-primary shrink-0 px-3 py-2 text-[11.5px]"
              >
                {pulling ? <Loader2 size={13} className="animate-spin" /> : <ArrowDownToLine size={13} />}
                Pull
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setPullName(suggestion)}
                  className="chip text-[10px] transition hover:border-electric-400/40 hover:text-electric-200"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            {confirmPull && (
              <div className="mt-3 rounded-xl border border-electric-500/30 bg-electric-500/[0.08] p-3">
                <p className="text-[11.5px] font-medium text-slate-100">
                  Download '{pullName.trim()}' now?
                </p>
                <p className="mt-1 text-[10.5px] leading-relaxed text-slate-400">
                  This can be several gigabytes and uses disk space and bandwidth on the host. The
                  download starts immediately and can take a while.
                </p>
                <div className="mt-2.5 flex gap-2">
                  <button type="button" onClick={pull} className="btn-primary px-3 py-1.5 text-[11px]">
                    Yes, download
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmPull(false)}
                    className="btn-secondary px-3 py-1.5 text-[11px]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {pulling && (
              <div className="mt-3">
                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-electric-500 to-violet-500 transition-all"
                    style={{ width: `${pullPercent}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {pullLog.length > 0 && (
            <div className="panel overflow-hidden">
              <div className="border-b border-white/[0.06] px-4 py-2.5">
                <h3 className="text-[12px] font-semibold text-slate-100">Pull progress</h3>
              </div>
              <div className="max-h-56 overflow-y-auto bg-forge-950/60 p-3 font-mono text-[10.5px] leading-relaxed text-slate-400">
                {pullLog.map((line, index) => (
                  <p key={`${line}-${index}`} className="truncate">
                    <span className="text-slate-600">{String(index + 1).padStart(2, '0')} </span>
                    {line}
                  </p>
                ))}
              </div>
            </div>
          )}

          <div className="panel p-4">
            <h3 className="section-title">Availability</h3>
            <div className="mt-2 space-y-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Chat models</span>
                <span className="text-slate-300">{chatOptions.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Embedding models</span>
                <span className="text-slate-300">{embeddingOptions.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Vision models</span>
                <span className="text-slate-300">{visionOptions.length}</span>
              </div>
            </div>
            <p className="mt-2.5 text-[10px] leading-relaxed text-slate-500">
              Classification is by model name (embed/bge/minilm, llava/vision/moondream). Any other
              installed Ollama model is treated as a chat model.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
