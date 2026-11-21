import { useCallback, useEffect, useState } from 'react';
import {
  Archive,
  Cpu,
  Database,
  HardDrive,
  Loader2,
  Lock,
  MemoryStick,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldCheck,
  Terminal,
} from 'lucide-react';
import { api } from '../../services/api.js';
import { formatBytes, formatRelative } from '../../services/format.js';

function Meter({ label, value, suffix = '%', tone }) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div>
      <div className="flex items-center justify-between text-[10.5px]">
        <span className="text-slate-500">{label}</span>
        <span className="text-slate-300">
          {safe}
          {suffix}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
        <div
          className={`h-full rounded-full ${tone || 'bg-gradient-to-r from-electric-500 to-violet-500'}`}
          style={{ width: `${safe}%` }}
        />
      </div>
    </div>
  );
}

export default function ServerPanel({ info, health, onRefresh, notify }) {
  const [copied, setCopied] = useState(false);
  const [backups, setBackups] = useState(null);
  const [backupBusy, setBackupBusy] = useState('');
  const [backupError, setBackupError] = useState('');
  const [preferences, setPreferences] = useState(null);
  const [preferencesBusy, setPreferencesBusy] = useState(false);
  const resources = info?.resources;

  useEffect(() => {
    api
      .settings()
      .then((data) => setPreferences(data.settings))
      .catch(() => setPreferences(null));
  }, []);

  const savePreferences = async () => {
    if (!preferences) return;
    setPreferencesBusy(true);
    try {
      const data = await api.saveSettings({
        chat_history_limit: Number(preferences.chat_history_limit),
        document_top_k: Number(preferences.document_top_k),
      });
      setPreferences(data.settings);
      notify?.('success', 'Preferences saved to SQLite.');
    } catch (error) {
      notify?.('error', error.message);
    } finally {
      setPreferencesBusy(false);
    }
  };

  const loadBackups = useCallback(async () => {
    try {
      const data = await api.backups();
      setBackups(data.backups || []);
      setBackupError('');
    } catch (error) {
      setBackups([]);
      setBackupError(error.message);
    }
  }, []);

  useEffect(() => {
    loadBackups();
  }, [loadBackups]);

  const makeBackup = async () => {
    setBackupBusy('create');
    setBackupError('');
    try {
      const result = await api.createBackup(true);
      await loadBackups();
      onRefresh?.();
      notify?.('success', `Backup created: ${result?.backup?.id || 'ok'}`);
    } catch (error) {
      setBackupError(error.message);
      notify?.('error', error.message);
    } finally {
      setBackupBusy('');
    }
  };

  const restore = async (backup) => {
    const confirmed = window.confirm(
      `Restore ${backup.id}?\n\nThis replaces the current database, documents and vectors. ` +
        'A safety backup of the current state is created first. BotForge may need a refresh afterwards.',
    );
    if (!confirmed) return;
    setBackupBusy(backup.id);
    setBackupError('');
    try {
      const result = await api.restoreBackup(backup.id);
      await loadBackups();
      onRefresh?.();
      notify?.('success', `Restored ${backup.id}. Reload the page to see restored data.`);
      if (result?.warnings?.length) setBackupError(result.warnings.join(' '));
    } catch (error) {
      setBackupError(error.message);
      notify?.('error', error.message);
    } finally {
      setBackupBusy('');
    }
  };

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(info?.api?.bind || 'http://127.0.0.1:8000');
      setCopied(true);
      notify?.('success', 'API address copied.');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify?.('error', 'Clipboard access was blocked.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
            <Server size={12} /> Local API
          </div>
          <p className="mt-2 break-all font-mono text-[12px] text-slate-100">
            {info?.api?.bind || 'http://127.0.0.1:8000'}
          </p>
          <div className="mt-2 flex items-center gap-2">
            <span className="chip">
              <Lock size={10} /> {info?.api?.loopback_only ? 'Loopback only' : 'Exposed binding'}
            </span>
            <button type="button" onClick={copyAddress} className="text-[10px] text-electric-300 hover:text-electric-200">
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
            <Database size={12} /> Vector store
          </div>
          <p className="mt-2 text-[15px] font-semibold text-slate-100">
            {info?.vector_store?.backend || health?.vector_store?.backend || 'initialising'}
          </p>
          <p className="mt-1 text-[10.5px] text-slate-500">
            {info?.vector_store?.chunks ?? health?.vector_store?.chunks ?? 0} chunks · local disk
          </p>
        </div>
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
            <Terminal size={12} /> Runtime
          </div>
          <p className="mt-2 text-[12px] text-slate-100">Python {info?.runtime?.python || '—'}</p>
          <p className="mt-0.5 truncate text-[10.5px] text-slate-500" title={info?.runtime?.platform}>
            {info?.runtime?.platform || ''}
          </p>
          <p className="mt-1 text-[10px] text-slate-600">
            Uptime {Math.round((info?.runtime?.uptime_seconds || 0) / 60)} min
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="section-title">Resources</h3>
            <button type="button" onClick={onRefresh} className="btn-ghost px-2 py-1 text-[10.5px]">
              <RefreshCw size={11} /> Refresh
            </button>
          </div>
          {resources?.available ? (
            <div className="space-y-3">
              <Meter label={`CPU (${resources.cpu_count} cores)`} value={resources.cpu_percent} />
              <Meter label="Memory used" value={resources.memory_used_percent} />
              <div className="flex items-center gap-4 pt-1 text-[10.5px] text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <MemoryStick size={11} /> {resources.memory_total_mb} MB total
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <HardDrive size={11} /> {resources.disk_free_gb} GB free
                </span>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-slate-500">
              {resources?.error || 'Resource metrics are not available in this environment.'}
            </p>
          )}
          <p className="mt-3 border-t border-white/[0.05] pt-2.5 text-[10px] text-slate-600">
            Model inference is the main consumer; large models need several GB of RAM.
          </p>
        </div>

        <div className="panel p-4">
          <h3 className="section-title">Configuration</h3>
          <div className="mt-3 space-y-2 text-[11.5px]">
            {[
              ['Data directory', info?.data_dir],
              ['Ollama endpoint', info?.ollama?.base_url],
              ['Default chat model', info?.ollama?.selected_chat_model],
              ['Embedding model', info?.ollama?.selected_embedding_model],
              ['Vision model', info?.ollama?.selected_vision_model],
              ['Conversations', info?.counts?.conversations],
              ['Personas', info?.counts?.personas],
            ].map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-4 border-b border-white/[0.05] pb-2 last:border-0">
                <span className="text-slate-500">{label}</span>
                <span className="max-w-[65%] break-all text-right font-mono text-[10.5px] text-slate-300">
                  {value ?? '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="section-title flex items-center gap-2">
            <Archive size={14} className="text-electric-300" /> Database &amp; backups
          </h3>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadBackups}
              className="btn-ghost px-2 py-1 text-[10.5px]"
              disabled={Boolean(backupBusy)}
            >
              <RefreshCw size={11} /> Refresh
            </button>
            <button
              type="button"
              onClick={makeBackup}
              className="btn-secondary px-2.5 py-1.5 text-[10.5px]"
              disabled={Boolean(backupBusy)}
            >
              {backupBusy === 'create' ? (
                <Loader2 size={11} className="animate-spin" />
              ) : (
                <Archive size={11} />
              )}
              Create backup
            </button>
          </div>
        </div>
        <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">SQLite database</p>
            <p className="mt-1 break-all font-mono text-[10px] text-slate-300">
              {info?.database?.path || health?.database?.path || '—'}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">
              {formatBytes(info?.database?.size_bytes || health?.database?.size_bytes || 0)} ·{' '}
              {(info?.database?.migrations || []).length} migrations applied
            </p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">Stored data</p>
            <p className="mt-1 text-[11px] text-slate-300">
              {info?.counts?.conversations ?? health?.conversations ?? 0} conversations ·{' '}
              {info?.counts?.personas ?? health?.personas ?? 0} personas ·{' '}
              {info?.counts?.documents ?? health?.documents?.count ?? 0} documents
            </p>
            <p className="mt-1 text-[10px] text-slate-500">
              Integrity: {info?.database?.integrity || 'ok'}
            </p>
          </div>
        </div>

        {backupError && (
          <div className="mt-3 rounded-xl border border-rose-500/25 bg-rose-500/[0.08] px-3 py-2 text-[11px] text-rose-200">
            {backupError}
          </div>
        )}

        <div className="mt-3 overflow-hidden rounded-xl border border-white/[0.06]">
          {backups === null ? (
            <p className="px-3 py-3 text-[11px] text-slate-500">Loading backups…</p>
          ) : backups.length === 0 ? (
            <p className="px-3 py-3 text-[11px] text-slate-500">
              No backups yet. Create one before changing models or policies.
            </p>
          ) : (
            <ul className="divide-y divide-white/[0.05]">
              {backups.map((backup) => (
                <li
                  key={backup.id}
                  className="flex flex-wrap items-center gap-2 px-3 py-2.5 text-[11px]"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-[10.5px] text-slate-300">{backup.id}</p>
                    <p className="text-[10px] text-slate-500">
                      {formatRelative(backup.created_at)} · {formatBytes(backup.size_bytes)} ·{' '}
                      {backup.includes_vectors ? 'with vectors' : 'database only'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => restore(backup)}
                    disabled={Boolean(backupBusy)}
                    className="btn-ghost px-2 py-1.5 text-[10.5px]"
                  >
                    {backupBusy === backup.id ? (
                      <Loader2 size={11} className="animate-spin" />
                    ) : (
                      <RotateCcw size={11} />
                    )}
                    Restore
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-600">
          Backups are zip archives in {info?.database?.backups_dir || 'the data/backups folder'}, kept
          on this machine. Restoring never deletes the current backup set and takes a safety snapshot
          first.
        </p>
      </div>

      <div className="panel p-4">
        <h3 className="section-title">Application preferences</h3>
        {preferences ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="pref-history">
                Messages kept as chat history
              </label>
              <input
                id="pref-history"
                type="number"
                min={1}
                max={40}
                className="input"
                value={preferences.chat_history_limit}
                onChange={(event) =>
                  setPreferences((prev) => ({ ...prev, chat_history_limit: event.target.value }))
                }
              />
            </div>
            <div>
              <label className="label" htmlFor="pref-topk">
                Document chunks retrieved per question
              </label>
              <input
                id="pref-topk"
                type="number"
                min={1}
                max={12}
                className="input"
                value={preferences.document_top_k}
                onChange={(event) =>
                  setPreferences((prev) => ({ ...prev, document_top_k: event.target.value }))
                }
              />
            </div>
            <div className="sm:col-span-2 flex items-center gap-2">
              <button
                type="button"
                onClick={savePreferences}
                disabled={preferencesBusy}
                className="btn-primary px-3 py-1.5 text-[11px]"
              >
                {preferencesBusy && <Loader2 size={12} className="animate-spin" />}
                Save preferences
              </button>
              <span className="text-[10px] text-slate-600">Stored in app_settings.</span>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-[11px] text-slate-500">Preferences are unavailable.</p>
        )}
      </div>

      <div className="panel p-4">
        <h3 className="section-title flex items-center gap-2">
          <ShieldCheck size={14} className="text-emerald-300" /> Security posture
        </h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">Admin password</p>
            <p className={`mt-1 text-[11.5px] ${info?.security?.default_admin_password ? 'text-amber-300' : 'text-emerald-300'}`}>
              {info?.security?.default_admin_password ? 'Default value in use — change it' : 'Custom value configured'}
            </p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">Session secret</p>
            <p className={`mt-1 text-[11.5px] ${info?.security?.default_session_secret ? 'text-amber-300' : 'text-emerald-300'}`}>
              {info?.security?.default_session_secret ? 'Development default' : 'Custom secret'}
            </p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">Inference</p>
            <p className="mt-1 text-[11.5px] text-emerald-300">Local Ollama only</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-slate-500">External services</p>
            <p className="mt-1 text-[11.5px] text-slate-300">
              ElevenLabs {policyVoiceLabel(health)}
            </p>
          </div>
        </div>
        <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
          <Cpu size={10} className="mr-1 inline" />
          This MVP is not a hardened multi-tenant deployment: keep the API on loopback and use a
          reverse proxy with TLS and authentication before exposing it.
        </p>
      </div>
    </div>
  );
}

function policyVoiceLabel(health) {
  if (!health?.voice) return 'unknown';
  if (!health.voice.configured) return 'not configured (off)';
  return health.voice.enabled_by_policy ? 'enabled on demand' : 'configured but blocked';
}
