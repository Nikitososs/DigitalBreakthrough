import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { scoreColor } from '../utils/scoreColor'

function riskBadge(score) {
  if (score >= 75) return { label: 'Критический', Icon: TrendingUp,   bg: '#fef2f2', text: '#dc2626' }
  if (score >= 60) return { label: 'Высокий',     Icon: TrendingUp,   bg: '#fff7ed', text: '#ea580c' }
  if (score >= 45) return { label: 'Умеренный',   Icon: Minus,        bg: '#fefce8', text: '#ca8a04' }
  return                  { label: 'Стабильный',  Icon: TrendingDown, bg: '#f0fdf4', text: '#16a34a' }
}

export default function Top10Table({ districts, onDistrictClick }) {
  if (!districts.length) {
    return (
      <p className="px-4 py-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
        Нет данных для рейтинга
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2 px-1 py-1">
      {districts.map((d, i) => {
        const color = scoreColor(d.score)
        const risk = riskBadge(d.score)
        return (
          <button
            key={d.id}
            type="button"
            onClick={() => onDistrictClick(d)}
            className="w-full text-left transition-all duration-200 focus:outline-none"
            style={{
              borderRadius: '20px',
              padding: '16px 18px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              boxShadow: `0 4px 16px ${color}33`,
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = color; e.currentTarget.style.boxShadow = `0 8px 28px ${color}55` }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = `0 4px 16px ${color}33` }}
          >
            {/* Шапка: номер + капсула слева, балл справа */}
            <div className="flex items-start justify-between mb-2 gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="text-[10px] font-bold w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                  style={{ background: 'var(--bg-sub)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                >
                  {i + 1}
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide"
                  style={{ background: risk.bg, color: risk.text }}
                >
                  <risk.Icon className="w-3 h-3" />
                  {risk.label}
                </span>
              </div>
              <span className="text-2xl font-black tabular-nums flex-shrink-0" style={{ color }}>
                {d.score}
              </span>
            </div>

            {/* Прогресс-бар */}
            <div className="h-1 rounded-full overflow-hidden mb-3" style={{ background: 'var(--bg-sub)' }}>
              <div className="h-full rounded-full" style={{ width: `${d.score}%`, background: color }} />
            </div>

            {/* Название */}
            <p className="font-bold text-sm leading-snug mb-1" style={{ color: 'var(--text)' }}>
              {d.name}
            </p>

            {/* Топ-проблема */}
            {d.topProblem && d.topProblem !== '—' && (
              <p className="text-[13px] leading-snug mb-2" style={{ color: 'var(--text-2)' }}>
                {d.topProblem}
              </p>
            )}

            {/* Саммари */}
            {d.summary && (
              <p className="text-[13px] leading-relaxed line-clamp-3" style={{ color: 'var(--muted)' }}>
                {d.summary}
              </p>
            )}
          </button>
        )
      })}
    </div>
  )
}
