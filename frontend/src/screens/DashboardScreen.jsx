import { useEffect, useMemo, useRef, useState } from 'react'
import { Zap, TrendingUp, AlertTriangle, RotateCcw, Eye, EyeOff, Loader2, Download, FileType, CalendarRange, Archive, Inbox, PieChart, Database, Users2, Percent, Flame, LocateFixed, ChevronDown, MapPin } from 'lucide-react'
import { getAllDemoDistrictReports, getDemoMergedDashboard, demoMeta } from '../demo'
import { api } from '../api/client'
import { mergeDashboard } from '../api/adapters'
import { formatPeriod, formatIncidentStats } from '../utils/formatPeriod'
import OmskMap from '../components/OmskMap'
import Top10Table from '../components/Top10Table'
import DistrictCard from '../components/DistrictCard'
import ThemeToggle from '../components/ThemeToggle'
import TaskTimingPopover from '../components/TaskTimingPopover'
import LiveDemoPanel from '../components/LiveDemoPanel'
import LiveDatasetDemoButton from '../components/LiveDatasetDemoButton'
import DepartmentReportsModal from '../components/DepartmentReportsModal'
import { useLiveFeed } from '../hooks/useLiveFeed'
import { useLiveDemoPlayback } from '../hooks/useLiveDemoPlayback'
import { liveEventToIncident } from '../utils/incidentModel'
import { LIVE_TASK_ID } from '../constants'
import OperatorScreen from './OperatorScreen'
import ForecastScreen from './ForecastScreen'
import AnalystIncidentsMap from '../components/AnalystIncidentsMap'
import UserMenu from '../components/UserMenu'
import {
  defaultDashboardTabForUser,
  isAdminUser,
  isAnalyticsUser,
  visibleDashboardTabsForUser,
} from '../auth/roles'

const BASE_ROLES = [
  { id: 'analyst', label: 'Аналитика', icon: PieChart },
  { id: 'forecast', label: 'Прогноз', icon: TrendingUp },
  { id: 'operator', label: 'Обращения', icon: Inbox },
]

function defaultRoleForUser(user) {
  return defaultDashboardTabForUser(user)
}

function visibleRolesForUser(user) {
  return visibleDashboardTabsForUser(user, BASE_ROLES)
}

const card = {
  background: 'var(--bg-card)',
  borderColor: 'var(--border)',
  borderWidth: 1,
  borderStyle: 'solid',
}

