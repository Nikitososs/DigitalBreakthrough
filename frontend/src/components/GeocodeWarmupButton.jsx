import { useState } from 'react'
import { Loader2, Map as MapIcon } from 'lucide-react'

function clampProgress(pct) {
  return Math.min(100, Math.max(0, Number(pct) || 0))
}

export default function GeocodeWarmupButton({
  geocodeWarmup,
  startWarmup,
  disabled = false,
  compact = false,
}) {
  const [starting, setStarting] = useState(false)
  const running = geocodeWarmup?.status === 'running'
  const done = geocodeWarmup?.status === 'done' && (geocodeWarmup?.pending_addresses ?? 0) === 0
  const progressPct = clampProgress(geocodeWarmup?.progress_pct)

  const handleClick = async () => {
    if (!startWarmup || running || starting || done) return
    setStarting(true)
    try {
      await startWarmup()
    } finally {
      setStarting(false)
    }
  }

  if (compact && done) return null

  const label = running
    ? `Геокод… ${progressPct.toFixed(1)}%`
    : done
      ? 'Геокоды загружены'
      : 'Подгрузить все геокоды'

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || running || starting || done}
      className={`emergency-geocode-btn flex items-center gap-1.5 rounded-lg font-semibold transition-all ${compact ? 'emergency-geocode-btn--compact px-2 py-1.5 text-xs' : 'px-3 py-1.5 text-xs'}`}
      style={{
        background: running ? 'color-mix(in srgb, #2563eb 12%, var(--bg-card))' : 'var(--bg-card)',
        color: running ? '#1d4ed8' : done ? 'var(--muted)' : 'var(--text-2)',
        border: `1px solid ${running ? 'color-mix(in srgb, #2563eb 35%, var(--border))' : 'var(--border)'}`,
        cursor: running || starting || done ? 'default' : 'pointer',
      }}
      title={done ? 'Геокоды загружены' : 'Nominatim в фоне → таблица geocode_cache в БД'}
    >
      {(running || starting) ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
      ) : (
        <MapIcon className="w-3.5 h-3.5 flex-shrink-0" />
      )}
      {!compact && label}
      {compact && running && label}
    </button>
  )
}
