import { useEffect, useRef, useState, useMemo } from 'react'
import {
  ArrowLeft,
  Download,
  FileType,
  Tags,
  Route,
  Leaf,
  Bus,
  Lightbulb,
  TreeDeciduous,
  Building2,
  BotMessageSquare,
  FileSearch,
  Loader2,
  Send,
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import ThemeToggle from '../components/ThemeToggle'
import TaskTimingPopover from '../components/TaskTimingPopover'
import { api } from '../api/client'
import { districtFromReport } from '../api/adapters'
import { demoMeta, getDemoDistrictReport } from '../demo'
import { districtToReportPayload } from '../utils/districtReportPayload'
import { cleanAppealText } from '../utils/cleanAppealText'
import { scoreColor } from '../utils/scoreColor'

const CATEGORY_ICONS = {
  ЖКХ: Building2,
  Дороги: Route,
  Экология: Leaf,
  Транспорт: Bus,
  Освещение: Lightbulb,
  Благоустройство: TreeDeciduous,
}

const SEVERITY_COLORS = {
  0: '#94a3b8',
  1: '#84cc16',
  2: '#eab308',
  3: '#f97316',
  4: '#dc2626',
}

const SeverityTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div
      className="rounded-lg px-3 py-2 shadow-lg text-sm"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)' }}
    >
      {row.label}: <strong>{row.count}</strong> ({row.percentage}%)
    </div>
  )
}

const LEFT_CARD_CHROME = 84
const COMPACT_CATEGORIES_MAX = 8

