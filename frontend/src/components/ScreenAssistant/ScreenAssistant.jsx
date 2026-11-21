import { useEffect, useRef, useState } from 'react';
import {
  Camera,
  Eye,
  ImagePlus,
  Loader2,
  Minus,
  Monitor,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { api } from '../../services/api.js';
import Markdown from '../shared/Markdown.jsx';

export default function ScreenAssistant({ open, onOpen, onClose }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [prompt, setPrompt] = useState('What is on this screen? Point out anything important.');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const fileRef = useRef(null);
  const previewRef = useRef('');

  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  const setSelected = (selected, url) => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = url;
    setPreview(url);
    setFile(selected);
    setAnswer('');
    setError('');
  };

  const handleFile = (selected) => {
    if (!selected) return;
    setSelected(selected, URL.createObjectURL(selected));
  };

  const captureScreen = async () => {
    setError('');
    setCapturing(true);
    try {
      if (!navigator.mediaDevices?.getDisplayMedia) {
        throw new Error('Screen capture is not available in this browser or context.');
      }
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const track = stream.getVideoTracks()[0];
      const video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      await video.play();
      await new Promise((resolve) => setTimeout(resolve, 250));
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      stream.getTracks().forEach((item) => item.stop());
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('Could not capture a frame from the selected screen.');
      setSelected(new File([blob], 'screenshot.png', { type: 'image/png' }), URL.createObjectURL(blob));
    } catch (err) {
      setError(err.message || 'Screen capture was cancelled.');
    } finally {
      setCapturing(false);
    }
  };

  const analyse = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError('');
    setAnswer('');
    try {
      const result = await api.analyzeScreen(file, prompt);
      setAnswer(result.answer);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full border border-white/10 bg-forge-900/95 px-4 py-2.5 text-xs font-medium text-slate-200 shadow-glow backdrop-blur transition hover:border-electric-500/40 hover:text-white"
      >
        <Monitor size={15} className="text-electric-300" />
        Screen assistant
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 w-[380px] max-w-[calc(100vw-2rem)] animate-fade-up overflow-hidden rounded-2xl border border-white/10 bg-forge-900/97 shadow-panel backdrop-blur">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Eye size={14} className="text-electric-300" />
          <div>
            <p className="text-[12px] font-semibold text-slate-100">Screen assistant</p>
            <p className="text-[9.5px] text-slate-500">Local vision model · explicit consent</p>
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-300"
            aria-label="Minimise screen assistant"
          >
            <Minus size={14} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-500 hover:bg-white/5 hover:text-slate-300"
            aria-label="Close screen assistant"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="max-h-[70vh] space-y-3 overflow-y-auto p-4">
        <div className="relative flex min-h-[120px] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-forge-950/60">
          {preview ? (
            <>
              <img src={preview} alt="Selected screenshot preview" className="max-h-52 w-full object-contain" />
              <button
                type="button"
                onClick={() => setSelected(null, '')}
                className="absolute right-2 top-2 rounded-md bg-forge-950/80 p-1 text-slate-300 hover:text-white"
                aria-label="Remove screenshot"
              >
                <X size={13} />
              </button>
            </>
          ) : (
            <div className="p-4 text-center">
              <Monitor size={20} className="mx-auto mb-2 text-slate-600" />
              <p className="text-[11px] text-slate-500">
                Nothing captured. Choose a screenshot or share a screen when you are ready.
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={captureScreen}
            disabled={capturing}
            className="btn-secondary flex-1 px-2 py-2 text-[11px]"
          >
            {capturing ? <Loader2 size={13} className="animate-spin" /> : <Camera size={13} />}
            {capturing ? 'Capturing…' : 'Capture screen'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              handleFile(event.target.files?.[0]);
              event.target.value = '';
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="btn-secondary flex-1 px-2 py-2 text-[11px]"
          >
            <ImagePlus size={13} /> Upload image
          </button>
        </div>

        <div>
          <label className="label" htmlFor="screen-prompt">
            What should the assistant look for?
          </label>
          <textarea
            id="screen-prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={2000}
            rows={2}
            className="input resize-none text-[12px]"
          />
        </div>

        <button
          type="button"
          onClick={analyse}
          disabled={!file || busy}
          className="btn-primary w-full py-2 text-[12px]"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {busy ? 'Analysing locally…' : 'Analyse screenshot'}
        </button>

        {error && (
          <div className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-[11px] leading-relaxed text-rose-200">
            {error}
          </div>
        )}

        {answer && (
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
              Analysis
            </p>
            <Markdown content={answer} className="text-[12.5px]" />
          </div>
        )}

        <p className="flex items-start gap-1.5 text-[9.5px] leading-relaxed text-slate-600">
          <ShieldCheck size={11} className="mt-0.5 shrink-0" />
          Nothing is captured until you press Capture or pick a file. Images are sent only to your
          local Ollama vision model and are not stored.
        </p>
      </div>
    </div>
  );
}
