import { memo, useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react'
import {
  Loader2,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  BarChart3,
  CalendarRange,
  MapPin,
  Tags,
  Activity,
  Flame,
  Minus,
  Info,
  Sparkles,
  Building2,
  Clock,
  Map,
  Eye,
  EyeOff,
  BotMessageSquare,
} from 'lucide-react'
import OmskMap from '../components/OmskMap'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ComposedChart,
  Area,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import { api } from '../api/client'

const HORIZONS = [2, 4, 8]
const CHART_H_MAIN = 300
const CHART_H_SIDE = 260

const RISK_COLORS = {
  высокий: '#dc2626',
  средний: '#ea580c',
  стабильный: '#64748b',
  снижение: '#16a34a',
  'низкая уверенность': '#94a3b8',
}

const SEVERITY_COLORS = {
  1: '#84cc16',
  2: '#eab308',
  3: '#f97316',
  4: '#dc2626',
}

const CHART = {
  grid: 'color-mix(in srgb, var(--border) 80%, transparent)',
  actual: '#2563eb',
  actualDark: '#3b82f6',
  forecast: '#ea580c',
  forecastLine: '#c2410c',
  monthly: '#6366f1',
  margin: { top: 12, right: 12, left: 4, bottom: 4 },
}

function formatWeek(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function formatMonth(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 7)
  return d.toLocaleDateString('ru-RU', { month: 'short', year: '2-digit' })
}

function formatAxis(n) {
  if (n == null || Number.isNaN(n)) return ''
  const v = Number(n)
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 10_000) return `${Math.round(v / 1000)}k`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`
  return String(Math.round(v))
}

function yDomain(values, pad = 0.12) {
  const nums = values.filter((v) => v != null && !Number.isNaN(v))
  if (!nums.length) return [0, 10]
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const span = Math.max(max - min, max * 0.15, 1)
  return [Math.max(0, min - span * pad), max + span * pad]
}

function RiskBadge({ level }) {
  const color = RISK_COLORS[level] || '#64748b'
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold"
      style={{
        background: `color-mix(in srgb, ${color} 12%, var(--bg-card))`,
        color,
        border: `1px solid color-mix(in srgb, ${color} 30%, var(--border))`,
      }}
    >
      {level}
    </span>
  )
}

function Skeleton({ className = '' }) {
  return (
    <div
      className={`animate-pulse rounded-xl ${className}`}
      style={{ background: 'color-mix(in srgb, var(--muted) 18%, var(--bg-sub))' }}
    />
  )
}

function ForecastSkeleton() {
  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-5 space-y-4">
      <Skeleton className="h-14" />
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
      <div className="flex gap-1 p-1 rounded-xl overflow-x-auto">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-20 flex-shrink-0" />
        ))}
      </div>
      <Skeleton className="h-[460px]" />
    </div>
  )
}

const TOOLTIP_LABELS = {
  actual: 'Факт',
  predicted: 'Прогноз',
  count: 'Обращений',
  forecastUpperBound: 'Верхняя граница',
  forecastLowerBound: 'Нижняя граница',
}

const ChartTooltip = memo(({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload || {}
  const seen = new Set()
  const rangeLow = row.forecastLowerBound
  const rangeHigh = row.forecastUpperBound
  const showRange = rangeLow != null && rangeHigh != null
  return (
    <div
      className="rounded-xl px-3 py-2.5 shadow-xl text-xs min-w-[140px]"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        color: 'var(--text)',
        boxShadow: '0 8px 24px color-mix(in srgb, #000 12%, transparent)',
      }}
    >
      <div className="font-semibold mb-1.5" style={{ color: 'var(--text)' }}>
        {label || row.periodLabel}
      </div>
      {payload
        .filter((p) => {
          if (p.value == null || seen.has(p.dataKey)) return false
          if (showRange && (p.dataKey === 'forecastUpperBound' || p.dataKey === 'forecastLowerBound')) return false
          seen.add(p.dataKey)
          return true
        })
        .map((p) => (
          <div key={p.dataKey} className="flex justify-between gap-4 tabular-nums" style={{ color: 'var(--text-2)' }}>
            <span>{TOOLTIP_LABELS[p.dataKey] || p.name || p.dataKey}</span>
            <strong>{Math.round(Number(p.value)).toLocaleString('ru-RU')}</strong>
          </div>
        ))}
      {showRange && (
        <div className="flex justify-between gap-4 tabular-nums" style={{ color: 'var(--text-2)' }}>
          <span>Диапазон прогноза</span>
          <strong>
            {Math.round(Number(rangeLow)).toLocaleString('ru-RU')}
            {' – '}
            {Math.round(Number(rangeHigh)).toLocaleString('ru-RU')}
          </strong>
        </div>
      )}
      {row.share_pct != null && (
        <div className="mt-1 pt-1" style={{ borderTop: '1px solid var(--border)', color: 'var(--muted)' }}>
          Доля: {row.share_pct}%
        </div>
      )}
    </div>
  )
})

const HORIZON_HINTS = {
  2: 'Краткий — ближайшие 2 недели',
  4: 'Базовый — месяц вперёд',
  8: 'Расширенный — 2 месяца',
}

const CHART_H_FOCUS = 380

const CHART_VIEWS = [
  {
    id: 'weekly',
    label: 'Недельный',
    short: 'Недели',
    icon: TrendingUp,
    description: '26 недель истории и прогноз на выбранный горизонт',
  },
  {
    id: 'monthly',
    label: 'Помесячный',
    short: 'Месяцы',
    icon: CalendarRange,
    description: 'Сумма обращений за календарный месяц за 24 месяца',
  },
  {
    id: 'critical',
    label: 'Критичные',
    short: '3–4',
    icon: Flame,
    description: 'Обращения классов 3–4 (высокая и критическая тяжесть): недельный тренд и прогноз',
  },
  {
    id: 'structure',
    label: 'Структура',
    short: 'Структура',
    icon: BarChart3,
    description: 'Где сосредоточена нагрузка за последние 12 недель',
    subs: [
      { id: 'muni', label: 'МО', icon: MapPin },
      { id: 'topics', label: 'Темы', icon: Tags },
      { id: 'groups', label: 'Группы', icon: BarChart3 },
      { id: 'agencies', label: 'Ведомства', icon: Building2 },
    ],
  },
  {
    id: 'profile',
    label: 'Профиль',
    short: 'Профиль',
    icon: Flame,
    description: 'Распределение обращений по классам тяжести',
  },
  {
    id: 'heatmap',
    label: 'Карта',
    short: 'Карта',
    icon: Map,
    description: 'Прогнозная нагрузка по муниципалитетам на карте области (цвет = тренд и ожидаемый объём)',
    subs: [
      { id: 'geo', label: 'Карта МО', icon: Map },
      { id: 'matrix', label: 'Таблица', icon: BarChart3 },
    ],
  },
  {
    id: 'processing',
    label: 'Сроки',
    short: 'Сроки',
    icon: Clock,
    description: 'Скорость закрытия обращений и баланс притока / закрытия по неделям',
    subs: [
      { id: 'flow', label: 'Приток / закрытие', icon: Activity },
      { id: 'agencies', label: 'По ведомствам', icon: Building2 },
    ],
  },
  {
    id: 'trends',
    label: 'Тренды',
    short: 'Тренды',
    icon: AlertTriangle,
    description: 'МО и темы с наибольшим ростом или снижением',
    subs: [
      { id: 'rising', label: 'Рост', icon: TrendingUp },
      { id: 'declining', label: 'Снижение', icon: TrendingDown },
    ],
  },
]

function formatDateRu(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function trendDirection(trendPct) {
  if (trendPct > 8) return { label: 'Рост', Icon: TrendingUp, color: '#dc2626' }
  if (trendPct < -8) return { label: 'Снижение', Icon: TrendingDown, color: '#16a34a' }
  return { label: 'Стабильно', Icon: Minus, color: '#64748b' }
}

function buildInsights(data, horizon) {
  const region = data?.region_chart || data?.region_series
  const kpis = data?.kpis
  if (!region || !kpis) return null

  const trend = region.trend_pct ?? 0
  const avg = kpis.avg_weekly_12w ?? 0
  const forecastAvg = kpis.forecast_avg_weekly ?? 0
  const deltaPct = avg > 0 ? Math.round(((forecastAvg - avg) / avg) * 100) : 0
  const expectedTotal = kpis.forecast_total ?? 0
  const baselineTotal = avg * horizon

  return {
    trend,
    deltaPct,
    avg,
    forecastAvg,
    expectedTotal,
    baselineTotal,
    nextWeek: region.forecast_next_week,
    risk: region.risk_level,
    lastWeek: region.last_week_actual,
    risingMuni: data.rising_municipalities?.[0],
    risingTopic: data.rising_topics?.[0],
    peakCount: kpis.peak_week_count,
    peakDate: kpis.peak_week_date,
    direction: trendDirection(trend),
  }
}

function InsightHero({ data, horizon, summaryText }) {
  const insights = buildInsights(data, horizon)
  if (!insights) return null
  const { direction, trend, deltaPct, expectedTotal, baselineTotal, nextWeek, risk, lastWeek, risingMuni, risingTopic, peakCount, peakDate } = insights
  const DirIcon = direction.Icon

  return (
    <div
      className="rounded-2xl p-4 sm:p-5 space-y-4"
      style={{
        background: `linear-gradient(135deg, color-mix(in srgb, ${direction.color} 8%, var(--bg-card)), var(--bg-card))`,
        border: `1px solid color-mix(in srgb, ${direction.color} 22%, var(--border))`,
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: `color-mix(in srgb, ${direction.color} 14%, var(--bg-sub))` }}
          >
            <DirIcon className="w-5 h-5" style={{ color: direction.color }} />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>Главный вывод</p>
            <h3 className="text-lg sm:text-xl font-black mt-0.5" style={{ color: 'var(--text)' }}>
              {direction.label} обращений на {horizon} нед.
            </h3>
            <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>
              Тренд {trend > 0 ? '+' : ''}{Math.round(trend)}% · прогноз ~{Math.round(insights.forecastAvg).toLocaleString('ru-RU')}/нед.
              {deltaPct !== 0 && (
                <span style={{ color: deltaPct > 0 ? '#dc2626' : '#16a34a' }}>
                  {' '}({deltaPct > 0 ? '+' : ''}{deltaPct}% к среднему за 12 нед.)
                </span>
              )}
            </p>
          </div>
        </div>
        <RiskBadge level={risk} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {[
          { label: 'Следующая неделя', value: nextWeek != null ? `~${Math.round(nextWeek).toLocaleString('ru-RU')}` : '—', hint: 'ожидаемый объём' },
          { label: `Сумма за ${horizon} нед.`, value: Math.round(expectedTotal).toLocaleString('ru-RU'), hint: 'прогноз всего' },
          { label: 'Прошлая неделя', value: lastWeek != null ? Math.round(lastWeek).toLocaleString('ru-RU') : '—', hint: 'факт' },
          { label: 'Пик за период', value: peakCount?.toLocaleString('ru-RU') ?? '—', hint: peakDate ? formatDateRu(peakDate) : 'макс. неделя' },
        ].map((item) => (
          <div key={item.label} className="rounded-xl px-3 py-2.5" style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}>
            <p className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'var(--muted)' }}>{item.label}</p>
            <p className="text-lg font-black tabular-nums mt-0.5" style={{ color: 'var(--text)' }}>{item.value}</p>
            <p className="text-[10px] mt-0.5 truncate" style={{ color: 'var(--muted)' }} title={item.hint}>{item.hint}</p>
          </div>
        ))}
      </div>

      {(risingMuni || risingTopic) && (
        <div className="flex flex-wrap gap-2 text-xs">
          {risingMuni && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: 'color-mix(in srgb, #ea580c 10%, var(--bg-sub))', color: '#c2410c' }}>
              <MapPin className="w-3 h-3" />
              Рост: {risingMuni.label} ({risingMuni.trend_pct > 0 ? '+' : ''}{risingMuni.trend_pct}%)
            </span>
          )}
          {risingTopic && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: 'color-mix(in srgb, #8b5cf6 10%, var(--bg-sub))', color: '#6d28d9' }}>
              <Tags className="w-3 h-3" />
              Тема: {risingTopic.label} ({risingTopic.trend_pct > 0 ? '+' : ''}{risingTopic.trend_pct}%)
            </span>
          )}
        </div>
      )}

      {summaryText && (
        <div className="flex gap-2 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
          <Sparkles className="w-4 h-4 flex-shrink-0 mt-0.5 text-indigo-500" />
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-2)' }}>{summaryText}</p>
        </div>
      )}

      {baselineTotal > 0 && expectedTotal > baselineTotal * 1.08 && (
        <p className="text-xs flex items-start gap-1.5 px-3 py-2 rounded-lg" style={{ background: 'color-mix(in srgb, #dc2626 8%, var(--bg-sub))', color: '#b91c1c' }}>
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          Прогноз на {horizon} нед. ({Math.round(expectedTotal).toLocaleString('ru-RU')}) выше «обычного» сценария ({Math.round(baselineTotal).toLocaleString('ru-RU')}) — имеет смысл усилить контроль по растущим МО и темам.
        </p>
      )}
    </div>
  )
}

function MethodologyNote() {
  return (
    <div className="flex gap-2 text-[11px] leading-relaxed px-3 py-2 rounded-xl" style={{ background: 'var(--bg-sub)', color: 'var(--muted)', border: '1px solid var(--border)' }}>
      <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
      <span>
        Прогноз строится по всем проблемным обращениям из архива БД — решённые и нерешённые (дубликаты файлов не учитываются дважды).
        Для каждой серии берётся линейный тренд за последние 12 недель; синие столбцы — факт, оранжевые — прогноз, заливка — возможный разброс.
      </span>
    </div>
  )
}

function ChartTabBar({ active, onChange }) {
  return (
    <div
      className="flex gap-1 p-1 rounded-xl overflow-x-auto"
      style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
      role="tablist"
      aria-label="Виды графиков"
    >
      {CHART_VIEWS.map((view) => {
        const Icon = view.icon
        const selected = active === view.id
        return (
          <button
            key={view.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(view.id)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-all flex-shrink-0"
            style={selected
              ? { background: 'var(--bg-card)', color: 'var(--text)', boxShadow: '0 1px 4px color-mix(in srgb, #000 8%, transparent)' }
              : { background: 'transparent', color: 'var(--muted)' }}
          >
            <Icon className="w-3.5 h-3.5" style={{ color: selected ? '#dc2626' : 'inherit' }} />
            <span className="hidden sm:inline">{view.label}</span>
            <span className="sm:hidden">{view.short}</span>
          </button>
        )
      })}
    </div>
  )
}

function SubTabBar({ subs, active, onChange }) {
  if (!subs?.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {subs.map((sub) => {
        const Icon = sub.icon
        const selected = active === sub.id
        return (
          <button
            key={sub.id}
            type="button"
            onClick={() => onChange(sub.id)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-colors"
            style={selected
              ? { background: 'color-mix(in srgb, #dc2626 12%, var(--bg-sub))', color: '#dc2626', border: '1px solid color-mix(in srgb, #dc2626 25%, var(--border))' }
              : { background: 'var(--bg-sub)', color: 'var(--muted)', border: '1px solid var(--border)' }}
          >
            {Icon && <Icon className="w-3 h-3" />}
            {sub.label}
          </button>
        )
      })}
    </div>
  )
}

function defaultSubForView(viewId) {
  const view = CHART_VIEWS.find((v) => v.id === viewId)
  return view?.subs?.[0]?.id ?? null
}

function ForecastChartPanel({ viewId, subId, onSubChange, data, regionChart, dark, refreshing, showDetails }) {
  const view = CHART_VIEWS.find((v) => v.id === viewId) || CHART_VIEWS[0]
  const chartHeight = CHART_H_FOCUS

  if (!showDetails && !['weekly', 'monthly', 'critical'].includes(viewId)) {
    return (
      <div
        className="rounded-2xl flex items-center justify-center gap-2 py-16 text-sm"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--muted)' }}
      >
        <Loader2 className="w-4 h-4 animate-spin" />
        Загрузка данных…
      </div>
    )
  }

  let panelBody = null
  switch (viewId) {
    case 'weekly':
      panelBody = <WeeklyChart series={regionChart} dark={dark} avgWeekly={data?.kpis?.avg_weekly_12w} height={chartHeight} />
      break
    case 'critical':
      panelBody = <WeeklyChart series={data?.critical_chart} dark={dark} avgWeekly={null} height={chartHeight} barColorOverride="#dc2626" />
      break
    case 'monthly':
      panelBody = <MonthlyChart data={data?.monthly_series} height={chartHeight} />
      break
    case 'structure':
      if (subId === 'topics') panelBody = <HorizontalBarChart data={data?.top_topics} color="#8b5cf6" maxLabelLen={40} height={chartHeight} />
      else if (subId === 'groups') panelBody = <HorizontalBarChart data={data?.top_groups} color="#6366f1" maxLabelLen={32} height={chartHeight} />
      else if (subId === 'agencies') panelBody = <HorizontalBarChart data={data?.top_agencies} color="#0d9488" maxLabelLen={36} height={chartHeight} />
      else panelBody = <HorizontalBarChart data={data?.top_municipalities} color="#2563eb" height={chartHeight} />
      break
    case 'profile':
      panelBody = <SeverityChart data={data?.severity_breakdown} height={chartHeight} />
      break
    case 'processing':
      panelBody = subId === 'agencies'
        ? <ProcessingAgenciesTable processing={data?.processing} />
        : <ProcessingFlowChart processing={data?.processing} height={chartHeight} />
      break
    case 'heatmap':
      panelBody = subId === 'matrix'
        ? <HeatmapTable heatmap={data?.heatmap} />
        : <ForecastMapPanel districts={data?.map_districts} dark={dark} height={chartHeight} />
      break
    case 'trends':
      panelBody = subId === 'declining' ? (
        <div className="space-y-4">
          <DetailTable title="Снижение — муниципалитеты" items={data?.declining_municipalities || []} emptyText="Нет МО с выраженным снижением" icon={TrendingDown} trendUp={false} />
          <DetailTable title="Снижение — темы" items={data?.declining_topics || []} emptyText="Нет тем с выраженным снижением" icon={TrendingDown} trendUp={false} />
        </div>
      ) : (
        <div className="space-y-4">
          <DetailTable title="Рост — муниципалитеты" items={data?.rising_municipalities || []} emptyText="Нет МО с выраженным ростом" icon={AlertTriangle} trendUp />
          <DetailTable title="Рост — темы" items={data?.rising_topics || []} emptyText="Нет тем с выраженным ростом" icon={AlertTriangle} trendUp />
        </div>
      )
      break
    default:
      break
  }

  return (
    <div className="rounded-2xl overflow-hidden relative" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      {refreshing && (
        <div className="absolute inset-0 z-10 flex items-center justify-center backdrop-blur-[1px]" style={{ background: 'color-mix(in srgb, var(--bg-card) 55%, transparent)' }}>
          <Loader2 className="w-5 h-5 animate-spin text-red-600" />
        </div>
      )}
      <div className="px-4 sm:px-5 py-4 space-y-3" style={{ borderBottom: view.subs ? '1px solid var(--border)' : 'none' }}>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{view.label}</h3>
            <p className="text-[11px] mt-0.5 max-w-xl" style={{ color: 'var(--muted)' }}>{view.description}</p>
          </div>
          {view.subs && <SubTabBar subs={view.subs} active={subId} onChange={onSubChange} />}
        </div>
      </div>
      <div className="p-4 sm:p-5" key={`${viewId}-${subId}`}>
        {panelBody}
      </div>
    </div>
  )
}

function DataQualityKpiRow({ dataQuality }) {
  if (!dataQuality) return null
  const lastUpload = dataQuality.last_upload
    ? formatDateRu(dataQuality.last_upload.slice(0, 10))
    : '—'
  const items = [
    { label: 'С адресом', value: `${dataQuality.address_pct ?? 0}%`, hint: 'has_address' },
    { label: 'Геокод', value: `${dataQuality.geocode_pct ?? 0}%`, hint: 'координаты в БД' },
    { label: 'Дата закрытия', value: `${dataQuality.closed_at_pct ?? 0}%`, hint: 'поле closed_at' },
    { label: 'Ведомств', value: dataQuality.agencies?.toLocaleString('ru-RU') ?? '—', hint: 'уникальных' },
    { label: 'Загрузок', value: dataQuality.jobs_count ?? '—', hint: 'файлов, без live' },
    { label: 'Последняя загрузка', value: lastUpload, hint: 'в БД' },
  ]
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wider mb-2 px-0.5" style={{ color: 'var(--muted)' }}>
        Качество данных
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {items.map((item) => (
          <div key={item.label} className="rounded-xl px-3 py-2" style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}>
            <p className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'var(--muted)' }}>{item.label}</p>
            <p className="text-base font-bold tabular-nums mt-0.5" style={{ color: 'var(--text)' }}>{item.value ?? '—'}</p>
            <p className="text-[10px]" style={{ color: 'var(--muted)' }}>{item.hint}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function ContextKpiRow({ kpis, data }) {
  if (!kpis) return null
  const items = [
    { label: 'В выборке', value: data?.incident_count?.toLocaleString('ru-RU'), hint: 'проблемных обращений' },
    { label: 'Загрузок в БД', value: data?.jobs_count ?? '—', hint: 'файлов, как в архиве' },
    { label: 'Муниципалитетов', value: kpis.municipalities?.toLocaleString('ru-RU'), hint: 'в архиве' },
    { label: 'Тем', value: kpis.topics?.toLocaleString('ru-RU'), hint: 'уникальных' },
    { label: 'История', value: `${kpis.history_weeks ?? 0} нед.`, hint: 'для тренда' },
    { label: 'Рост / спад', value: `${kpis.rising_municipalities ?? 0} / ${kpis.declining_municipalities ?? 0}`, hint: 'МО с трендом' },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl px-3 py-2" style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}>
          <p className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'var(--muted)' }}>{item.label}</p>
          <p className="text-base font-bold tabular-nums mt-0.5" style={{ color: 'var(--text)' }}>{item.value ?? '—'}</p>
          <p className="text-[10px]" style={{ color: 'var(--muted)' }}>{item.hint}</p>
        </div>
      ))}
    </div>
  )
}

const WeeklyChart = memo(function WeeklyChart({ series, dark, avgWeekly, height = CHART_H_MAIN, barColorOverride }) {
  const chartData = useMemo(() => {
    const points = series?.points || []
    return points.map((p) => {
      const low = p.is_forecast ? p.predicted_low : null
      const high = p.is_forecast ? p.predicted_high : null
      return {
        periodLabel: formatWeek(p.period),
        isForecast: p.is_forecast,
        actual: p.is_forecast ? null : p.actual,
        predicted: p.is_forecast ? p.predicted : null,
        forecastLowerBound: low,
        forecastUpperBound: high,
        forecastBandBase: low,
        forecastBandRange: low != null && high != null ? Math.max(0, high - low) : null,
      }
    })
  }, [series])

  const domain = useMemo(
    () => yDomain(chartData.flatMap((d) => [d.actual, d.predicted, d.forecastUpperBound, d.forecastLowerBound, avgWeekly])),
    [chartData, avgWeekly],
  )

  const firstForecastLabel = useMemo(
    () => chartData.find((d) => d.isForecast)?.periodLabel,
    [chartData],
  )

  if (!chartData.length) return null
  const barColor = barColorOverride || (dark ? CHART.actualDark : CHART.actual)

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3 text-[11px]" style={{ color: 'var(--muted)' }}>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: barColor }} /> Факт</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: CHART.forecast }} /> Прогноз</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm opacity-40" style={{ background: CHART.forecast }} /> Диапазон</span>
        {avgWeekly > 0 && (
          <span className="inline-flex items-center gap-1.5"><span className="w-4 h-0 border-t border-dashed" style={{ borderColor: '#6366f1' }} /> Среднее 12 нед.</span>
        )}
      </div>
      <div style={{ height, width: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ ...CHART.margin, left: 8, bottom: 8 }}>
        <defs>
          <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.forecast} stopOpacity={0.4} />
            <stop offset="100%" stopColor={CHART.forecast} stopOpacity={0.08} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" vertical={false} />
        <XAxis
          dataKey="periodLabel"
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={28}
          height={36}
        />
        <YAxis
          domain={domain}
          tickFormatter={formatAxis}
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={52}
          label={{ value: 'обращений / нед.', angle: -90, position: 'insideLeft', fill: 'var(--muted)', fontSize: 10, dx: 8 }}
        />
        <Tooltip content={<ChartTooltip />} />
        {avgWeekly > 0 && (
          <ReferenceLine y={avgWeekly} stroke="#6366f1" strokeDasharray="4 4" strokeWidth={1.5} label={{ value: 'Ø12', position: 'insideTopRight', fill: '#6366f1', fontSize: 10 }} />
        )}
        <Area dataKey="forecastBandBase" stackId="band" fill="transparent" stroke="none" legendType="none" connectNulls />
        <Area dataKey="forecastBandRange" stackId="band" name="Диапазон прогноза" fill="url(#forecastGrad)" stroke="none" legendType="none" connectNulls />
        <Bar dataKey="actual" name="Факт" fill={barColor} radius={[5, 5, 0, 0]} maxBarSize={22} />
        <Bar dataKey="predicted" name="Прогноз" fill={CHART.forecast} fillOpacity={0.88} radius={[5, 5, 0, 0]} maxBarSize={22} />
      </ComposedChart>
      </ResponsiveContainer>
      </div>
      {firstForecastLabel && (
        <p className="text-[11px] text-center" style={{ color: 'var(--muted)' }}>
          Прогноз начинается с недели «{firstForecastLabel}»
        </p>
      )}
    </div>
  )
})

const MonthlyChart = memo(function MonthlyChart({ data, height = CHART_H_MAIN }) {
  const chartData = useMemo(
    () => (data || []).map((p) => ({ ...p, periodLabel: formatMonth(p.period) })),
    [data],
  )
  const domain = useMemo(() => yDomain(chartData.map((d) => d.count)), [chartData])
  if (!chartData.length) return null

  return (
    <div style={{ height, width: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ ...CHART.margin, left: 8, bottom: 8 }}>
        <defs>
          <linearGradient id="monthlyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.monthly} stopOpacity={0.35} />
            <stop offset="100%" stopColor={CHART.monthly} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" vertical={false} />
        <XAxis
          dataKey="periodLabel"
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={20}
          height={36}
        />
        <YAxis
          domain={domain}
          tickFormatter={formatAxis}
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={52}
          label={{ value: 'за мес.', angle: -90, position: 'insideLeft', fill: 'var(--muted)', fontSize: 10, dx: 12 }}
        />
        <Tooltip content={<ChartTooltip />} />
        <Area type="monotone" dataKey="count" name="Обращений за месяц" fill="url(#monthlyGrad)" stroke={CHART.monthly} strokeWidth={2.5} dot={false} />
      </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
})

const HorizontalBarChart = memo(function HorizontalBarChart({ data, color = '#2563eb', maxLabelLen = 28, height: fixedHeight }) {
  const chartData = useMemo(
    () => (data || []).map((row) => ({
      ...row,
      shortLabel: row.label.length > maxLabelLen ? `${row.label.slice(0, maxLabelLen)}…` : row.label,
    })),
    [data, maxLabelLen],
  )
  const domain = useMemo(() => yDomain(chartData.map((d) => d.value)), [chartData])

  if (!chartData.length) {
    return <p className="text-sm text-center py-8" style={{ color: 'var(--muted)' }}>Нет данных</p>
  }

  const height = fixedHeight ?? Math.min(Math.max(200, chartData.length * 34 + 24), 340)

  return (
    <div style={{ height, width: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }}>
        <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" domain={domain} tickFormatter={formatAxis} tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="shortLabel" width={128} tick={{ fill: 'var(--text-2)', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip content={<ChartTooltip />} />
        <Bar dataKey="value" name="Обращений" radius={[0, 6, 6, 0]} maxBarSize={20}>
          {chartData.map((_, i) => (
            <Cell key={i} fill={color} fillOpacity={Math.max(0.45, 0.92 - i * 0.05)} />
          ))}
        </Bar>
      </BarChart>
      </ResponsiveContainer>
    </div>
  )
})

const SeverityChart = memo(function SeverityChart({ data, height = CHART_H_SIDE }) {
  const yMax = useMemo(() => {
    const max = Math.max(...(data || []).map((d) => d.count), 1)
    return Math.ceil(max * 1.1)
  }, [data])
  if (!data?.length) return null
  return (
    <div style={{ height, width: '100%' }}>
      <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 12, right: 12, left: 4, bottom: 4 }} barCategoryGap="20%">
        <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval={0}
          height={40}
        />
        <YAxis
          domain={[0, yMax]}
          allowDecimals={false}
          tickFormatter={formatAxis}
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--bg-sub)', opacity: 0.4 }} />
        <Bar dataKey="count" name="Обращений" baseValue={0} radius={[6, 6, 0, 0]} maxBarSize={48}>
          {data.map((row) => (
            <Cell key={row.severity} fill={SEVERITY_COLORS[row.severity] || '#64748b'} />
          ))}
        </Bar>
      </BarChart>
      </ResponsiveContainer>
    </div>
  )
})

const ProcessingFlowChart = memo(function ProcessingFlowChart({ processing, height = CHART_H_MAIN }) {
  const chartData = useMemo(() => {
    return (processing?.weekly_flow || []).map((p) => ({
      periodLabel: formatWeek(p.period),
      created: p.created,
      closed: p.closed,
    }))
  }, [processing])

  const domain = useMemo(
    () => yDomain(chartData.flatMap((d) => [d.created, d.closed])),
    [chartData],
  )

  if (!processing?.available && (processing?.closed_count ?? 0) < 5) {
    return (
      <div className="text-sm text-center py-12 space-y-2" style={{ color: 'var(--muted)' }}>
        <Clock className="w-8 h-8 mx-auto opacity-40" />
        <p>Срок обработки недоступен: в выгрузке мало или нет дат закрытия (closed_at).</p>
        {processing?.closed_share_pct > 0 && (
          <p className="text-xs">Заполнено только {processing.closed_share_pct}% обращений.</p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { label: 'Медиана закрытия', value: processing.median_days != null ? `${processing.median_days} дн.` : '—' },
          { label: '90-й перцентиль', value: processing.p90_days != null ? `${processing.p90_days} дн.` : '—' },
          { label: 'Закрыто', value: `${processing.closed_share_pct ?? 0}%`, hint: `${processing.closed_count?.toLocaleString('ru-RU')} из ${(processing.closed_count + processing.open_count).toLocaleString('ru-RU')}` },
          { label: 'Открытых', value: processing.open_count?.toLocaleString('ru-RU') ?? '—' },
        ].map((item) => (
          <div key={item.label} className="rounded-xl px-3 py-2" style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}>
            <p className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'var(--muted)' }}>{item.label}</p>
            <p className="text-base font-bold tabular-nums mt-0.5" style={{ color: 'var(--text)' }}>{item.value}</p>
            {item.hint && <p className="text-[10px]" style={{ color: 'var(--muted)' }}>{item.hint}</p>}
          </div>
        ))}
      </div>
      {chartData.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-3 text-[11px]" style={{ color: 'var(--muted)' }}>
            <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: '#2563eb' }} /> Поступило</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: '#16a34a' }} /> Закрыто</span>
          </div>
          <div style={{ height, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ ...CHART.margin, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={CHART.grid} strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="periodLabel" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={28} height={36} />
                <YAxis domain={domain} tickFormatter={formatAxis} tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} width={52} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="created" name="Поступило" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="closed" name="Закрыто" fill="#16a34a" radius={[4, 4, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : null}
    </div>
  )
})

function ProcessingAgenciesTable({ processing }) {
  const items = processing?.slowest_agencies || []
  if (!processing?.available) {
    return (
      <p className="text-sm text-center py-12" style={{ color: 'var(--muted)' }}>
        Недостаточно закрытых обращений с датами для рейтинга ведомств.
      </p>
    )
  }
  if (!items.length) {
    return (
      <p className="text-sm text-center py-12" style={{ color: 'var(--muted)' }}>
        Нет ведомств с ≥3 закрытыми обращениями для расчёта медианы.
      </p>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Ведомство</th>
            <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Медиана, дн.</th>
            <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Закрыто</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.label} style={{ borderBottom: '1px solid var(--border)' }}>
              <td className="px-4 py-2.5 font-medium max-w-[280px]" style={{ color: 'var(--text)' }}>
                <span className="line-clamp-2" title={row.label}>{row.label}</span>
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums font-semibold" style={{ color: '#ea580c' }}>{row.median_days}</td>
              <td className="px-4 py-2.5 text-right tabular-nums" style={{ color: 'var(--muted)' }}>{row.count?.toLocaleString('ru-RU')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ForecastMapPanel({ districts, dark, height = CHART_H_FOCUS }) {
  const [showTiles, setShowTiles] = useState(true)
  const mapped = useMemo(
    () => (districts || []).map((d) => ({
      id: d.id || d.name,
      name: d.name,
      score: d.score,
      trend_pct: d.trend_pct,
      risk_level: d.risk_level,
      forecast_next_week: d.forecast_next_week,
    })),
    [districts],
  )

  if (!mapped.length) {
    return (
      <p className="text-sm text-center py-16" style={{ color: 'var(--muted)' }}>
        Недостаточно данных по муниципалитетам для карты прогноза.
      </p>
    )
  }

  return (
    <div className="space-y-2 flex flex-col" style={{ height }}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 flex-shrink-0">
        {[['#991b1b', 'сильный рост'], ['#f97316', 'рост'], ['#84cc16', 'стабильно'], ['#22c55e', 'снижение'], ['#cbd5e1', 'нет данных']].map(
          ([c, l]) => (
            <div key={l} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
              <span className="text-[11px]" style={{ color: 'var(--muted)' }}>{l}</span>
            </div>
          ),
        )}
        <button
          type="button"
          onClick={() => setShowTiles((t) => !t)}
          className="ml-auto flex-shrink-0 transition-colors"
          style={{ color: showTiles ? 'var(--muted)' : '#dc2626', lineHeight: 0 }}
          title={showTiles ? 'Скрыть подложку' : 'Показать подложку'}
        >
          {showTiles ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
        </button>
      </div>
      <p className="text-[11px] flex-shrink-0" style={{ color: 'var(--muted)' }}>
        Наведите на район: тренд за 12 нед. и прогноз на следующую неделю. {mapped.length} МО в выборке.
      </p>
      <div className="flex-1 min-h-[280px] rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        <OmskMap districts={mapped} showTiles={showTiles} dark={dark} />
      </div>
    </div>
  )
}

function HeatmapTable({ heatmap }) {
  const { municipalities = [], weeks = [], values = [] } = heatmap || {}
  if (!municipalities.length) {
    return <p className="text-sm text-center py-8" style={{ color: 'var(--muted)' }}>Недостаточно данных</p>
  }
  const flat = values.flat()
  const maxVal = Math.max(...flat, 1)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="text-left py-2 pr-2 font-semibold" style={{ color: 'var(--muted)' }}>МО</th>
            {weeks.map((w) => (
              <th key={w} className="px-1 py-2 text-center font-semibold whitespace-nowrap" style={{ color: 'var(--muted)' }}>{w}</th>
            ))}
            <th className="px-2 py-2 text-right font-semibold" style={{ color: 'var(--muted)' }}>Σ</th>
          </tr>
        </thead>
        <tbody>
          {municipalities.map((muni, ri) => {
            const row = values[ri] || []
            const total = row.reduce((a, b) => a + b, 0)
            return (
              <tr key={muni} style={{ borderTop: '1px solid var(--border)' }}>
                <td className="py-2 pr-2 font-medium max-w-[160px] truncate" style={{ color: 'var(--text)' }} title={muni}>{muni}</td>
                {row.map((val, ci) => {
                  const intensity = val / maxVal
                  return (
                    <td key={ci} className="px-1 py-1.5 text-center">
                      <span
                        className="inline-flex items-center justify-center min-w-[32px] h-7 rounded-lg tabular-nums font-semibold"
                        style={{
                          background: `color-mix(in srgb, #2563eb ${Math.round(intensity * 72 + 6)}%, var(--bg-sub))`,
                          color: intensity > 0.5 ? '#fff' : 'var(--text-2)',
                          fontSize: '10px',
                        }}
                        title={`${val} обращений`}
                      >
                        {val || '·'}
                      </span>
                    </td>
                  )
                })}
                <td className="px-2 py-2 text-right tabular-nums font-bold" style={{ color: 'var(--text)' }}>{total.toLocaleString('ru-RU')}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DetailTable({ title, items, emptyText, icon: Icon = AlertTriangle, trendUp = true }) {
  return (
    <div className="rounded-2xl overflow-hidden shadow-sm" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <Icon className={`w-4 h-4 flex-shrink-0 ${trendUp ? 'text-orange-500' : 'text-emerald-500'}`} />
        <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{title}</span>
      </div>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-sm text-center" style={{ color: 'var(--muted)' }}>{emptyText}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Название</th>
                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }} title="Изменение тренда за 12 нед.">Δ %</th>
                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }} title="Ожидаемый объём на след. неделю">След. нед.</th>
                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Всего в истории</th>
                <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Риск</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.label} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-4 py-2.5 font-medium max-w-[200px]" style={{ color: 'var(--text)' }}>
                    <span className="line-clamp-2" title={row.label}>{row.label}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums font-semibold" style={{ color: trendUp ? '#ea580c' : '#16a34a' }}>
                    {row.trend_pct > 0 ? '+' : ''}{row.trend_pct}%
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: 'var(--text-2)' }}>
                    {row.forecast_next_week != null ? Math.round(row.forecast_next_week).toLocaleString('ru-RU') : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums" style={{ color: 'var(--muted)' }}>
                    {row.history_total?.toLocaleString('ru-RU')}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <RiskBadge level={row.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function AiSummaryPanel({ summary, loading, error, onGenerate, onRegenerate, horizon }) {
  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, color-mix(in srgb, #6366f1 8%, var(--bg-card)), var(--bg-card))',
        border: '1px solid color-mix(in srgb, #6366f1 28%, var(--border))',
      }}
    >
      <div className="px-4 sm:px-5 py-3 flex flex-wrap items-center justify-between gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2 min-w-0">
          <BotMessageSquare className="w-4 h-4 text-indigo-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Сводка от ИИ</p>
            <p className="text-[11px]" style={{ color: 'var(--muted)' }}>
              По всем графикам и трендам · горизонт {horizon} нед.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {summary && (
            <button
              type="button"
              onClick={onRegenerate}
              disabled={loading}
              className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold transition-colors disabled:opacity-60"
              style={{ background: 'var(--bg-sub)', color: 'var(--muted)', border: '1px solid var(--border)' }}
            >
              Обновить
            </button>
          )}
          {!summary && (
            <button
              type="button"
              onClick={onGenerate}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-60"
              style={{
                background: loading ? 'var(--bg-sub)' : 'linear-gradient(135deg, #6366f1, #4f46e5)',
                color: loading ? 'var(--muted)' : '#fff',
                border: loading ? '1px solid var(--border)' : 'none',
                boxShadow: loading ? 'none' : '0 2px 10px color-mix(in srgb, #6366f1 35%, transparent)',
              }}
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {loading ? 'Генерация…' : 'Получить сводку'}
            </button>
          )}
        </div>
      </div>
      <div className="px-4 sm:px-5 py-4">
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
        {loading && !summary && (
          <div className="flex items-center gap-2 text-sm py-6 justify-center" style={{ color: 'var(--muted)' }}>
            <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
            ИИ анализирует прогноз, графики и тренды…
          </div>
        )}
        {summary && (
          <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: 'var(--text-2)' }}>
            {summary}
          </p>
        )}
        {!loading && !summary && !error && (
          <p className="text-sm text-center py-4" style={{ color: 'var(--muted)' }}>
            Нажмите «Получить сводку» — ИИ подготовит единый доклад по недельному и помесячному прогнозу,
            критичным обращениям, структуре нагрузки, карте рисков и срокам обработки.
          </p>
        )}
      </div>
    </div>
  )
}

