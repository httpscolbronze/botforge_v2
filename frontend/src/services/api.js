/**
 * Single API client for both modes.
 *
 * The browser only ever talks to `/api` on its own origin (Vite proxies that to
 * the FastAPI process). Admin tokens live in localStorage; secrets never do.
 */

const BASE = import.meta.env.VITE_API_BASE || '/api';
const CLIENT_KEY = 'botforge.clientId';
const TOKEN_KEY = 'botforge.adminToken';

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function getClientId() {
  let id = localStorage.getItem(CLIENT_KEY);
  if (!id) {
    id = `ws_${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36).slice(-4)}`;
    localStorage.setItem(CLIENT_KEY, id);
  }
  return id;
}

export function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setAdminToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function headers(extra = {}) {
  const result = { 'X-Client-Id': getClientId(), ...extra };
  const token = getAdminToken();
  if (token) result.Authorization = `Bearer ${token}`;
  return result;
}

function errorMessage(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${(item.loc || []).slice(1).join('.') || 'input'}: ${item.msg}`)
      .join('; ');
  }
  if (payload?.error) return String(payload.error);
  return fallback;
}

async function request(path, { method = 'GET', body } = {}) {
  const options = { method, headers: headers() };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`${BASE}${path}`, options);
  } catch (error) {
    throw new ApiError(
      'Cannot reach the BotForge backend. Make sure the API is running on port 8000.',
      0,
      error,
    );
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      errorMessage(payload, `Request failed (HTTP ${response.status}).`),
      response.status,
      payload,
    );
  }
  return payload;
}

export const api = {
  getClientId,

  // -- system --------------------------------------------------------------
  health: () => request('/health'),
  systemInfo: () => request('/system/info'),
  logs: (limit = 200, level = '') =>
    request(`/system/logs?limit=${limit}${level ? `&level=${encodeURIComponent(level)}` : ''}`),

  // -- auth ----------------------------------------------------------------
  login: (password) => request('/auth/login', { method: 'POST', body: { password } }),
  session: () => request('/auth/session'),

  // -- models --------------------------------------------------------------
  models: () => request('/models'),
  modelsStatus: () => request('/models/status'),
  selectedModels: () => request('/models/selected'),
  saveSelectedModels: (payload) =>
    request('/models/selected', { method: 'PUT', body: payload }),
  refreshModels: () => request('/models/refresh', { method: 'POST' }),
  setActiveModel: (name) =>
    request('/models/selected', { method: 'PUT', body: { chat_model: name } }),
  loadModel: (name) => request('/models/load', { method: 'POST', body: { name } }),
  unloadModel: (name) => request('/models/unload', { method: 'POST', body: { name } }),

  async pullModel(name, onEvent) {
    let response;
    try {
      response = await fetch(`${BASE}/models/pull`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ name, confirm: true }),
      });
    } catch {
      throw new ApiError('Cannot reach the backend to pull a model.', 0);
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(errorMessage(payload, 'Model pull was refused.'), response.status);
    }
    const reader = response.body?.getReader();
    if (!reader) throw new ApiError('Streaming is not supported in this browser.', 0);
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index;
      while ((index = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 2);
        for (const line of raw.split('\n')) {
          if (!line.startsWith('data:')) continue;
          try {
            onEvent?.(JSON.parse(line.slice(5).trim()));
          } catch {
            /* ignore malformed progress frames */
          }
        }
      }
    }
  },

  // -- settings & backups --------------------------------------------------
  settings: () => request('/settings'),
  saveSettings: (payload) => request('/settings', { method: 'PUT', body: payload }),
  backups: () => request('/backups'),
  createBackup: (includeVectors = true) =>
    request('/backup', { method: 'POST', body: { include_vectors: includeVectors } }),
  restoreBackup: (backupId) =>
    request('/backup/restore', { method: 'POST', body: { backup_id: backupId } }),
  audit: (limit = 200) => request(`/audit?limit=${limit}`),

  // -- policies ------------------------------------------------------------
  policies: () => request('/policies'),
  savePolicies: (policy) => request('/policies', { method: 'PUT', body: policy }),

  // -- personas ------------------------------------------------------------
  personas: () => request('/personas'),
  agents: () => request('/agents'),
  savePersona: (persona) => request('/persona', { method: 'POST', body: persona }),
  deletePersona: (id) => request(`/personas/${id}`, { method: 'DELETE' }),

  // -- documents -----------------------------------------------------------
  documents: () => request('/documents'),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  queryDocuments: (payload) =>
    request('/documents/query', { method: 'POST', body: payload }),

  uploadDocument(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE}/documents/upload`);
      Object.entries(headers()).forEach(([key, value]) => xhr.setRequestHeader(key, value));
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        let payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch {
          payload = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(payload);
        else
          reject(
            new ApiError(
              errorMessage(payload, `Upload failed (HTTP ${xhr.status}).`),
              xhr.status,
              payload,
            ),
          );
      };
      xhr.onerror = () =>
        reject(new ApiError('Upload failed: cannot reach the BotForge backend.', 0));
      const form = new FormData();
      form.append('file', file);
      xhr.send(form);
    });
  },

  // -- conversations -------------------------------------------------------
  conversations: () => request('/conversations'),
  conversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),

  async chatStream(payload, handlers = {}, signal) {
    let response;
    try {
      response = await fetch(`${BASE}/chat`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ ...payload, stream: true }),
        signal,
      });
    } catch {
      throw new ApiError(
        'Cannot reach the BotForge backend. Is it running on port 8000?',
        0,
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(
        errorMessage(body, `Chat failed (HTTP ${response.status}).`),
        response.status,
        body,
      );
    }
    const reader = response.body?.getReader();
    if (!reader) throw new ApiError('Streaming is not supported in this browser.', 0);
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let index;
        while ((index = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, index).trim();
          buffer = buffer.slice(index + 2);
          for (const line of raw.split('\n')) {
            if (!line.startsWith('data:')) continue;
            let event;
            try {
              event = JSON.parse(line.slice(5).trim());
            } catch {
              continue;
            }
            if (event.type === 'meta') handlers.onMeta?.(event);
            else if (event.type === 'token') handlers.onToken?.(event.content);
            else if (event.type === 'done') handlers.onDone?.(event);
            else if (event.type === 'error') handlers.onError?.(event.message, event);
          }
        }
      }
    } finally {
      reader.releaseLock?.();
    }
  },

  // -- screen & voice ------------------------------------------------------
  async analyzeScreen(file, prompt) {
    const form = new FormData();
    form.append('image', file);
    form.append('prompt', prompt || 'Describe what is on this screen.');
    let response;
    try {
      response = await fetch(`${BASE}/screen/analyze`, {
        method: 'POST',
        headers: headers(),
        body: form,
      });
    } catch {
      throw new ApiError('Cannot reach the backend for screen analysis.', 0);
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        errorMessage(payload, 'Screen analysis failed.'),
        response.status,
        payload,
      );
    }
    return payload;
  },

  voiceStatus: () => request('/voice/status'),

  async generateVoice(text) {
    let response;
    try {
      response = await fetch(`${BASE}/voice/generate`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text }),
      });
    } catch {
      throw new ApiError('Cannot reach the backend for voice generation.', 0);
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(errorMessage(payload, 'Voice generation failed.'), response.status, payload);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  // -- presence ------------------------------------------------------------
  heartbeat: (name, mode) =>
    request('/clients/heartbeat', {
      method: 'POST',
      body: { client_id: getClientId(), name, mode },
    }),
  clients: () => request('/clients'),
};
