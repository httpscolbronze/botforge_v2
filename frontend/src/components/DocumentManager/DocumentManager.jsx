import { useRef, useState } from 'react';
import {
  AlertTriangle,
  Database,
  FileSpreadsheet,
  FileText,
  Loader2,
  Lock,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import { formatBytes, formatRelative } from '../../services/format.js';

function iconFor(extension) {
  if (extension === '.csv') return FileSpreadsheet;
  return FileText;
}

export default function DocumentManager({
  documents,
  vectorStore,
  onUpload,
  onDelete,
  uploading,
  progress,
  error,
  documentAccess = true,
  maxMb = 25,
  onClose,
}) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const pick = (files) => {
    const file = files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div>
          <h2 className="text-[13px] font-semibold text-slate-100">Document intelligence</h2>
          <p className="text-[10.5px] text-slate-500">Local RAG · retrieves cited context</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-300"
            aria-label="Close documents panel"
          >
            <X size={15} />
          </button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {!documentAccess ? (
          <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.08] p-3.5">
            <div className="flex items-center gap-2 text-xs font-medium text-amber-200">
              <AlertTriangle size={14} /> Document access disabled
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-amber-100/70">
              Your administrator turned off document access in the host AI policy. Existing
              files stay on disk but cannot be queried.
            </p>
          </div>
        ) : (
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              pick(event.dataTransfer.files);
            }}
            className={`rounded-xl border border-dashed p-4 text-center transition ${
              dragging
                ? 'border-electric-400/60 bg-electric-500/[0.08]'
                : 'border-white/10 bg-white/[0.02] hover:border-white/20'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.csv,.md"
              className="hidden"
              onChange={(event) => {
                pick(event.target.files);
                event.target.value = '';
              }}
            />
            <UploadCloud size={20} className="mx-auto mb-2 text-electric-300" />
            <p className="text-[12px] font-medium text-slate-200">Add a document</p>
            <p className="mt-1 text-[10.5px] leading-relaxed text-slate-500">
              PDF, DOCX, TXT, CSV or MD · up to {maxMb} MB
            </p>
            <button
              type="button"
              className="btn-secondary mt-3 px-3 py-1.5 text-[11px]"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? <Loader2 size={13} className="animate-spin" /> : null}
              {uploading ? `Indexing… ${progress}%` : 'Choose file'}
            </button>
            {uploading && (
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-electric-500 to-violet-500 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-[11px] leading-relaxed text-rose-200">
            {error}
          </div>
        )}

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="label mb-0">Indexed files</span>
            <span className="text-[10px] text-slate-500">{documents.length}</span>
          </div>

          {documents.length === 0 ? (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4 text-center">
              <Database size={16} className="mx-auto mb-1.5 text-slate-600" />
              <p className="text-[11px] text-slate-500">
                No documents yet. Upload one to ask questions grounded in its content.
              </p>
            </div>
          ) : (
            <ul className="space-y-1.5">
              {documents.map((doc) => {
                const Icon = iconFor(doc.extension);
                return (
                  <li
                    key={doc.id}
                    className="group rounded-xl border border-white/[0.06] bg-white/[0.025] p-2.5"
                  >
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5 rounded-lg bg-electric-500/10 p-1.5 text-electric-300">
                        <Icon size={13} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12px] font-medium text-slate-200" title={doc.name}>
                          {doc.name}
                        </p>
                        <p className="mt-0.5 text-[10px] text-slate-500">
                          {formatBytes(doc.size_bytes)} · {doc.chunks} chunks
                          {doc.pages ? ` · ${doc.pages} pages` : ''} ·{' '}
                          {formatRelative(doc.created_at)}
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <span className="chip px-1.5 py-0.5 text-[9.5px]">
                            {doc.embedding_provider === 'ollama'
                              ? doc.embedding_model || 'ollama embeddings'
                              : 'local fallback embeddings'}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onDelete(doc.id)}
                        className="rounded-md p-1 text-slate-500 opacity-0 transition hover:bg-rose-500/10 hover:text-rose-300 group-hover:opacity-100"
                        aria-label={`Delete ${doc.name}`}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <div className="border-t border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <Lock size={10} />
          Files stored locally · vector store:{' '}
          <span className="text-slate-400">{vectorStore?.backend || 'initialising'}</span>
        </div>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
          Document text is treated as untrusted; instructions inside files are never followed.
        </p>
      </div>
    </div>
  );
}