export default function ForecastScreen({ dark }) {
  const [horizon, setHorizon] = useState(4)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [showDetails, setShowDetails] = useState(false)
  const [chartView, setChartView] = useState('weekly')
  const [chartSub, setChartSub] = useState(defaultSubForView('weekly'))
  const [aiSummary, setAiSummary] = useState('')
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false)
  const [aiSummaryError, setAiSummaryError] = useState('')
  const [, startTransition] = useTransition()
  const abortRef = useRef(null)
  const hasDataRef = useRef(false)

  const load = useCallback(async (h = horizon) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    if (!hasDataRef.current) setLoading(true)
    else setRefreshing(true)
    setError('')

    try {
      const res = await api.getForecast(h, { signal: controller.signal })
      if (controller.signal.aborted) return
      hasDataRef.current = true
      startTransition(() => {
        setData(res)
        setShowDetails(false)
        requestAnimationFrame(() => setShowDetails(true))
      })
    } catch (err) {
      if (controller.signal.aborted || err.name === 'AbortError') return
      setError(err.message || 'Не удалось загрузить прогноз')
      if (!hasDataRef.current) setData(null)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [horizon])

  const handleChartViewChange = useCallback((viewId) => {
    setChartView(viewId)
    setChartSub(defaultSubForView(viewId))
  }, [])

  const requestAiSummary = useCallback(async (force = false) => {
    setAiSummaryLoading(true)
    setAiSummaryError('')
    try {
      const res = await api.generateForecastAiSummary(horizon, { force })
      setAiSummary(res.summary || '')
    } catch (err) {
      setAiSummary('')
      setAiSummaryError(err.message || 'Не удалось получить сводку от ИИ')
    } finally {
      setAiSummaryLoading(false)
    }
  }, [horizon])

  useEffect(() => {
    setAiSummary('')
    setAiSummaryError('')
  }, [horizon])

  useEffect(() => {
    load(horizon)
    return () => abortRef.current?.abort()
  }, [horizon, load])

  const regionChart = useMemo(() => data?.region_chart || data?.region_series, [data])
  const periodLabel = useMemo(() => {
    const k = data?.kpis
    if (!k?.date_from || !k?.date_to) return null
    return `${k.date_from} — ${k.date_to}`
  }, [data])

  if (loading && !data) return <ForecastSkeleton />

  if (error && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8">
        <p className="text-red-600 text-sm">{error}</p>
        <button type="button" onClick={() => load()} className="text-sm underline" style={{ color: 'var(--muted)' }}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <BarChart3 className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--muted)' }} />
          <div className="min-w-0">
            <h2 className="text-base font-bold truncate" style={{ color: 'var(--text)' }}>Прогноз проблемных обращений</h2>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
              {periodLabel
                ? `Период данных: ${periodLabel.split(' — ').map(formatDateRu).join(' — ')}`
                : `В выборке ${data?.incident_count?.toLocaleString('ru-RU') ?? '—'} обращений`}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <div className="flex flex-wrap items-center gap-2 justify-end">
            <button
              type="button"
              onClick={() => requestAiSummary(Boolean(aiSummary))}
              disabled={aiSummaryLoading || refreshing || !data}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-60"
              style={{
                background: 'color-mix(in srgb, #6366f1 12%, var(--bg-sub))',
                color: '#4f46e5',
                border: '1px solid color-mix(in srgb, #6366f1 30%, var(--border))',
              }}
              title="Единая AI-сводка по всем графикам и трендам"
            >
              {aiSummaryLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Сводка от ИИ
            </button>
            <div className="inline-flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}>
              {HORIZONS.map((w) => (
                <button
                  key={w}
                  type="button"
                  disabled={refreshing}
                  onClick={() => setHorizon(w)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors disabled:opacity-60"
                  style={horizon === w ? { background: '#dc2626', color: '#fff' } : { background: 'transparent', color: 'var(--muted)' }}
                  title={HORIZON_HINTS[w]}
                >
                  {w} нед.
                </button>
              ))}
            </div>
          </div>
          <span className="text-[10px]" style={{ color: 'var(--muted)' }}>{HORIZON_HINTS[horizon]}</span>
        </div>
      </div>

      {refreshing && (
        <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-xl" style={{ background: 'var(--bg-sub)', color: 'var(--muted)' }}>
          <Loader2 className="w-3.5 h-3.5 animate-spin text-red-600" />
          Обновление прогноза…
        </div>
      )}

      <InsightHero data={data} horizon={horizon} summaryText={data?.summary_text} />

      {(aiSummary || aiSummaryLoading || aiSummaryError) && (
        <AiSummaryPanel
          summary={aiSummary}
          loading={aiSummaryLoading}
          error={aiSummaryError}
          horizon={horizon}
          onGenerate={() => requestAiSummary(false)}
          onRegenerate={() => requestAiSummary(true)}
        />
      )}

      <ContextKpiRow kpis={data?.kpis} data={data} />
      {showDetails && <DataQualityKpiRow dataQuality={data?.data_quality} />}
      <MethodologyNote />

      <ChartTabBar active={chartView} onChange={handleChartViewChange} />

      <ForecastChartPanel
        viewId={chartView}
        subId={chartSub}
        onSubChange={setChartSub}
        data={data}
        regionChart={regionChart}
        dark={dark}
        refreshing={refreshing}
        showDetails={showDetails}
      />
    </div>
  )
}
