import { useState } from 'react';
import { CheckCircle2, Copy, Database, Globe, HardDrive, Lock, Server, ShieldCheck } from 'lucide-react';
import Modal from '../shared/Modal.jsx';
import { api } from '../../services/api.js';

function Row({ icon: Icon, label, value, tone = 'default' }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3.5 py-3">
      <Icon size={15} className="mt-0.5 shrink-0 text-slate-500" />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">{label}</p>
        <p className={`mt-0.5 text-[12.5px] ${tone === 'warn' ? 'text-amber-300' : 'text-slate-200'}`}>
          {value}
        </p>
      </div>
    </div>
  );
}

export default function SettingsPanel({ open, onClose, health, policy, voiceStatus }) {
  const [copied, setCopied] = useState(false);

  const copyWorkspace = async () => {
    try {
      await navigator.clipboard.writeText(api.getClientId());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked */
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Workspace settings"
      subtitle="What runs locally, what leaves your machine, and which policies apply."
      width="max-w-2xl"
    >
      <div className="space-y-3">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] px-4 py-3">
          <div className="flex items-center gap-2 text-[12px] font-medium text-emerald-200">
            <ShieldCheck size={14} /> Privacy-first by default
          </div>
          <p className="mt-1 text-[11.5px] leading-relaxed text-emerald-100/70">
            Chat inference, embeddings, document text and screenshots are processed by Ollama on
            the host machine. Nothing is sent to a third party unless your administrator enables
            external voice generation and you press the speak button.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <Row
            icon={Server}
            label="Local model"
            value={
              health?.ollama?.connected
                ? `${health.active_model} · Ollama ${health.ollama.version || ''}`.trim()
                : 'Ollama offline'
            }
            tone={health?.ollama?.connected ? 'default' : 'warn'}
          />
          <Row
            icon={Database}
            label="Vector store"
            value={`${health?.vector_store?.backend || 'initialising'} · ${
              health?.vector_store?.chunks ?? 0
            } chunks`}
          />
          <Row icon={HardDrive} label="Documents" value={`${health?.documents?.count ?? 0} indexed locally`} />
          <Row
            icon={Lock}
            label="Host policy"
            value={`Documents ${policy?.document_access ? 'allowed' : 'blocked'} · screens ${
              policy?.screen_analysis ? 'allowed' : 'blocked'
            }`}
          />
          <Row
            icon={Globe}
            label="External voice"
            value={
              !voiceStatus?.configured
                ? 'Not configured (fully local)'
                : voiceStatus?.enabled_by_policy
                  ? 'ElevenLabs available on demand'
                  : 'Configured but disabled by policy'
            }
            tone={voiceStatus?.configured ? 'warn' : 'default'}
          />
          <Row
            icon={Server}
            label="This workspace"
            value={api.getClientId()}
          />
        </div>

        <button type="button" onClick={copyWorkspace} className="btn-secondary w-full text-xs">
          {copied ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Copy size={14} />}
          {copied ? 'Workspace id copied' : 'Copy workspace id'}
        </button>

        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3">
          <p className="text-[11.5px] leading-relaxed text-amber-100/70">
            <span className="font-medium text-amber-200">MVP security note.</span> BotForge_v2 is
            designed for a trusted local network. Host Mode is password protected and policies are
            enforced server-side, but workspace isolation is not multi-tenant authentication. Do not
            expose this API to the public internet as-is.
          </p>
        </div>
      </div>
    </Modal>
  );
}
