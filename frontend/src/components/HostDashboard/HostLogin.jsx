import { useState } from 'react';
import { ArrowLeft, KeyRound, Loader2, Lock, Shield, Sparkles } from 'lucide-react';
import { api } from '../../services/api.js';

export default function HostLogin({ onSuccess, onSwitchMode, initialError = '' }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const data = await api.login(password);
      api.setAdminToken(data.token);
      onSuccess(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-electric-500 to-violet-600 shadow-glow">
            <Sparkles size={20} className="text-white" />
          </div>
          <div>
            <p className="text-base font-semibold tracking-tight text-slate-100">
              BotForge <span className="text-[11px] font-medium text-electric-300">v2</span>
            </p>
            <p className="text-[11px] text-slate-500">Host Mode · administrator access</p>
          </div>
        </div>

        <div className="panel p-6">
          <div className="mb-5 flex items-center gap-2.5">
            <div className="rounded-xl border border-white/10 bg-white/[0.04] p-2 text-electric-300">
              <Shield size={17} />
            </div>
            <div>
              <h1 className="text-[15px] font-semibold text-slate-100">Sign in to the control centre</h1>
              <p className="text-[11px] text-slate-500">
                Policies, models and server settings are administrator-only.
              </p>
            </div>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="admin-password">
                Administrator password
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  id="admin-password"
                  type="password"
                  autoFocus
                  autoComplete="current-password"
                  className="input pl-9"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter BOTFORGE_ADMIN_PASSWORD"
                  required
                />
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5 text-[12px] leading-relaxed text-rose-200">
                {error}
              </div>
            )}

            <button type="submit" className="btn-primary w-full py-2.5" disabled={busy || !password}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
              {busy ? 'Verifying…' : 'Unlock Host Mode'}
            </button>
          </form>

          <div className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3.5 py-2.5">
            <p className="text-[10.5px] leading-relaxed text-slate-500">
              The password comes from <code className="font-mono text-slate-400">BOTFORGE_ADMIN_PASSWORD</code>{' '}
              in the server <code className="font-mono text-slate-400">.env</code>. First run uses{' '}
              <code className="font-mono text-slate-400">botforge-admin</code> — change it before
              sharing this machine.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onSwitchMode}
          className="mt-5 inline-flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-300"
        >
          <ArrowLeft size={13} /> Back to the AI workspace
        </button>
      </div>
    </div>
  );
}
