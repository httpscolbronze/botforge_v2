# BotForge_v2

A local-first AI assistant platform for individuals and teams. Create custom personas, chat with a
Llama model running in Ollama on your own machine, ask questions grounded in your own documents, and
let an administrator set organisation-wide AI policies that clients cannot override.

Inference, embeddings, screenshots and document text never leave the host. The only optional
external service is ElevenLabs voice generation, and it is off unless you configure it.

```
Client Mode (workspace)                  Host Mode (control centre)
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ conversations · streaming    │         │ models · pull/load/unload    │
│ personas · RAG documents     │  HTTP   │ AI policies · server health  │
│ screen assistant · voice     │ ──────► │ clients · logs · security    │
└──────────────┬───────────────┘         └──────────────┬───────────────┘
               │  React + Vite + Tailwind               │
               ▼                                        ▼
        FastAPI on 127.0.0.1:8000  ──►  Ollama 127.0.0.1:11434 (llama3.2:3b)
                                   └─►  ChromaDB + local files
```

## What works

**Client Mode**

- Streaming chat with conversation history, new chat, delete, stop generation and clear errors.
- Persona builder (name, role, tone, response style, expertise, language, extra instructions) that
  composes a system prompt server-side.
- Document intelligence: upload PDF/DOCX/TXT/CSV/MD, chunking, embeddings, ChromaDB retrieval,
  context injection and per-answer source citations with page numbers.
- Screen assistant: explicit screen capture (browser `getDisplayMedia`) or image upload, preview,
  then analysis by a local vision model. No capture happens without a click.
- Voice: read answers aloud through ElevenLabs, only when an API key exists and host policy allows
  it. The browser never sees the key.

**Host Mode** (administrator password)

- Automatic Ollama model discovery at startup and on demand: connection status, installed models
  classified as chat/embedding/vision, retry-connection button and refresh.
- Independent chat, embedding and vision model selection persisted in SQLite, with an explicit
  warning when a selected model is no longer installed. Nothing downloads without confirmation and
  no model is ever swapped silently.
- Installed Ollama models, load/unload, pull with live progress, connection status.
- Database panel: SQLite path/size/integrity, stored-data counts, create backup, list backups and
  restore with a pre-restore safety snapshot.
- Application preferences (history depth, retrieval depth) persisted in SQLite.
- AI policy manager: organisational purpose, allowed and restricted topics, document/screen/voice
  toggles, mandatory rules, retrieval depth. Saved server-side and enforced on every request.
- Server panel: API binding, data directory, runtime, CPU/memory/disk, vector store, database,
  backups, security posture.
- Connected clients (90-second presence window) and an in-memory log viewer.

## Requirements

- **Python 3.10+** (3.12 recommended)
- **Node.js 18+** and npm
- **Ollama** — https://ollama.com/download
- Optional: an ElevenLabs API key for voice

## 1. Install and start Ollama

```bash
# macOS / Linux (installer)
curl -fsSL https://ollama.com/install.sh | sh

# then pull the models (llama3.2:3b is the default chat model)
ollama pull llama3.2:3b
ollama pull nomic-embed-text      # embeddings for RAG
ollama pull llava                 # optional: screen analysis
```

Start the server if it is not already running:

```bash
ollama serve
```

Check it:

```bash
curl http://127.0.0.1:11434/api/tags
```

## 2. Configure the backend

From the repository root:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Edit `.env` and change at least:

```env
BOTFORGE_ADMIN_PASSWORD=choose-a-strong-password
BOTFORGE_SESSION_SECRET=a-long-random-string
```

Leave `BOTFORGE_HOST=127.0.0.1` unless you know what you are doing: the API is meant to be local.

## 3. Run the backend

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health (includes Ollama status and warnings)

The AI features work as soon as Ollama answers. If it is offline, the UI and API say so instead of
faking an answer.

## 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. Vite proxies `/api` to `http://127.0.0.1:8000`, so there is no CORS
setup to worry about and no second port to expose.

