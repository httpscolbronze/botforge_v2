import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Cpu,
  Database,
  FileText,
  Lock,
  RefreshCw,
  ScrollText,
  Server,
  ShieldCheck,
  Users,
} from 'lucide-react';
import StatusDot from '../shared/StatusDot.jsx';

function Stat({ icon: Icon, label, value, hint, tone = 'default' }) {
  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
        <Icon size={12} /> {label}
      </div>
      <p
        className={`mt-2 truncate text-[17px] font-semibold tracking-tight ${
          tone === 'warn' ? 'text-amber-300' : 'text-slate-100'
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 truncate text-[10.5px] text-slate-500">{hint}</p>}
    </div>
  );
}

export default function OverviewPanel({
  health,
  models,
  policy,
  info,
  clients,
  onNavigate,
  onRefresh,
}) {
  const ollamaOnline = Boolean(health?.ollama?.connected);
  const activeModel = health?.active_model;
  const warnings = [];
  if (!ollamaOnline) {
    warnings.push(
      health?.ollama?.error ||
        'Ollama is offline. Start it with `ollama serve` so clients can chat.',
    );
  }
  if (health?.warnings?.some?.((warning) => warning.includes('default admin password'))) {
    warnings.push('Host Mode is using the default admin password. Set a strong one in .env.');
  }
  if (policy && !policy.document_access) {
    warnings.push('Document access is currently disabled for all clients.');
  }

  return (
    <div className="space-y-5">
      <div className="panel relative overflow-hidden p-5">
        <div className="absolute -right-16 -top-20 h-48 w-48 rounded-full bg-electric-500/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-electric-300/80">
              Local-first AI infrastructure
            </p>
            <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-slate-100">
              Everything runs on this machine
            </h2>
            <p className="mt-1.5 text-[12px] leading-relaxed text-slate-400">
              {policy?.org_purpose ||
                'Set an organisational purpose in AI policies so every assistant follows your rules.'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="chip">
                <Lock size={10} /> Inference local
              </span>
              <span className={`chip ${policy?.document_access ? '' : 'border-amber-500/30 text-amber-200'}`}>
                <FileText size={10} /> Documents {policy?.document_access ? 'on' : 'off'}
              </span>
              <span className={`chip ${policy?.screen_analysis ? '' : 'border-amber-500/30 text-amber-200'}`}>
                <Cpu size={10} /> Screen analysis {policy?.screen_analysis ? 'on' : 'off'}
              </span>
            </div>
          </div>
          <button type="button" onClick={onRefresh} className="btn-secondary text-[11.5px]">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((warning) => (
            <div
              key={warning}
              className="flex items-start gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-3.5 py-2.5 text-[11.5px] leading-relaxed text-amber-100/85"
            >
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              {warning}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Server}
          label="Ollama"
          value={ollamaOnline ? 'Connected' : 'Offline'}
          hint={health?.ollama?.version ? `Version ${health.ollama.version}` : health?.ollama?.base_url}
          tone={ollamaOnline ? 'default' : 'warn'}
        />
        <Stat
          icon={Boxes}
          label="Active model"
          value={activeModel || 'None selected'}
          hint={`${models?.models?.length ?? 0} installed · ${models?.running?.length ?? 0} loaded`}
        />
        <Stat
          icon={Database}
          label="Document index"
          value={`${health?.vector_store?.chunks ?? 0} chunks`}
          hint={`${health?.documents?.count ?? 0} files · ${health?.vector_store?.backend || 'starting'}`}
        />
        <Stat
          icon={Users}
          label="Clients online"
          value={clients?.count ?? 0}
          hint="Checked in within 90 seconds"
        />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="section-title">Policy snapshot</h3>
            <button
              type="button"
              onClick={() => onNavigate('policies')}
              className="inline-flex items-center gap-1 text-[11px] text-electric-300 hover:text-electric-200"
            >
              Edit <ArrowRight size={11} />
            </button>
          </div>
          <div className="space-y-2 text-[11.5px]">
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">Organisational purpose</span>
              <span className="max-w-[60%] truncate text-right text-slate-300" title={policy?.org_purpose}>
                {policy?.org_purpose || 'Not set'}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">Allowed topics</span>
              <span className="text-slate-300">{policy?.allowed_topics?.length ?? 0}</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">Restricted topics</span>
              <span className="text-slate-300">{policy?.restricted_topics?.length ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">External voice</span>
              <span className={policy?.external_voice ? 'text-amber-300' : 'text-emerald-300'}>
                {policy?.external_voice ? 'Enabled (ElevenLabs)' : 'Disabled · fully local'}
              </span>
            </div>
          </div>
          <p className="mt-3 text-[10px] text-slate-600">
            Last updated {policy?.updated_at ? new Date(policy.updated_at).toLocaleString() : 'never'} ·
            enforced on every request
          </p>
        </div>

        <div className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="section-title">Local server</h3>
            <button
              type="button"
              onClick={() => onNavigate('server')}
              className="inline-flex items-center gap-1 text-[11px] text-electric-300 hover:text-electric-200"
            >
              Details <ArrowRight size={11} />
            </button>
          </div>
          <div className="space-y-2 text-[11.5px]">
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">API binding</span>
              <span className="font-mono text-[11px] text-slate-300">
                {health?.api ? `${health.api.host}:${health.api.port}` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">Loopback only</span>
              <StatusDot
                status={info?.api?.loopback_only ? 'online' : 'warn'}
                label={info?.api?.loopback_only ? 'Yes' : 'Exposed'}
                pulse={false}
              />
            </div>
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
              <span className="text-slate-500">Embeddings</span>
              <span className="text-slate-300">{info?.ollama?.embedding_model || 'nomic-embed-text'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Conversations</span>
              <span className="text-slate-300">{health?.conversations ?? 0}</span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-500/15 bg-emerald-500/[0.05] px-2.5 py-2">
            <ShieldCheck size={13} className="text-emerald-300" />
            <p className="text-[10.5px] text-emerald-200/80">
              Host policies are validated and enforced server-side.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {[
          { id: 'models', label: 'Manage models', icon: Boxes },
          { id: 'policies', label: 'Configure policies', icon: ShieldCheck },
          { id: 'logs', label: 'Inspect logs', icon: ScrollText },
        ].map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onNavigate(action.id)}
              className="panel-soft flex items-center gap-2.5 px-3.5 py-3 text-left text-[12px] text-slate-300 transition hover:border-electric-500/30 hover:text-slate-100"
            >
              <Icon size={15} className="text-electric-300" />
              {action.label}
              <ArrowRight size={12} className="ml-auto text-slate-600" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
