import { CalendarRange } from 'lucide-react'
import { DATE_PRESETS } from '../utils/incidentDateFilter'

export default function IncidentDateFilter({
  preset,
  onPresetChange,
  from,
  to,
  onFromChange,
  onToChange,
  compact = false,
  visiblePresets = null,
}) {
  const chipCls = compact
    ? 'px-2 py-0.5 rounded-md text-[11px] font-semibold transition-all'
    : 'px-2 py-1 rounded-md text-xs font-semibold transition-all'

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <CalendarRange className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--muted)' }} />
      {DATE_PRESETS.filter((p) => p.id !== 'custom' && (!visiblePresets || visiblePresets.includes(p.id))).map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onPresetChange(p.id)}
          className={chipCls}
          style={{
            background: preset === p.id ? '#dc2626' : 'var(--bg-sub)',
            color: preset === p.id ? '#fff' : 'var(--muted)',
          }}
        >
          {p.label}
        </button>
      ))}
      {(!visiblePresets || visiblePresets.includes('custom')) && (
        <button
          type="button"
          onClick={() => onPresetChange('custom')}
          className={chipCls}
          style={{
            background: preset === 'custom' ? '#dc2626' : 'var(--bg-sub)',
            color: preset === 'custom' ? '#fff' : 'var(--muted)',
          }}
        >
          Период
        </button>
      )}
      {preset === 'custom' && (
        <>
          <input
            type="date"
            value={from}
            onChange={(e) => onFromChange(e.target.value)}
            className="text-xs px-2 py-1 rounded-lg border outline-none"
            style={{ borderColor: 'var(--border)', background: 'var(--bg-card)', color: 'var(--text-2)' }}
            title="С даты"
          />
          <span className="text-xs" style={{ color: 'var(--muted)' }}>—</span>
          <input
            type="date"
            value={to}
            onChange={(e) => onToChange(e.target.value)}
            className="text-xs px-2 py-1 rounded-lg border outline-none"
            style={{ borderColor: 'var(--border)', background: 'var(--bg-card)', color: 'var(--text-2)' }}
            title="По дату"
          />
        </>
      )}
    </div>
  )
}