## 5. First-run walkthrough

1. **Host Mode** — click *Host mode* in the sidebar and sign in with `BOTFORGE_ADMIN_PASSWORD`
   (first run: `botforge-admin`).
2. **Models** — discovery runs automatically. Confirm Ollama is connected, then choose the default
   **chat**, **embedding** and **vision** models from the dropdowns (they are saved to SQLite). Pull
   `nomic-embed-text` (and `llava`) from the pull panel if they are missing; each download asks for
   confirmation first.
3. **AI policies** — set an organisational purpose, restricted topics, and whether documents,
   screens and external voice are allowed. Save.
4. **Client workspace** — start a new chat. The reply streams from your local model.
5. **Persona** — open the persona card, change name/role/tone, save, and ask again.
6. **Documents** — open the document panel, upload a PDF, wait for indexing, then ask a question
   about it. Answers show source chips with page numbers.
7. **Screen assistant** — press the monitor icon, capture a window or upload an image, analyse.
8. **Voice** — add `ELEVENLABS_API_KEY` to `.env`, restart the API, and press the speaker icon on an
   answer.

## API

| Method | Path | Auth | Purpose |
| ------ | ---- | ---- | ------- |
| GET | `/health` | — | Backend, SQLite and live Ollama status, counts, warnings |
| GET | `/settings`, PUT `/settings` | PUT admin | Application preferences persisted in SQLite |
| GET | `/models` | — | Installed models, selections, running models, availability |
| GET | `/models/status` | — | Discovery state, counts, missing selections, warning |
| GET | `/models/selected`, PUT `/models/selected` | PUT admin | Read/change chat, embedding and vision models independently |
| POST | `/models/refresh` | admin | Re-run Ollama discovery |
| POST | `/models/pull` | admin | Pull a model (SSE progress, requires `confirm: true`) |
| POST | `/models/active` | admin | Legacy alias for selecting the chat model |
| POST | `/models/load` `/models/unload` | admin | Warm / stop a model |
| POST | `/chat` | — | Chat (SSE stream, or JSON with `stream:false`) |
| POST | `/persona` | — | Create/update a persona |
| GET/DELETE | `/personas`, `/personas/{id}` | — | List and delete personas |
| POST | `/documents/upload` | — | Upload and index a document |
| POST | `/documents/query` | — | Retrieve relevant chunks |
| GET | `/documents` | — | List workspace documents |
| DELETE | `/documents/{id}` | — | Delete a document and its vectors |
| GET | `/policies` | — | Capability summary (full policy for admins) |
| PUT | `/policies` | admin | Save the host policy |
| POST | `/screen/analyze` | — | Analyse an uploaded screenshot locally |
| POST | `/voice/generate` | — | ElevenLabs audio (optional, external) |
| GET | `/voice/status` | — | Whether voice is configured/allowed |
| GET/DELETE | `/conversations`, `/conversations/{id}` | — | Conversation history and messages |
| GET | `/agents` | — | Agent configurations (name, description, chat model) |
| POST | `/backup` | admin | Create a database + documents + vectors backup |
| GET | `/backups` | admin | List backup archives |
| POST | `/backup/restore` | admin | Restore an archive (safety snapshot first) |
| GET | `/audit` | admin | Recent audit records |
| POST | `/clients/heartbeat`, GET `/clients` | admin (GET) | Presence for the host dashboard |
| GET | `/system/info`, `/system/logs` | admin | Server details and recent logs |
| POST | `/auth/login`, GET `/auth/session` | — | Administrator session |

Clients send an `X-Client-Id` header; documents, personas and conversations are scoped to it.

## How policies are enforced

Every chat request goes through `backend/engine/policy_engine.py`:

1. Restricted-topic and prompt-injection checks run **before** inference; blocked requests get a 403
   with a policy explanation and nothing is sent to the model.