export default function DashboardScreen({
  taskId,
  isDemo,
  fromArchive = false,
  onDistrictClick,
  onReset,
  onOpenArchive,
  onBackToArchive,
  dark,
  onToggleTheme,
  initialOperatorDistrict,
  onOperatorDistrictConsumed,
  initialDashboardRole,
  onInitialDashboardRoleConsumed,
  initialLiveOn,
  onInitialLiveOnConsumed,
  authUser,
  onLogout,
  onOpenAdmin,
}) {
  const [districts, setDistricts] = useState([])
  const [top10, setTop10] = useState([])
  const [critical, setCritical] = useState([])
  const [periodLabel, setPeriodLabel] = useState(null)
  const [statsLabel, setStatsLabel] = useState(null)
  const [loading, setLoading] = useState(!isDemo)
  const [error, setError] = useState('')
  const [showTiles, setShowTiles] = useState(true)
  const [exportingRegionPdf, setExportingRegionPdf] = useState(false)
  const [deptModalOpen, setDeptModalOpen] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const exportMenuRef = useRef(null)
  const isLiveTask = taskId === LIVE_TASK_ID
  const visibleRoles = useMemo(() => visibleRolesForUser(authUser), [authUser])
  const [role, setRole] = useState(() => defaultRoleForUser(authUser))
  const canLoadDashboard = role === 'analyst' && isAnalyticsUser(authUser)
  const showAnalystChrome = role === 'analyst'
  const canManageArchive = isAdminUser(authUser)
  const liveFeed = useLiveFeed(!isDemo && isLiveTask, { taskId: isLiveTask ? LIVE_TASK_ID : null })
  const liveDemoPlayback = useLiveDemoPlayback({
    enabled: !isDemo && isLiveTask,
    onSubmitted: (incident) => {
      if (incident) liveFeed.ingest(incident)
    },
  })
  const liveMapPins = useMemo(
    () => liveFeed.events
      .map(liveEventToIncident)
      .filter(item => item.lat != null && item.lng != null),
    [liveFeed.events],
  )
  const [kpi, setKpi] = useState(null)
  const [operatorDistrict, setOperatorDistrict] = useState('')
  const [focusIncident, setFocusIncident] = useState(null)
  const [analystMapTab, setAnalystMapTab] = useState('districts')

  useEffect(() => {
    if (initialOperatorDistrict) {
      setOperatorDistrict(initialOperatorDistrict)
      setRole('operator')
      onOperatorDistrictConsumed?.()
    }
  }, [initialOperatorDistrict, onOperatorDistrictConsumed])

  useEffect(() => {
    if (!initialDashboardRole) return
    if (initialDashboardRole === 'emergency' || initialDashboardRole === 'incidents') {
      setRole('analyst')
      setAnalystMapTab('incidents')
    } else {
      setRole(initialDashboardRole)
    }
    onInitialDashboardRoleConsumed?.()
  }, [initialDashboardRole, onInitialDashboardRoleConsumed])

  useEffect(() => {
    if (initialLiveOn) {
      onInitialLiveOnConsumed?.()
    }
  }, [initialLiveOn, onInitialLiveOnConsumed])

  const applyDashboardMeta = (merged, meta = null) => {
    const start = merged.startDate ?? meta?.start_date
    const end = merged.endDate ?? meta?.end_date
    setPeriodLabel(formatPeriod(start, end))
    const total = merged.totalIncidents ?? meta?.rows_total
    const problems = merged.problemCount ?? meta?.problem_count
    setStatsLabel(formatIncidentStats({ totalIncidents: total, problemCount: problems }))
    if (total) setKpi({ total, problems })
  }

  const handleRegionPdf = async () => {
    if (exportingRegionPdf) return
    setExportingRegionPdf(true)
    try {
      if (isDemo || !taskId) {
        await api.downloadRegionPdfFromData(getAllDemoDistrictReports())
      } else {
        await api.downloadRegionPdf(taskId)
      }
    } catch (err) {
      console.error(err)
      alert(err.message || 'Не удалось сформировать сводный PDF.')
    } finally {
      setExportingRegionPdf(false)
    }
  }

  const effectiveTaskId = isDemo ? demoMeta.source_job : taskId
  const apiTaskId = isDemo ? null : taskId

  const handleDepartmentReports = () => {
    if (!effectiveTaskId) return
    setDeptModalOpen(true)
  }

  useEffect(() => {
    if (!exportMenuOpen) return
    const handler = (e) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) {
        setExportMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [exportMenuOpen])

  useEffect(() => {
    if (authUser) {
      const allowed = visibleRolesForUser(authUser).map((r) => r.id)
      if (!allowed.includes(role)) {
        setRole(defaultRoleForUser(authUser))
      }
    }
  }, [authUser, role])

  useEffect(() => {
    if (!isLiveTask || !canLoadDashboard || isDemo) return undefined
    if (liveFeed.received === 0 && liveDemoPlayback.sent === 0) return undefined

    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const dashboard = await api.getDashboard(taskId || null)
        if (cancelled) return
        const merged = mergeDashboard(dashboard)
        setDistricts(merged.districts)
        setTop10(merged.top10)
        setCritical(merged.critical)
        applyDashboardMeta(merged)
      } catch {
        /* фоновое обновление live-дашборда */
      }
    }, 800)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [isLiveTask, canLoadDashboard, isDemo, taskId, liveFeed.received, liveDemoPlayback.sent])

  useEffect(() => {
    if (isDemo) {
      const merged = getDemoMergedDashboard()
      setDistricts(merged.districts)
      setTop10(merged.top10)
      setCritical(merged.critical)
      applyDashboardMeta(merged, demoMeta)
      setLoading(false)
      return
    }

    if (!canLoadDashboard) {
      setLoading(false)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const dashboard = await api.getDashboard(taskId || null)
        if (cancelled) return
        const merged = mergeDashboard(dashboard)
        setDistricts(merged.districts)
        setTop10(merged.top10)
        setCritical(merged.critical)
        applyDashboardMeta(merged)
      } catch (err) {
        if (cancelled) return
        const msg = err.message || ''
        if (err.status === 409 || msg.includes('не готова') || msg.includes('running')) {
          setError('Обработка ещё идёт. Подождите завершения на экране прогресса.')
          return
        }
        setError(msg || 'Не удалось загрузить дашборд')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [taskId, isDemo, isLiveTask, canLoadDashboard])

  if (loading && showAnalystChrome) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3" style={{ background: 'var(--bg)' }}>
        <Loader2 className="w-6 h-6 animate-spin text-red-600" />
        <span style={{ color: 'var(--text-2)' }}>Загрузка дашборда…</span>
      </div>
    )
  }

  if (error && showAnalystChrome) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-4" style={{ background: 'var(--bg)' }}>
        <p className="text-red-600 text-sm">{error}</p>
        <button onClick={onReset} className="text-sm underline" style={{ color: 'var(--muted)' }}>
          Загрузить другой файл
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen min-h-0 overflow-hidden" style={{ background: 'var(--bg)' }}>
      <header
        className="sticky top-0 z-50 shadow-sm"
        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="relative px-3 sm:px-5 py-2.5 flex items-center gap-3 min-h-[52px]">
          <div className="flex items-center gap-2.5 min-w-0 flex-shrink-0 z-10">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center flex-shrink-0 shadow-sm">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0 leading-tight">
              <span className="font-bold tracking-tight text-[15px] block" style={{ color: 'var(--text)' }}>
                ZeroProblems
              </span>
              <TaskTimingPopover taskId={taskId} isDemo={isDemo} sourceJob={isDemo ? demoMeta.source_job : null} compact />
            </div>
          </div>

          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-20 px-0.5 max-w-[calc(100%-14rem)] sm:max-w-none">
            <div
              className="inline-flex w-full sm:w-auto items-center gap-1 p-1 rounded-2xl"
              style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
            >
              {visibleRoles.map((r) => {
                const Icon = r.icon
                const active = role === r.id
                const activeStyle = { background: '#dc2626', color: '#fff', boxShadow: '0 2px 8px rgba(220,38,38,0.3)' }
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setRole(r.id)}
                    className="flex flex-1 sm:flex-initial items-center justify-center gap-1.5 px-3 sm:px-4 py-2 rounded-xl text-xs font-semibold transition-colors duration-200 min-w-[5.5rem] sm:min-w-[7.25rem]"
                    style={
                      active
                        ? activeStyle
                        : { background: 'transparent', color: 'var(--muted)' }
                    }
                  >
                    <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{r.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="ml-auto flex items-center gap-1.5 flex-shrink-0 z-10 min-h-[36px]">
            {isLiveTask && !isDemo && (
              <LiveDatasetDemoButton playback={liveDemoPlayback} />
            )}
            {showAnalystChrome && (
              <div className="relative flex-shrink-0" ref={exportMenuRef}>
                <button
                  type="button"
                  onClick={() => setExportMenuOpen((v) => !v)}
                  className="flex items-center gap-1 sm:gap-1.5 text-xs font-semibold px-2 sm:px-3 py-1.5 rounded-xl transition-colors"
                  style={{
                    background: 'var(--bg-sub)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-2)',
                  }}
                  title="Экспорт отчётов"
                >
                  <Download className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="hidden sm:inline">Экспорт</span>
                  <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 hidden sm:block transition-transform duration-200 ${exportMenuOpen ? 'rotate-180' : ''}`} />
                </button>
                {exportMenuOpen && (
                  <div
                    className="absolute right-0 top-full mt-1.5 rounded-xl shadow-xl overflow-hidden min-w-[180px] z-50"
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                  >
                    {(taskId || (isDemo && demoMeta.source_job)) && (
                      <>
                        <button
                          type="button"
                          onClick={() => { setExportMenuOpen(false); api.downloadExcel(isDemo ? demoMeta.source_job : taskId).catch((e) => alert(e.message)) }}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
                          style={{ color: 'var(--text)', background: 'transparent' }}
                        >
                          <Download className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                          Excel все МО
                        </button>
                        <button
                          type="button"
                          onClick={() => { setExportMenuOpen(false); api.downloadExcelTop10(isDemo ? demoMeta.source_job : taskId).catch((e) => alert(e.message)) }}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
                          style={{ color: 'var(--text)', background: 'transparent' }}
                        >
                          <Download className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                          Excel Топ-10
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => { setExportMenuOpen(false); handleRegionPdf() }}
                      disabled={exportingRegionPdf}
                      className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
                      style={{ color: 'var(--text)', background: 'transparent', opacity: exportingRegionPdf ? 0.6 : 1 }}
                    >
                      <FileType className="w-3.5 h-3.5 text-red-600 flex-shrink-0" />
                      {exportingRegionPdf ? 'Формирование…' : 'PDF все МО'}
                    </button>
                    {effectiveTaskId && (
                      <button
                        type="button"
                        onClick={() => { setExportMenuOpen(false); handleDepartmentReports() }}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
                        style={{ color: 'var(--text)', background: 'transparent' }}
                      >
                        <Archive className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                        Ведомства
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
            {canManageArchive && (
              fromArchive ? (
                <button
                  type="button"
                  onClick={onBackToArchive}
                  className="hidden sm:flex items-center gap-1.5 px-2.5 h-8 rounded-xl text-xs font-medium transition-colors"
                  style={{ color: 'var(--text)', border: '1px solid var(--border)', background: 'var(--bg-card)' }}
                  title="К списку базы"
                >
                  <Database className="w-3.5 h-3.5 text-red-600" />
                  База
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onOpenArchive}
                  className="hidden sm:flex items-center gap-1.5 px-2.5 h-8 rounded-xl text-xs font-medium transition-colors"
                  style={{ color: 'var(--text)', border: '1px solid var(--border)', background: 'var(--bg-card)' }}
                  title="Работа с базой"
                >
                  <Database className="w-3.5 h-3.5 text-red-600" />
                  База
                </button>
              )
            )}
            <UserMenu user={authUser} onLogout={onLogout} onOpenAdmin={onOpenAdmin} />
            <ThemeToggle dark={dark} onToggle={onToggleTheme} />
          </div>
        </div>

        {role === 'analyst' && liveFeed.received > 0 && (
          <div className="px-3 sm:px-5 py-1.5 flex items-center gap-2" style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-sub)' }}>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: '#dcfce7', color: '#16a34a', border: '1px solid #bbf7d0' }}>
              +{liveFeed.received} live
            </span>
          </div>
        )}
      </header>

      <DepartmentReportsModal
        taskId={effectiveTaskId}
        open={deptModalOpen}
        onClose={() => setDeptModalOpen(false)}
      />

      <LiveDemoPanel enabled={!isDemo && isLiveTask} feed={liveFeed} />

      <div
        className="flex flex-col flex-1 min-h-0"
        style={{ display: role === 'operator' ? 'flex' : 'none' }}
        aria-hidden={role !== 'operator'}
      >
        <OperatorScreen
          dark={dark}
          initialDistrict={operatorDistrict}
          taskId={apiTaskId}
          loadEnabled={role === 'operator' || isLiveTask}
          sharedLiveFeed={isLiveTask ? liveFeed : null}
          municipalityOptions={districts.map((d) => d.name)}
          onShowOnMap={(item) => {
            setFocusIncident(item)
            setRole('analyst')
            setAnalystMapTab('incidents')
          }}
        />
      </div>
      {role === 'forecast' && (
        <ForecastScreen dark={dark} />
      )}

      {showAnalystChrome && kpi && (
        <div className="flex-shrink-0 px-3 sm:px-5 py-2 grid grid-cols-2 lg:grid-cols-5 gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
          {/* Карточка периода */}
          <div
            className="relative flex items-center gap-3 px-3 py-2.5 rounded-xl overflow-hidden"
            style={{
              background: 'color-mix(in srgb, #6366f1 5%, var(--bg-card))',
              border: '1px solid color-mix(in srgb, #6366f1 18%, var(--border))',
            }}
          >
            <div style={{
              width: '34px', height: '34px', borderRadius: '10px', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'color-mix(in srgb, #6366f1 22%, var(--bg-card))',
              border: '1px solid color-mix(in srgb, #6366f1 40%, var(--border))',
              boxShadow: '0 2px 8px color-mix(in srgb, #6366f1 20%, transparent)',
            }}>
              <CalendarRange style={{ width: '15px', height: '15px', color: '#6366f1' }} />
            </div>
            <div className="min-w-0">
              <div className="text-base font-black leading-none truncate" style={{ color: '#6366f1' }}>
                {periodLabel || '—'}
              </div>
              <div className="inline-flex items-center gap-1 mt-1">
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDemo ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse'}`} />
                <span className="text-[11px] font-medium" style={{ color: 'var(--muted)' }}>
                  {isDemo ? `Демо · ${demoMeta.municipalities} МО` : isLiveTask ? 'Live' : 'Актуально'}
                </span>
              </div>
            </div>
          </div>

          {[
            { label: 'Обращений',      value: kpi.total.toLocaleString('ru-RU'),                       color: '#475569', accent: '#64748b', Icon: Users2        },
            { label: 'Проблемных',     value: `${((kpi.problems / kpi.total) * 100).toFixed(1)}%`,     color: '#ea580c', accent: '#ea580c', Icon: Percent       },
            { label: 'Критических МО', value: critical.length,                                          color: '#dc2626', accent: '#dc2626', Icon: Flame         },
            { label: 'Охвачено МО',    value: districts.length,                                         color: '#2563eb', accent: '#2563eb', Icon: LocateFixed   },
          ].map((item) => (
            <div
              key={item.label}
              className="relative flex items-center gap-3 px-3 py-2.5 rounded-xl overflow-hidden"
              style={{
                background: `color-mix(in srgb, ${item.accent} 5%, var(--bg-card))`,
                border: `1px solid color-mix(in srgb, ${item.accent} 18%, var(--border))`,
              }}
            >
              <div style={{
                width: '34px', height: '34px', borderRadius: '10px', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: `color-mix(in srgb, ${item.accent} 22%, var(--bg-card))`,
                border: `1px solid color-mix(in srgb, ${item.accent} 40%, var(--border))`,
                boxShadow: `0 2px 8px color-mix(in srgb, ${item.accent} 20%, transparent)`,
              }}>
                <item.Icon style={{ width: '15px', height: '15px', color: item.accent, filter: 'saturate(1.4)' }} />
              </div>
              <div className="min-w-0">
                <div className="text-lg font-black tabular-nums leading-none" style={{ color: item.color }}>{item.value}</div>
                <div className="text-[11px] font-medium mt-0.5 truncate" style={{ color: 'var(--muted)' }}>{item.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAnalystChrome && (
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {analystMapTab === 'incidents' ? (
          <AnalystIncidentsMap
            dark={dark}
            taskId={apiTaskId}
            focusIncident={focusIncident}
            onFocusConsumed={() => setFocusIncident(null)}
            showTiles={showTiles}
            onToggleTiles={() => setShowTiles((t) => !t)}
            onSwitchToDistricts={() => setAnalystMapTab('districts')}
          />
        ) : (
      <div className="flex-1 flex flex-col xl:flex-row min-h-0 overflow-y-auto xl:overflow-hidden">
        <div className="w-full xl:w-1/2 flex flex-col flex-shrink-0 p-3 sm:p-4 xl:min-h-0 h-[min(48vh,440px)] xl:h-auto xl:max-h-full xl:flex-1">
          <div className="rounded-2xl overflow-hidden flex flex-col shadow-sm flex-1 min-h-[240px]" style={{ ...card }}>
            <div
              className="px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 flex-shrink-0 flex-wrap"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <TrendingUp className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Карта Омской области</span>
              <span className="text-xs hidden sm:inline" style={{ color: 'var(--muted)' }}>
                {isLiveTask
                  ? (districts.length
                    ? `рейтинг по ${districts.length} МО с обращениями · маркеры — адреса`
                    : 'live-обращения с адресом')
                  : 'кликните на район'}
              </span>
              <div className="ml-auto flex items-center gap-1 flex-shrink-0">
              <button
                type="button"
                onClick={() => setAnalystMapTab('incidents')}
                className="analyst-map-feed-btn"
                title="Обращения на карте"
                aria-label="Обращения на карте"
                style={{ color: '#dc2626' }}
              >
                <MapPin className="w-5 h-5" />
              </button>
              <button
                type="button"
                onClick={() => setShowTiles((t) => !t)}
                className="analyst-map-feed-btn"
                style={{ color: showTiles ? 'var(--muted)' : '#dc2626' }}
                title={showTiles ? 'Скрыть подложку' : 'Показать подложку'}
                aria-label={showTiles ? 'Скрыть подложку' : 'Показать подложку'}
              >
                {showTiles ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
              </button>
              </div>
            </div>
            <div
              className="px-3 sm:px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              {[['#991b1b', '75+'], ['#ef4444', '60–74'], ['#f97316', '50–59'], ['#84cc16', '35–49'], ['#22c55e', '<35']].map(
                ([c, l]) => (
                  <div key={l} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>{l}</span>
                  </div>
                ),
              )}
            </div>
            <div className="flex-1 min-h-0">
              <OmskMap
                districts={districts}
                livePins={liveMapPins}
                onDistrictClick={onDistrictClick}
                showTiles={showTiles}
                dark={dark}
              />
            </div>
          </div>
        </div>

        <div className="w-full xl:w-1/2 xl:flex-shrink-0 flex flex-col gap-3 sm:gap-4 p-3 sm:p-4 min-h-0 overflow-visible xl:overflow-y-auto xl:overscroll-contain pb-6 xl:pb-4">
          <div className="flex-shrink-0">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
                style={{ background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' }}>
                <AlertTriangle className="w-3.5 h-3.5" />
                Критические районы
              </span>
              <span className="text-xs hidden sm:inline" style={{ color: 'var(--muted)' }}>требуют первоочередного внимания</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-3 sm:gap-4">
              {critical.map((d, i) => (
                <DistrictCard key={d.id} district={d} rank={i + 1} onClick={() => onDistrictClick(d)} />
              ))}
              {isLiveTask && critical.length === 0 && (
                <p className="text-xs col-span-full py-4 px-2" style={{ color: 'var(--muted)' }}>
                  Критические районы появятся при накоплении обращений из формы.
                </p>
              )}
            </div>
          </div>

          <div className="flex-shrink-0 flex flex-col">
            <div
              className="px-1 py-2.5 flex items-center gap-2 flex-shrink-0 flex-wrap"
            >
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
                style={{ background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>
                <AlertTriangle className="w-3.5 h-3.5" />
                Топ-10 проблемных районов
              </span>
              <span className="text-xs hidden lg:inline" style={{ color: 'var(--muted)' }}>выше индекс — больше проблем</span>
            </div>
            <div className="overflow-visible">
              <Top10Table districts={top10} onDistrictClick={onDistrictClick} />
            </div>
          </div>
        </div>
      </div>
        )}
      </div>
      )}
    </div>
  )
}
