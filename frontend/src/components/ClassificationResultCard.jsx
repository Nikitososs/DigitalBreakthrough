import { Tag, TrendingUp } from 'lucide-react'
import { SEVERITY_COLORS } from '../utils/incidentModel'

const SEVERITY_TITLES = {
  0: { title: 'Не инцидент', desc: 'Обращение не требует реагирования' },
  1: { title: 'Низкая тяжесть', desc: 'Локальная проблема, плановое решение' },
  2: { title: 'Средняя тяжесть', desc: 'Заметная проблема, требует внимания' },
  3: { title: 'Высокая тяжесть', desc: 'Системная проблема, требует оперативного реагирования' },
  4: { title: 'Критическая / ЧС', desc: 'Угроза жизни и здоровью, немедленное реагирование' },
}

const SCALE_LABELS = {
  0: 'Не инцидент',
  4: 'Критическая / ЧС',
}

function SeverityScale({ active }) {
  return (
    <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
      <p className="text-[10px] font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
        Шкала тяжести
      </p>
      <div className="flex items-end gap-1.5">
        {[0, 1, 2, 3, 4].map((level) => {
          const color = SEVERITY_COLORS[level]
          const isActive = level === active
          return (
            <div key={level} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <div
                className="w-full rounded-md transition-all"
                style={{
                  height: isActive ? 10 : 6,
                  background: color,
                  opacity: isActive ? 1 : 0.45,
                  boxShadow: isActive ? `0 0 0 2px ${color}40` : 'none',
                }}
              />
              <span
                className="text-[10px] font-semibold tabular-nums"
                style={{ color: isActive ? color : 'var(--muted)' }}
              >
                {level}
              </span>
            </div>
          )
        })}
      </div>
      <div className="flex justify-between mt-1.5">
        <span className="text-[9px] leading-tight max-w-[40%]" style={{ color: 'var(--muted)' }}>
          {SCALE_LABELS[0]}
        </span>
        <span className="text-[9px] leading-tight text-right max-w-[40%]" style={{ color: 'var(--muted)' }}>
          {SCALE_LABELS[4]}
        </span>
      </div>
    </div>
  )
}

export default function ClassificationResultCard({
  severity,
  label,
  confidence,
  category,
  children,
}) {
  const sev = Number(severity ?? 0)
  const meta = SEVERITY_TITLES[sev] ?? SEVERITY_TITLES[2]
  const accent = SEVERITY_COLORS[sev] ?? SEVERITY_COLORS[2]
  const pct = Math.round((confidence ?? 0) * 1000) / 10
  const displayCategory = category || label || '—'

  return (
    <div
      className="rounded-2xl p-5 shadow-sm"
      style={{
        background: 'var(--bg-card)',
        border: `1px solid ${accent}35`,
        boxShadow: `0 4px 24px ${accent}12`,
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center text-2xl font-bold text-white shadow-md"
          style={{ background: accent }}
        >
          {sev}
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          <h3 className="text-base font-bold leading-tight" style={{ color: accent }}>
            {meta.title}
          </h3>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-2)' }}>
            {meta.desc}
          </p>
        </div>
        <div
          className="flex-shrink-0 w-3 h-3 rounded-full mt-2"
          style={{ background: accent, boxShadow: `0 0 0 4px ${accent}30` }}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 mt-5">
        <div
          className="rounded-xl px-3 py-3"
          style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider uppercase mb-2" style={{ color: 'var(--muted)' }}>
            <Tag className="w-3 h-3" />
            Категория
          </div>
          <p className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>
            {displayCategory}
          </p>
        </div>
        <div
          className="rounded-xl px-3 py-3"
          style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider uppercase mb-2" style={{ color: 'var(--muted)' }}>
            <TrendingUp className="w-3 h-3" />
            Уверенность
          </div>
          <p className="text-sm font-semibold tabular-nums" style={{ color: 'var(--text)' }}>
            {pct}%
          </p>
          <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, pct)}%`, background: accent }}
            />
          </div>
        </div>
      </div>

      <SeverityScale active={sev} />

      {children}
    </div>
  )
}