2. The system prompt is assembled policy-first, persona-second. Persona text can never remove or
   precede the policy block.
3. Disabled capabilities (documents, screens, voice) are refused by the API itself, not merely hidden
   in the UI.
4. Retrieved document chunks are wrapped in `<excerpt>` markers and labelled untrusted data; the
   model is told not to follow instructions found inside them.

## Persistence architecture

SQLite is the primary application database. ChromaDB stores vectors in a persistent collection, and
original uploads stay on disk. Nothing is recreated, reset or deleted on startup.

```
backend/data/
├── botforge.db          SQLite: users, personas, agents, conversations, messages,
│                        host policies, documents, grants, audit logs, settings, presence
├── documents/           original uploaded files (PDF/DOCX/TXT/CSV/MD)
├── chroma_db/           persistent ChromaDB collection "botforge_documents"
├── conversations/       reserved for conversation exports
├── logs/                reserved for persisted logs
├── backups/             botforge-<timestamp>.zip (database + documents + vectors.json)
└── uploads/             legacy location, still readable for existing installs
```

`data/`, `backend/data/`, `*.db`, `.env` and log files are git-ignored. The database is created and
migrated automatically on first start (`backend/database/migrations/`); migrations run once and are
recorded in `schema_migrations`.

### Database schema

| Table | Contents |
| ----- | -------- |
| `users` | Local administrators and per-workspace owners (`X-Client-Id`) |
| `personas` | Persona prompt fields, owned by a user |
| `agents` | Agent configuration: name, description, chat/embedding model override, `config_json` |
| `conversations` | Owner, agent, persona, title, model, timestamps |
| `messages` | Role, content, source references, model, conversation FK (cascade delete) |
| `host_policies` | Organisation purpose, topics, capability toggles, rules, retrieval depth |
| `documents` | File metadata, checksum, chunk count, embedding provider/model, stored path |
| `document_grants` | Per-document read/write permission for other users |
| `audit_logs` | Actor, action, target, JSON detail, timestamp |
| `app_settings` | Preferences and selected chat/embedding/vision models |
| `client_presence` | 90-second presence registry for Host Mode |

Indexes cover owner + recency lookups for personas, agents, conversations, documents and audit logs.
Every query is parameterized. Writes that touch multiple tables (persona + agent, document + grant)
run inside a single transaction.

### Model discovery

On startup BotForge asks Ollama `GET /api/tags`, classifies models by name
(`embed`/`bge`/`minilm` → embedding, `llava`/`vision`/`moondream` → vision, everything else → chat),
and compares the installed set with the SQLite selections. The Host dashboard shows connection state,
installed models, selected models and any missing model with the available alternatives.

Selections are independent: changing the chat model never changes the embedding model. If a selected
model disappears, chat returns a clear 409 error with alternatives instead of silently switching. If
Ollama is offline, the app stays usable, reports the connection error and offers a retry.

The `OLLAMA_DEFAULT_MODEL`, `OLLAMA_EMBEDDING_MODEL` and `OLLAMA_VISION_MODEL` environment variables
are only first-run defaults; after that the SQLite selection wins.

### Backups and restore

`POST /backup` writes a zip with a consistent SQLite copy, the original documents and
`vectors.json`. Restore validates the archive and database integrity, first creates a safety backup
of the current state, then swaps the database, documents and vectors. Errors are returned as readable
messages, and a document whose file is missing on disk is flagged in `/documents` with a warning.

## Honest limitations (MVP)

- **Not a hardened multi-tenant product.** Host Mode has a password and HMAC-signed session token,
  and policies are enforced server-side, but there is no per-user account system. Workspace ids are an
  isolation boundary for a trusted local machine, not authentication. Do not expose this API to the
  internet. For a hosted deployment, put it behind a reverse proxy with TLS and real authentication.