function SeverityChartCard({ severityStat, cardStyle }) {
  const rows = (severityStat || []).filter((s) => s.severity > 0 && s.count > 0)
  if (!rows.length) return null

  return (
    <div className="p-5 shadow-sm flex-shrink-0" style={cardStyle}>
      <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>
        Распределение по тяжести (нерешённые)
      </h2>
      <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>
        Только нерешённые проблемные обращения · классы 1–4
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: 'var(--muted)', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval={0}
            angle={-12}
            textAnchor="end"
            height={48}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: 'var(--muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<SeverityTooltip />} cursor={{ fill: 'var(--bg-sub)' }} />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
            {rows.map((row) => (
              <Cell key={row.severity} fill={SEVERITY_COLORS[row.severity] ?? '#94a3b8'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function DrilldownScreen({ district: initialDistrict, taskId, isDemo, onBack, onSendToOperator, dark, onToggleTheme }) {
  const [district, setDistrict] = useState(initialDistrict)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const rightColRef = useRef(null)
  const leftListRef = useRef(null)
  const [rightColHeight, setRightColHeight] = useState(null)
  const [listContentHeight, setListContentHeight] = useState(0)

  useEffect(() => {
    const el = rightColRef.current
    if (!el) return undefined

    const mq = window.matchMedia('(min-width: 1024px)')
    const syncHeight = () => {
      if (mq.matches) {
        setRightColHeight(Math.round(el.getBoundingClientRect().height))
      } else {
        setRightColHeight(null)
      }
    }

    const ro = new ResizeObserver(syncHeight)
    ro.observe(el)
    mq.addEventListener('change', syncHeight)
    syncHeight()

    return () => {
      ro.disconnect()
      mq.removeEventListener('change', syncHeight)
    }
  }, [district, loading])

  useEffect(() => {
    const list = leftListRef.current
    if (!list) return undefined

    const syncListHeight = () => setListContentHeight(list.scrollHeight)
    const ro = new ResizeObserver(syncListHeight)
    ro.observe(list)
    syncListHeight()

    return () => ro.disconnect()
  }, [district.problems, loading])

  useEffect(() => {
    setDistrict(initialDistrict)
  }, [initialDistrict])

  useEffect(() => {
    if (isDemo || !taskId) {
      const snap = getDemoDistrictReport(initialDistrict.id)
      if (snap?.data) {
        setDistrict((prev) => ({ ...prev, ...districtFromReport(snap.data) }))
      }
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        const res = await api.getDistrictReport(taskId, initialDistrict.id)
        if (cancelled) return
        setDistrict((prev) => ({ ...prev, ...districtFromReport(res.data) }))
      } catch {
        /* keep preview from dashboard */
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [taskId, isDemo, initialDistrict.id])

  const total =
    district.totalIncidents
    ?? district.problems.reduce((s, p) => s + p.count, 0)
  const unresolvedSeverityStat = useMemo(
    () => (district.severityStat || []).filter((s) => s.severity > 0 && s.count > 0),
    [district.severityStat],
  )
  const unresolvedProblemsTotal = useMemo(() => {
    if (district.problemCount != null && district.resolvedCount != null) {
      return Math.max(0, district.problemCount - district.resolvedCount)
    }
    return district.problems.reduce((s, p) => s + p.count, 0)
  }, [district.problemCount, district.resolvedCount, district.problems])
  const color = scoreColor(district.score)
  const max = district.problems[0]?.count || 1
  const categoriesListMaxHeightClass = district.summary
    ? 'max-h-[min(calc(100vh-19rem),720px)]'
    : 'max-h-[min(calc(100vh-12rem),780px)]'
  const categoriesNaturalHeight = LEFT_CARD_CHROME + listContentHeight
  const categoriesOverflows = Boolean(rightColHeight && categoriesNaturalHeight > rightColHeight)
  const compactLayout = Boolean(
    unresolvedSeverityStat.length > 0
    && district.problems.length > 0
    && district.problems.length <= COMPACT_CATEGORIES_MAX
    && !categoriesOverflows,
  )
  const categoriesScrollInside = categoriesOverflows && !compactLayout
  const categoriesAlignHeight = !compactLayout && rightColHeight
    ? Math.min(rightColHeight, categoriesNaturalHeight)
    : null

  const resolvedPct = district.resolvedPct
  const resolvedColor = resolvedPct == null
    ? undefined
    : resolvedPct >= 60
      ? '#16a34a'
      : resolvedPct >= 35
        ? '#eab308'
        : '#f97316'
  const resolvedValue = resolvedPct != null
    ? `${Number(resolvedPct).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%`
    : '—'
  const resolvedSub = district.resolvedCount != null && district.problemCount != null
    ? `${district.resolvedCount.toLocaleString('ru-RU')} из ${district.problemCount.toLocaleString('ru-RU')} проблем`
    : 'нет поля «Итог» (AD) в данных'

  const handlePdfExport = async () => {
    if (exportingPdf) return
    setExportingPdf(true)
    try {
      if (taskId && !isDemo) {
        await api.downloadDistrictPdf(taskId, district.id)
      } else {
        await api.downloadDistrictPdfFromData(districtToReportPayload(district))
      }
    } catch (err) {
      console.error(err)
      alert(err.message || 'Не удалось сформировать PDF.')
    } finally {
      setExportingPdf(false)
    }
  }

  const handleDownload = () => {
    const excelJobId = taskId || (isDemo ? demoMeta.source_job : null)
    if (excelJobId) {
      api.downloadExcelTop10(excelJobId).catch((err) => alert(err.message || 'Не удалось скачать Excel'))
      return
    }
    const lines = [
      `Отчёт: ${district.name}`,
      `Скор: ${district.score}`,
      `Топ-проблема: ${district.topProblem}`,
      `Обращений: ${total}`,
      '',
      'Проблемы (нерешённые):',
      ...district.problems.map((p) => `  ${p.category}: ${p.count}`),
      '',
      'Классы тяжести (нерешённые):',
      ...unresolvedSeverityStat.map(
        (s) => `  ${s.label}: ${s.count}${s.percentage != null ? ` (${s.percentage}%)` : ''}`,
      ),
      '',
      'Сводка:',
      district.summary,
      '',
      'Примеры:',
      ...district.examples.map((e, i) => `  ${i + 1}. [${e.label || e.severity}] ${e.text}`),
    ]
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }))
    Object.assign(document.createElement('a'), {
      href: url,
      download: `zeroproblems-${district.id}.txt`,
    }).click()
    URL.revokeObjectURL(url)
  }

  const handleFullReport = async () => {
    if (!taskId) return
    setGenerating(true)
    try {
      const gen = await api.generateDistrictReport(taskId, district.id)
      const wait = async () => {
        const st = await api.getGenerateStatus(gen.task_id)
        if (st.status === 'completed') {
          const res = await api.getDistrictReport(taskId, district.id)
          setDistrict((prev) => ({ ...prev, ...districtFromReport(res.data) }))
          setGenerating(false)
          return
        }
        if (st.status === 'failed') {
          setGenerating(false)
          return
        }
        setTimeout(wait, 2000)
      }
      await wait()
    } catch {
      setGenerating(false)
    }
  }

  const card = { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 16 }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg)' }}>
      <header
        className="drilldown-header sticky top-0 z-50 shadow-sm"
        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="drilldown-header__main px-3 sm:px-5 pt-2.5 sm:pt-3.5 pb-2">
          <button
            type="button"
            onClick={onBack}
            className="drilldown-header__back"
            aria-label="Назад"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden min-[400px]:inline">Назад</span>
          </button>

          <div className="drilldown-header__info min-w-0">
            <div className="drilldown-header__title-row">
              <h1 className="drilldown-header__title">{district.name}</h1>
              <span
                className="drilldown-header__score"
                style={{ color, background: `${color}18`, borderColor: `${color}40` }}
              >
                Скор {district.score}
              </span>
            </div>
            <div className="drilldown-header__task">
              <div className="sm:hidden">
                <TaskTimingPopover
                  taskId={taskId}
                  isDemo={isDemo}
                  sourceJob={isDemo ? demoMeta.source_job : null}
                  compact
                />
              </div>
              <div className="hidden sm:block">
                <TaskTimingPopover
                  taskId={taskId}
                  isDemo={isDemo}
                  sourceJob={isDemo ? demoMeta.source_job : null}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="drilldown-header__toolbar px-3 sm:px-5 pb-2.5 sm:pb-3.5">
          {onSendToOperator && (
            <button
              type="button"
              onClick={() => onSendToOperator(district.name)}
              className="drilldown-header__btn drilldown-header__btn--ghost"
              title="В ведомство"
              aria-label="В ведомство"
            >
              <Send className="w-4 h-4" />
              <span className="drilldown-header__btn-label sm:hidden">Ведомство</span>
              <span className="drilldown-header__btn-label hidden sm:inline">В ведомство</span>
            </button>
          )}
          {taskId && (
            <button
              type="button"
              onClick={handleFullReport}
              disabled={generating}
              className="drilldown-header__btn drilldown-header__btn--primary"
              title={generating ? 'Генерация…' : 'Сгенерировать сводку'}
            >
              <FileSearch className="w-4 h-4 flex-shrink-0" />
              <span className="drilldown-header__btn-label">
                {generating ? '…' : <><span className="sm:hidden">Сводка</span><span className="hidden sm:inline">Сгенерировать сводку</span></>}
              </span>
            </button>
          )}
          <button
            type="button"
            onClick={handlePdfExport}
            disabled={exportingPdf}
            className="drilldown-header__btn drilldown-header__btn--primary"
            title={exportingPdf ? 'PDF…' : 'Скачать PDF'}
            aria-label="Скачать PDF"
          >
            <FileType className="w-4 h-4" />
            <span className="drilldown-header__btn-label hidden sm:inline">
              {exportingPdf ? 'PDF…' : 'Скачать PDF'}
            </span>
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="drilldown-header__btn drilldown-header__btn--ghost"
            title={(taskId || (isDemo && demoMeta.source_job)) ? 'Excel Top-10' : 'TXT'}
            aria-label="Скачать файл"
          >
            <Download className="w-4 h-4" />
            <span className="drilldown-header__btn-label hidden lg:inline">
              {(taskId || (isDemo && demoMeta.source_job)) ? 'Excel Top-10' : 'TXT'}
            </span>
          </button>
          <div className="drilldown-header__theme">
            <ThemeToggle dark={dark} onToggle={onToggleTheme} />
          </div>
        </div>
      </header>

      {district.summary && (
        <div
          className="mx-4 lg:mx-5 mt-4 p-5 rounded-2xl flex gap-4 anim-up"
          style={{
            background: dark ? 'rgba(234,88,12,0.12)' : '#fff7ed',
            border: '2px solid rgba(234,88,12,0.4)',
          }}
        >
          <BotMessageSquare className="w-6 h-6 text-orange-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-bold text-orange-500 uppercase tracking-widest mb-2">
              Аналитическая сводка · нерешённые проблемы
            </p>
            <p className="text-base leading-relaxed font-medium whitespace-pre-line" style={{ color: dark ? '#fed7aa' : '#9a3412' }}>
              {district.summary}
            </p>
          </div>
        </div>
      )}

      {loading && (
        <div className="mx-4 lg:mx-5 mt-3 px-4 py-2 rounded-xl flex items-center gap-2 text-sm"
          style={{ background: 'var(--bg-sub)', color: 'var(--muted)', border: '1px solid var(--border)' }}>
          <Loader2 className="w-4 h-4 animate-spin text-red-600" />
          Обновление отчёта…
        </div>
      )}

      <div className="flex-1 p-3 sm:p-4 lg:p-5 grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 anim-up lg:items-start">
        <div className="min-h-0 flex flex-col gap-4">
          <div
            className="p-5 shadow-sm flex flex-col min-h-0 flex-shrink-0"
            style={{
              ...card,
              ...(categoriesAlignHeight
                ? { height: categoriesAlignHeight, maxHeight: categoriesAlignHeight }
                : null),
            }}
          >
            <h2 className="text-base font-semibold mb-4 flex-shrink-0" style={{ color: 'var(--text)' }}>Доли категорий</h2>
            {district.problems.length ? (
              <div
                ref={leftListRef}
                className={`space-y-3.5 overflow-x-hidden pr-1 -mr-1 min-h-0 ${
                  categoriesScrollInside ? 'flex-1 overflow-y-auto' : ''
                } ${categoriesAlignHeight ? '' : categoriesListMaxHeightClass}`}
              >
                {district.problems.map((p, i) => {
                  const Icon = CATEGORY_ICONS[p.category] || Tags
                  const barColor = i === 0 ? '#dc2626' : i === 1 ? '#ea580c' : '#94a3b8'
                  return (
                    <div key={p.category} className="flex items-start gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                        style={{ background: `${barColor}18`, color: barColor }}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between text-sm mb-2 gap-3">
                          <span className="font-medium leading-snug" style={{ color: 'var(--text-2)' }}>{p.category}</span>
                          <span className="text-sm flex-shrink-0 tabular-nums" style={{ color: 'var(--muted)' }}>
                            {p.count} · {unresolvedProblemsTotal > 0 ? Math.round((p.count / unresolvedProblemsTotal) * 100) : 0}%
                          </span>
                        </div>
                        <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-sub)' }}>
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${(p.count / max) * 100}%`,
                              background: barColor,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>Нет данных по категориям</p>
            )}
          </div>

          {compactLayout && (
            <SeverityChartCard severityStat={unresolvedSeverityStat} cardStyle={card} />
          )}
        </div>

        <div ref={rightColRef} className="space-y-4">
          <div className="p-5 shadow-sm" style={card}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>Примеры обращений</h2>
            <div
              className="space-y-3 overflow-y-auto pr-1"
              style={{ maxHeight: 'min(42vh, 380px)' }}
            >
              {(district.examples.length ? district.examples : [{ text: 'Нет примеров', severity: 0, label: '' }])
                .map((item, i) => {
                const text = cleanAppealText(typeof item === 'string' ? item : item.text)
                const severity = typeof item === 'string' ? 1 : item.severity
                const label = typeof item === 'string' ? '' : item.label
                const badgeColor = SEVERITY_COLORS[severity] ?? '#94a3b8'
                return (
                  <div
                    key={i}
                    className="flex gap-3 p-3.5 rounded-xl"
                    style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
                  >
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                      style={{ background: 'var(--border)', color: 'var(--text-2)' }}
                    >
                      {i + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      {severity > 0 && label && (
                        <span
                          className="inline-block text-xs font-semibold px-2 py-0.5 rounded-full mb-1.5"
                          style={{ background: `${badgeColor}22`, color: badgeColor }}
                        >
                          {label} · {severity}
                        </span>
                      )}
                      <p className="text-sm leading-relaxed break-words whitespace-pre-wrap" style={{ color: 'var(--text-2)' }}>{text}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2 sm:gap-3 items-stretch">
            {[
              { label: 'Всего обращений', value: total, sub: 'за период' },
              { label: 'Индекс', value: district.score, sub: 'из 100', color },
              { label: 'Топ-категория', value: district.topProblem, sub: 'больше всего жалоб', compactValue: true },
              { label: 'Категорий', value: district.problems.length, sub: 'типов проблем' },
              { label: 'Решено проблем', value: resolvedValue, sub: resolvedSub, color: resolvedColor },
            ].map(({ label, value, sub, color: c, compactValue }) => (
              <div key={label} className="p-4 shadow-sm h-full flex flex-col min-h-0" style={card}>
                <p className="text-xs mb-1 flex-shrink-0" style={{ color: 'var(--muted)' }}>{label}</p>
                <p
                  className={
                    compactValue
                      ? 'flex-1 min-h-0 text-xs sm:text-sm font-semibold leading-snug line-clamp-4'
                      : 'flex-1 min-h-0 text-2xl font-bold leading-none'
                  }
                  style={{ color: c || 'var(--text)' }}
                  title={compactValue ? String(value) : undefined}
                >
                  {value}
                </p>
                <p className="text-xs mt-2 flex-shrink-0" style={{ color: 'var(--muted)' }}>{sub}</p>
              </div>
            ))}
          </div>

          {!compactLayout && (
            <SeverityChartCard severityStat={unresolvedSeverityStat} cardStyle={card} />
          )}
        </div>
      </div>
    </div>
  )
}
