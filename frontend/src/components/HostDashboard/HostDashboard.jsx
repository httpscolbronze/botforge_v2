import { useCallback, useEffect, useState } from 'react';
import {
  Boxes,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Server,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react';
import { api } from '../../services/api.js';
import StatusDot from '../shared/StatusDot.jsx';
import OverviewPanel from './OverviewPanel.jsx';
import ModelManager from '../ModelManager/ModelManager.jsx';
import PolicyManager from '../PolicyManager/PolicyManager.jsx';
import ServerPanel from './ServerPanel.jsx';
import ClientsPanel from './ClientsPanel.jsx';
import LogsPanel from './LogsPanel.jsx';

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'models', label: 'Models', icon: Boxes },
  { id: 'policies', label: 'AI policies', icon: ShieldCheck },
  { id: 'server', label: 'Server', icon: Server },
  { id: 'clients', label: 'Clients', icon: Users },
  { id: 'logs', label: 'Logs', icon: ScrollText },
];

const TITLES = {
  overview: { title: 'Control centre', subtitle: 'Local inference health, policy and usage at a glance.' },
  models: { title: 'Model management', subtitle: 'Installed Ollama models, active model and downloads.' },
  policies: { title: 'AI policy manager', subtitle: 'Organisation-wide rules enforced on every request.' },
  server: { title: 'Server management', subtitle: 'Bindings, storage, resources and runtime details.' },
  clients: { title: 'Connected clients', subtitle: 'Workspaces that checked in during the last 90 seconds.' },
  logs: { title: 'Server logs', subtitle: 'Recent backend activity, kept in memory.' },
};

