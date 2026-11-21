import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  FileText,
  Menu,
  Monitor,
  PanelRight,
  Plus,
  Settings,
  Shield,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';
import { api } from '../services/api.js';
import ConversationList from '../components/Chat/ConversationList.jsx';
import ChatWindow from '../components/Chat/ChatWindow.jsx';
import Composer from '../components/Chat/Composer.jsx';
import PersonaBuilder from '../components/PersonaBuilder/PersonaBuilder.jsx';
import DocumentManager from '../components/DocumentManager/DocumentManager.jsx';
import ScreenAssistant from '../components/ScreenAssistant/ScreenAssistant.jsx';
import SettingsPanel from '../components/Settings/SettingsPanel.jsx';
import StatusDot from '../components/shared/StatusDot.jsx';
import { initials } from '../services/format.js';

const DEFAULT_PERSONA = {
  name: 'Alex',
  persona: 'Senior Software Engineer',
  tone: 'Professional',
  response_style: 'Detailed and explanatory',
  expertise: 'Python, APIs and System Design',
  language: 'English',
  additional_instructions: '',
};

export default function ClientMode({ onSwitchMode }) {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState('');
  const [models, setModels] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [activePersona, setActivePersona] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [sending, setSending] = useState(false);
  const [chatWarning, setChatWarning] = useState('');
  const [documents, setDocuments] = useState([]);
  const [vectorStore, setVectorStore] = useState(null);
  const [useDocuments, setUseDocuments] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [docError, setDocError] = useState('');
  const [docPanelOpen, setDocPanelOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [personaOpen, setPersonaOpen] = useState(false);
  const [personaSaving, setPersonaSaving] = useState(false);
  const [personaError, setPersonaError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [screenOpen, setScreenOpen] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [voiceError, setVoiceError] = useState('');
  const [speakingId, setSpeakingId] = useState(null);
  const abortRef = useRef(null);
  const audioRef = useRef(null);

  const persona = activePersona || personas[0] || DEFAULT_PERSONA;
  const modelOnline = Boolean(health?.ollama?.connected);
  const documentAccess = policy?.document_access ?? health?.documents?.access_enabled ?? true;
  const voiceAvailable = Boolean(voiceStatus?.configured && voiceStatus?.enabled_by_policy);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await api.health();
      setHealth(data);
      setHealthError('');
    } catch (error) {
      setHealthError(error.message);
    }
  }, []);

  const refreshModels = useCallback(async () => {
    try {
      const data = await api.models();
      setModels(data.models || []);
    } catch {
      /* the offline banner already explains model problems */
    }
  }, []);

  const refreshPolicies = useCallback(async () => {
    try {
      const data = await api.policies();
      setPolicy(data.policy);
    } catch {
      /* capabilities fall back to permissive defaults in the UI */
    }
  }, []);

  const refreshPersonas = useCallback(async () => {
    try {
      const data = await api.personas();
      setPersonas(data.personas || []);
      const stored = localStorage.getItem('botforge.activePersona');
      const match = (data.personas || []).find((item) => item.id === stored);
      if (match) setActivePersona(match);
    } catch {
      /* onboarding still works with the default persona */
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const data = await api.conversations();
      setConversations(data.conversations || []);
    } catch {
      /* offline banner already covers this */
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    try {
      const data = await api.documents();
      setDocuments(data.documents || []);
      setVectorStore(data.vector_store || null);
    } catch {
      /* handled by panel when the user uploads */
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    refreshModels();
    refreshPolicies();
    refreshPersonas();
    refreshConversations();
    refreshDocuments();
    api
      .voiceStatus()
      .then(setVoiceStatus)
      .catch(() => setVoiceStatus(null));
    const timer = setInterval(refreshHealth, 20000);
    return () => clearInterval(timer);
  }, [
    refreshHealth,
    refreshModels,
    refreshPolicies,
    refreshPersonas,
    refreshConversations,
    refreshDocuments,
  ]);

  useEffect(() => {
    if (window.innerWidth >= 1280) setDocPanelOpen(true);
  }, []);

  useEffect(() => {
    api.heartbeat('Local workspace', 'client').catch(() => {});
    const timer = setInterval(() => {
      api.heartbeat('Local workspace', 'client').catch(() => {});
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  const newChat = () => {
    setActiveId(null);
    setMessages([]);
    setChatWarning('');
    setSidebarOpen(false);
  };

  const openConversation = async (id) => {
    setSidebarOpen(false);
    setActiveId(id);
    setChatWarning('');
    try {
      const data = await api.conversation(id);
      setMessages(
        (data.conversation.messages || []).map((message, index) => ({
          ...message,
          id: `${id}-${index}`,
        })),
      );
    } catch (error) {
      setChatWarning(error.message);
    }
  };

  const removeConversation = async (id) => {
    if (!window.confirm('Delete this conversation? This cannot be undone.')) return;
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((item) => item.id !== id));
      if (activeId === id) newChat();
    } catch (error) {
      setChatWarning(error.message);
    }
  };

  const sendMessage = async (text) => {
    if (sending || streaming) return;
    const assistantId = `local-${Date.now()}`;
    const now = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: text, created_at: now },
      { id: assistantId, role: 'assistant', content: '', created_at: now, pending: true },
    ]);
    setSending(true);
    setStreaming(true);
    setChatWarning('');
    setSidebarOpen(false);

    const controller = new AbortController();
    abortRef.current = controller;
    let receivedAny = false;
    let finished = false;

    try {
      await api.chatStream(
        {
          message: text,
          conversation_id: activeId,
          persona: activePersona
            ? {
                name: activePersona.name,
                persona: activePersona.persona,
                tone: activePersona.tone,
                response_style: activePersona.response_style,
                expertise: activePersona.expertise,
                language: activePersona.language,
                additional_instructions: activePersona.additional_instructions,
                chat_model: activePersona.chat_model || undefined,
              }
            : undefined,
          persona_id: activePersona?.id || undefined,
          use_documents: useDocuments,
        },
        {
          onMeta: (meta) => {
            setActiveId(meta.conversation_id);
            if (meta.warning) setChatWarning(meta.warning);
          },
          onToken: (token) => {
            receivedAny = true;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + token, pending: false }
                  : message,
              ),
            );
          },
          onDone: (done) => {
            finished = true;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: done.content || message.content,
                      pending: false,
                      sources: done.sources || [],
                    }
                  : message,
              ),
            );
          },
          onError: (message) => {
            finished = true;
            setMessages((prev) =>
              prev.map((item) =>
                item.id === assistantId
                  ? { ...item, content: message, pending: false, error: true }
                  : item,
              ),
            );
          },
        },
        controller.signal,
      );
    } catch (error) {
      if (error.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  pending: false,
                  error: !receivedAny,
                  content: message.content || 'Generation stopped.',
                }
              : message,
          ),
        );
      } else {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  pending: false,
                  error: true,
                  content: error.message || 'The request failed.',
                }
              : message,
          ),
        );
      }
    } finally {
      if (!finished && receivedAny) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, pending: false } : message,
          ),
        );
      }
      abortRef.current = null;
      setStreaming(false);
      setSending(false);
      refreshConversations();
      refreshHealth();
    }
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setSending(false);
  };

  const savePersona = async (payload) => {
    setPersonaSaving(true);
    setPersonaError('');
    try {
      const data = await api.savePersona(payload);
      setActivePersona(data.persona);
      localStorage.setItem('botforge.activePersona', data.persona.id);
      await refreshPersonas();
      setPersonaOpen(false);
    } catch (error) {
      setPersonaError(error.message);
    } finally {
      setPersonaSaving(false);
    }
  };

  const deletePersona = async (id) => {
    if (!window.confirm('Delete this persona?')) return;
    try {
      await api.deletePersona(id);
      if (activePersona?.id === id) {
        setActivePersona(null);
        localStorage.removeItem('botforge.activePersona');
      }
      await refreshPersonas();
    } catch (error) {
      setPersonaError(error.message);
    }
  };

  const uploadDocument = async (file) => {
    if (!file) return;
    setUploading(true);
    setUploadProgress(0);
    setDocError('');
    try {
      const result = await api.uploadDocument(file, setUploadProgress);
      await refreshDocuments();
      await refreshHealth();
      if (result?.warning) setDocError(result.warning);
      setDocPanelOpen(true);
      setUseDocuments(true);
    } catch (error) {
      setDocError(error.message);
      setDocPanelOpen(true);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const deleteDocument = async (id) => {
    if (!window.confirm('Delete this document and its embeddings?')) return;
    try {
      await api.deleteDocument(id);
      await refreshDocuments();
      await refreshHealth();
    } catch (error) {
      setDocError(error.message);
    }
  };

  const speak = async (message) => {
    if (!voiceAvailable) {
      setVoiceError('Voice is not configured or is disabled by host policy.');
      return;
    }
    setVoiceError('');
    setSpeakingId(message.id);
    try {
      const url = await api.generateVoice(message.content.slice(0, 4500));
      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setSpeakingId(null);
      await audio.play();
    } catch (error) {
      setSpeakingId(null);
      setVoiceError(error.message);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-forge-950/70 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[278px] shrink-0 flex-col border-r border-white/[0.06] bg-forge-900/70 backdrop-blur-xl transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-2.5 px-4 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-electric-500 to-violet-600 shadow-glow">
            <Sparkles size={17} className="text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-tight text-slate-100">
              BotForge <span className="text-[10px] font-medium text-electric-300">v2</span>
            </p>
            <p className="text-[10px] text-slate-500">Local-first AI platform</p>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="ml-auto rounded-md p-1.5 text-slate-500 hover:bg-white/5 lg:hidden"
            aria-label="Close sidebar"
          >
            <X size={15} />
          </button>
        </div>

        <div className="px-3">
          <button type="button" onClick={newChat} className="btn-primary w-full py-2.5 text-[13px]">
            <Plus size={15} /> New chat
          </button>
        </div>

        <div className="mt-5 flex min-h-0 flex-1 flex-col">
          <p className="px-4 pb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            Conversations
          </p>
          <div className="scroll-region min-h-0 flex-1 overflow-y-auto pb-3">
            <ConversationList
              items={conversations}
              activeId={activeId}
              onSelect={openConversation}
              onDelete={removeConversation}
              loading={conversationsLoading}
            />
          </div>
        </div>

        <div className="space-y-2 border-t border-white/[0.06] p-3">
          <button
            type="button"
            onClick={() => {
              setPersonaError('');
              setPersonaOpen(true);
            }}
            className="w-full rounded-xl border border-white/[0.07] bg-white/[0.03] p-2.5 text-left transition hover:border-electric-500/30 hover:bg-white/[0.05]"
          >
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-500/25 bg-gradient-to-br from-violet-600/25 to-electric-600/25 text-[11px] font-semibold text-indigo-200">
                {initials(persona.name)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium text-slate-100">{persona.name}</p>
                <p className="truncate text-[10px] text-slate-500">
                  {persona.persona || 'Custom assistant'}
                </p>
              </div>
              <Wand2 size={13} className="text-slate-500" />
            </div>
          </button>

          <div className="grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="btn-ghost justify-start px-2.5 py-2 text-[11.5px]"
            >
              <Settings size={14} /> Settings
            </button>
            <button
              type="button"
              onClick={onSwitchMode}
              className="btn-ghost justify-start px-2.5 py-2 text-[11.5px]"
              title="Switch to the administrator dashboard"
            >
              <Shield size={14} /> Host mode
            </button>
          </div>
          <p className="px-1 text-[9.5px] text-slate-600">
            Private workspace · {api.getClientId().slice(0, 12)}…
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-white/[0.06] bg-forge-950/40 px-3 py-2.5 backdrop-blur sm:px-5">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-slate-100 lg:hidden"
            aria-label="Open sidebar"
          >
            <Menu size={18} />
          </button>

          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-gradient-to-br from-electric-600/20 to-violet-600/20 text-[10px] font-semibold text-indigo-200">
              {initials(persona.name)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-slate-100">{persona.name}</p>
              <p className="truncate text-[10px] text-slate-500">
                {persona.persona || 'Assistant'} · {persona.response_style || 'Adaptive'}
              </p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <span className="hidden items-center gap-2 rounded-lg border border-white/[0.07] bg-white/[0.03] px-2.5 py-1.5 sm:flex">
              <StatusDot status={modelOnline ? 'online' : 'offline'} />
              <span className="text-[10.5px] font-medium text-slate-300">
                {health?.active_model || 'model unknown'}
              </span>
            </span>
            <button
              type="button"
              onClick={() => setDocPanelOpen((value) => !value)}
              className={`rounded-lg p-2 transition ${
                docPanelOpen
                  ? 'bg-electric-500/10 text-electric-300'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
              }`}
              aria-label="Toggle documents panel"
              title="Documents"
            >
              <PanelRight size={17} />
            </button>
            <button
              type="button"
              onClick={() => setScreenOpen(true)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-white/5 hover:text-slate-100"
              aria-label="Open screen assistant"
              title="Screen assistant"
            >
              <Monitor size={17} />
            </button>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-white/5 hover:text-slate-100"
              aria-label="Open settings"
              title="Settings"
            >
              <Settings size={17} />
            </button>
          </div>
        </header>

        {(healthError || chatWarning || voiceError) && (
          <div className="space-y-1 px-4 pt-2 sm:px-6">
            {healthError && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-500/25 bg-rose-500/[0.08] px-3 py-2 text-[11.5px] text-rose-200">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <span className="flex-1">{healthError}</span>
              </div>
            )}
            {health?.models?.warning && !chatWarning && (
              <div className="flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-[11px] text-amber-100/80">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <span className="flex-1">{health.models.warning}</span>
              </div>
            )}
            {chatWarning && (
              <div className="flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-[11px] text-amber-100/80">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <span className="flex-1">{chatWarning}</span>
                <button
                  type="button"
                  onClick={() => setChatWarning('')}
                  className="text-amber-200/70 hover:text-amber-100"
                  aria-label="Dismiss warning"
                >
                  <X size={12} />
                </button>
              </div>
            )}
            {voiceError && (
              <div className="flex items-start gap-2 rounded-xl border border-violet-500/25 bg-violet-500/[0.08] px-3 py-2 text-[11px] text-violet-100/80">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                <span className="flex-1">{voiceError}</span>
                <button
                  type="button"
                  onClick={() => setVoiceError('')}
                  className="text-violet-200/70 hover:text-violet-100"
                  aria-label="Dismiss voice warning"
                >
                  <X size={12} />
                </button>
              </div>
            )}
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <ChatWindow
              messages={messages}
              streaming={streaming}
              persona={persona}
              onSuggestion={sendMessage}
              onSpeak={speak}
              speakingId={speakingId}
              voiceAvailable={voiceAvailable}
              documentCount={documents.length}
            />
            <Composer
              onSend={sendMessage}
              onStop={stopStreaming}
              disabled={sending && !streaming}
              streaming={streaming}
              useDocuments={useDocuments}
              onToggleDocuments={() => setUseDocuments((value) => !value)}
              documentCount={documents.length}
              onOpenDocuments={() => setDocPanelOpen(true)}
              onOpenScreen={() => setScreenOpen(true)}
              onOpenPersona={() => {
                setPersonaError('');
                setPersonaOpen(true);
              }}
              model={health?.active_model}
              modelOnline={modelOnline}
            />
          </div>

          {docPanelOpen && (
            <>
              <div
                className="fixed inset-0 z-20 bg-forge-950/60 backdrop-blur-sm xl:hidden"
                onClick={() => setDocPanelOpen(false)}
                aria-hidden="true"
              />
              <aside className="fixed inset-y-0 right-0 z-30 w-[330px] max-w-[90vw] border-l border-white/[0.06] bg-forge-900/95 backdrop-blur-xl xl:static xl:z-auto xl:bg-forge-900/40">
                <DocumentManager
                  documents={documents}
                  vectorStore={vectorStore}
                  onUpload={uploadDocument}
                  onDelete={deleteDocument}
                  uploading={uploading}
                  progress={uploadProgress}
                  error={docError}
                  documentAccess={documentAccess}
                  maxMb={25}
                  onClose={() => setDocPanelOpen(false)}
                />
              </aside>
            </>
          )}
        </div>
      </div>

      <PersonaBuilder
        open={personaOpen}
        onClose={() => setPersonaOpen(false)}
        personas={personas}
        activePersona={activePersona}
        onSave={savePersona}
        onDelete={deletePersona}
        saving={personaSaving}
        error={personaError}
        models={models}
        defaultModel={health?.active_model}
      />

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        health={health}
        policy={policy}
        voiceStatus={voiceStatus}
      />

      <ScreenAssistant
        open={screenOpen}
        onOpen={() => setScreenOpen(true)}
        onClose={() => setScreenOpen(false)}
      />
    </div>
  );
}