- **Ollama must be running.** Without it, chat, embeddings and screen analysis return explicit
  connection errors. With `BOTFORGE_EMBEDDING_FALLBACK=true`, embeddings fall back to a local hashing
  vectoriser so RAG still works offline; the UI labels this degraded mode. Retrieval quality is lower.
- **Scanned PDFs are not OCR'd.** PDFs must contain selectable text. DOCX files have no reliable page
  numbers, so citations say "document".
- **Screen analysis needs a vision model** (`llava`) and explicit user action. The browser capture
  uses `getDisplayMedia`, which requires a secure context (`localhost` is fine).
- **Voice is the only external call.** It is off without `ELEVENLABS_API_KEY` and can be disabled by
  policy. Generated audio is not stored.
- **No Electron overlay.** The in-app floating screen assistant covers the workflow; a desktop
  overlay is not part of this MVP.
- **Automated tests use a stub Ollama.** `tests/test_persistence.py` starts a real uvicorn server
  against a throwaway data directory and restarts it to verify persistence, RAG, backups, permissions
  and offline handling. Ollama discovery and chat plumbing run against `tests/stub_ollama.py` because
  the build environment has no Ollama; real answer quality and real `nomic-embed-text` embeddings are
  not verified there (the labelled hashing fallback is used instead).
- **Legacy JSON data is not imported.** The earlier MVP stored JSON files under `backend/data/`.
  They are left untouched, but this version starts from a fresh SQLite database.
- **Single host.** Backup restore and database files assume one local process using the data
  directory; do not run two BotForge processes against the same directory.

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| "Ollama is not reachable at http://127.0.0.1:11434" | Run `ollama serve`, check `OLLAMA_BASE_URL` in `.env` |
| "Model 'llama3.2:3b' is not installed" | `ollama pull llama3.2:3b`, or pull it from Host Mode → Models |
| Embedding warning in chat | `ollama pull nomic-embed-text` (fallback embeddings are in use). If you just switched embedding models, re-upload documents: old vectors are incompatible. |
| "Selected chat model ... is not installed" | Host Mode → Models: pull it or choose an installed chat model |
| Restore says vectors could not be restored | Re-upload the documents so embeddings are rebuilt |
| Screen analysis fails | `ollama pull llava`; check the model supports images |
| "ElevenLabs is not configured" | Set `ELEVENLABS_API_KEY` in `.env` and restart the API |
| Upload rejected | Only PDF/DOCX/TXT/CSV/MD, non-empty, under `BOTFORGE_MAX_UPLOAD_MB` |
| Host Mode password rejected | It comes from `BOTFORGE_ADMIN_PASSWORD`; default is `botforge-admin` |
| Frontend shows "Cannot reach the BotForge backend" | Start uvicorn on port 8000; the Vite proxy expects it |

## Production-style build

```bash
cd frontend && npm run build && cd ..
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

When `frontend/dist/index.html` exists the FastAPI app serves the built SPA at `/` alongside the API,
which is enough for a single-machine install or a simple hosted demo.

## Tests

```bash
.venv/bin/python tests/test_persistence.py
```

The suite starts the stub Ollama and a real uvicorn server on port 8001, exercises persona,
conversation, model-selection and document persistence across a full restart, verifies RAG retrieval,
vector deletion, backup/restore, workspace isolation, admin authorization and disconnected-Ollama
behaviour. A real PDF is generated with PyMuPDF and ingested end to end.

## Project layout

```
backend/
  main.py  config.py  log_buffer.py
  database/  connection.py models.py schemas.py backup.py migrations/001_initial.sql
  routes/    auth chat models policies personas documents screen voice clients system settings
  engine/    ollama_client persona policy_engine model_registry
  rag/       ingestion chunking embeddings retrieval
  storage/   repositories (SQLite) + legacy store.py
frontend/
  src/pages/          ClientMode.jsx  HostMode.jsx
  src/components/     Chat PersonaBuilder DocumentManager ScreenAssistant
                      HostDashboard ModelManager PolicyManager Settings shared
  src/services/       api.js format.js
```