export default function HostDashboard({ onLogout, onSwitchMode }) {
  const [tab, setTab] = useState('overview');
  const [health, setHealth] = useState(null);
  const [models, setModels] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [info, setInfo] = useState(null);
  const [clients, setClients] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [notice, setNotice] = useState(null);
  const [navOpen, setNavOpen] = useState(false);

  const notify = useCallback((type, message) => {
    setNotice({ type, message });
    window.setTimeout(() => setNotice(null), 4500);
  }, []);

  const handleError = useCallback(
    (error) => {
      if (error?.status === 401) {
        onLogout('Your administrator session expired. Please sign in again.');
        return true;
      }
      return false;
    },
    [onLogout],
  );

  const loadHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const loadModels = useCallback(async () => {
    try {
      setModels(await api.models());
    } catch (error) {
      if (!handleError(error)) setModels({ connected: false, error: error.message, models: [] });
    }
  }, [handleError]);

  const loadPolicy = useCallback(async () => {
    try {
      const data = await api.policies();
      setPolicy(data.policy);
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const loadInfo = useCallback(async () => {
    try {
      setInfo(await api.systemInfo());
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const loadClients = useCallback(async () => {
    try {
      setClients(await api.clients());
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const data = await api.logs(200);
      setLogs(data.logs || []);
    } catch (error) {
      handleError(error);
    } finally {
      setLogsLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    loadHealth();
    loadModels();
    loadPolicy();
    loadInfo();
    loadClients();
    const timer = setInterval(() => {
      loadHealth();
      loadModels();
      loadClients();
    }, 15000);
    return () => clearInterval(timer);
  }, [loadHealth, loadModels, loadPolicy, loadInfo, loadClients]);

  useEffect(() => {
    if (tab !== 'logs') return undefined;
    loadLogs();
    const timer = setInterval(loadLogs, 8000);
    return () => clearInterval(timer);
  }, [tab, loadLogs]);

  const handleNavigate = (next) => {
    setTab(next);
    setNavOpen(false);
    if (next === 'models') loadModels();
    if (next === 'policies') loadPolicy();
    if (next === 'server') loadInfo();
    if (next === 'clients') loadClients();
    if (next === 'logs') loadLogs();
  };

  const meta = TITLES[tab] || TITLES.overview;

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {navOpen && (
        <div
          className="fixed inset-0 z-20 bg-forge-950/70 backdrop-blur-sm lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[262px] shrink-0 flex-col border-r border-white/[0.06] bg-forge-900/75 backdrop-blur-xl transition-transform lg:static lg:z-auto lg:translate-x-0 ${
          navOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-2.5 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-electric-500 to-violet-600 shadow-glow">
            <Sparkles size={17} className="text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold tracking-tight text-slate-100">
              BotForge <span className="text-[10px] font-medium text-electric-300">v2</span>
            </p>
            <p className="text-[10px] text-violet-300/80">Host Mode</p>
          </div>
          <button
            type="button"
            onClick={() => setNavOpen(false)}
            className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 lg:hidden"
            aria-label="Close navigation"
          >
            <X size={15} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-2.5 py-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavigate(item.id)}
                className={`sidebar-item ${active ? 'sidebar-item-active' : ''}`}
              >
                <Icon size={16} className={active ? 'text-electric-300' : ''} />
                {item.label}
                {item.id === 'clients' && clients?.count > 0 && (
                  <span className="ml-auto rounded-full bg-white/[0.08] px-1.5 py-0.5 text-[10px] text-slate-300">
                    {clients.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="space-y-2 border-t border-white/[0.06] p-3">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
            <div className="flex items-center gap-2">
              <StatusDot status={health?.ollama?.connected ? 'online' : 'offline'} />
              <p className="text-[11px] font-medium text-slate-200">
                {health?.ollama?.connected ? 'Ollama connected' : 'Ollama offline'}
              </p>
            </div>
            <p className="mt-1 truncate text-[10px] text-slate-500">
              {health?.active_model || 'no active model'}
            </p>
          </div>
          <button
            type="button"
            onClick={onSwitchMode}
            className="btn-ghost w-full justify-start px-2.5 py-2 text-[11.5px]"
          >
            <Sparkles size={14} /> Client workspace
          </button>
          <button
            type="button"
            onClick={() => onLogout('')}
            className="btn-ghost w-full justify-start px-2.5 py-2 text-[11.5px]"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-white/[0.06] bg-forge-950/40 px-4 py-3 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold tracking-tight text-slate-100">
              {meta.title}
            </h1>
            <p className="truncate text-[10.5px] text-slate-500">{meta.subtitle}</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden rounded-full border border-violet-500/25 bg-violet-500/10 px-2.5 py-1 text-[10px] font-medium text-violet-200 sm:inline-flex">
              Administrator
            </span>
            <span className="hidden items-center gap-2 rounded-lg border border-white/[0.07] bg-white/[0.03] px-2.5 py-1.5 md:flex">
              <StatusDot status={health?.status === 'ok' ? 'online' : 'unknown'} />
              <span className="text-[10.5px] text-slate-300">Backend</span>
            </span>
          </div>
        </header>

        {notice && (
          <div
            className={`mx-4 mt-3 rounded-xl border px-3.5 py-2.5 text-[12px] sm:mx-6 ${
              notice.type === 'error'
                ? 'border-rose-500/25 bg-rose-500/10 text-rose-200'
                : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-200'
            }`}
          >
            {notice.message}
          </div>
        )}

        <main className="scroll-region min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto max-w-6xl">
            {tab === 'overview' && (
              <OverviewPanel
                health={health}
                models={models}
                policy={policy}
                info={info}
                clients={clients}
                onNavigate={handleNavigate}
                onRefresh={loadHealth}
              />
            )}
            {tab === 'models' && (
              <ModelManager models={models} onRefresh={loadModels} notify={notify} />
            )}
            {tab === 'policies' && (
              <PolicyManager
                policy={policy}
                onSaved={(next) => {
                  setPolicy(next);
                  loadHealth();
                }}
                notify={notify}
              />
            )}
            {tab === 'server' && (
              <ServerPanel info={info} health={health} onRefresh={loadInfo} notify={notify} />
            )}
            {tab === 'clients' && (
              <ClientsPanel clients={clients} onRefresh={loadClients} />
            )}
            {tab === 'logs' && (
              <LogsPanel logs={logs} loading={logsLoading} onRefresh={loadLogs} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
