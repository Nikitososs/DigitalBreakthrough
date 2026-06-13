import { Play, Square } from 'lucide-react'

export default function LiveDatasetDemoButton({ playback, className = '' }) {
  const { active, sent, error, canRun, sourceFile, toggle } = playback

  if (!canRun) return null

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <button
        type="button"
        onClick={toggle}
        className="inline-flex items-center gap-1 px-1.5 h-7 rounded-lg text-[10px] font-medium transition-opacity hover:opacity-80"
        style={{
          background: 'transparent',
          border: 'none',
          color: active ? '#16a34a' : 'var(--muted)',
        }}
        title={active ? 'Остановить demo-поток' : `Demo: циклическая отправка из ${sourceFile}`}
      >
        {active ? (
          <>
            <Square className="w-3 h-3" />
            <span className="hidden lg:inline">стоп</span>
          </>
        ) : (
          <>
            <Play className="w-3 h-3 opacity-60" />
            <span className="hidden lg:inline">demo</span>
          </>
        )}
      </button>
      {active && sent > 0 && (
        <span className="hidden xl:inline text-[9px] tabular-nums opacity-60" style={{ color: 'var(--muted)' }}>
          {sent}
        </span>
      )}
      {error && (
        <span className="text-[9px] text-red-600 max-w-[6rem] truncate opacity-80" title={error}>
          !
        </span>
      )}
    </div>
  )
}
