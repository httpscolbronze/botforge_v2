const STYLES = {
  online: 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]',
  offline: 'bg-rose-400',
  warn: 'bg-amber-400',
  unknown: 'bg-slate-500',
};

export default function StatusDot({ status = 'unknown', label, pulse = true, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${STYLES[status] || STYLES.unknown} ${
          pulse && status === 'online' ? 'animate-pulse-soft' : ''
        }`}
      />
      {label && <span className="text-xs font-medium text-slate-300">{label}</span>}
    </span>
  );
}
