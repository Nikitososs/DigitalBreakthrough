import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Archive,
  Building2,
  CheckCircle2,
  FileSpreadsheet,
  FileType,
  Loader2,
  Mail,
  MapPin,
  X,
} from 'lucide-react'
import { api } from '../api/client'

const PHASE_LABELS = {
  pdf: 'PDF',
  excel: 'Excel',
  archive: 'Архив',
  done: 'Готово',
  start: 'Старт',
}

function shortAgency(name) {
  if (!name) return ''
  const parts = name.split(' ')
  if (parts.length <= 4) return name
  return `${parts[0]} ${parts[1]}…`
}

function severityCount(agency, level) {
  const raw = agency?.counts?.[String(level)] ?? agency?.counts?.[level]
  const n = Number(raw)
  return Number.isFinite(n) ? n : 0
}

const PRIORITY_STYLES = {
  КРИТИЧЕСКИЙ: { bg: '#fef2f2', color: '#dc2626', border: '#fecaca' },
  ВЫСОКИЙ:     { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa' },
  СРЕДНИЙ:     { bg: '#fefce8', color: '#ca8a04', border: '#fef08a' },
  НИЗКИЙ:      { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0' },
}

function sortAgenciesBySeverity(agencies) {
  return [...(agencies ?? [])].sort((a, b) => {
    const a4 = severityCount(a, 4)
    const b4 = severityCount(b, 4)
    if (b4 !== a4) return b4 - a4
    const a3 = severityCount(a, 3)
    const b3 = severityCount(b, 3)
    if (b3 !== a3) return b3 - a3
    return String(a.name).localeCompare(String(b.name), 'ru')
  })
}

export default function DepartmentReportsModal({ taskId, open, onClose }) {
  const [preview, setPreview] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const downloadedRef = useRef(false)
  const pollRef = useRef(null)
  const genTaskRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('modal-open')
    return () => document.body.classList.remove('modal-open')
  }, [open])

  useEffect(() => {
    if (!open || !taskId) return undefined

    let cancelled = false
    setPreview(null)
    setStatus(null)
    setError('')
    downloadedRef.current = false
    genTaskRef.current = null

    const start = async () => {
      try {
        const [previewData, gen] = await Promise.all([
          api.getDepartmentReportsPreview(taskId),
          api.startDepartmentReportsGenerate(taskId),
        ])
        if (cancelled) return
        setPreview(previewData)
        setStatus(gen)
        genTaskRef.current = gen.task_id
        pollRef.current = setInterval(async () => {
          try {
            const next = await api.getDepartmentReportsStatus(gen.task_id)
            if (cancelled) return
            setStatus(next)
            if (next.status === 'completed') {
              clearInterval(pollRef.current)
              pollRef.current = null
              if (!downloadedRef.current) {
                downloadedRef.current = true
                await api.downloadDepartmentReportsByGenId(gen.task_id)
              }
            }
            if (next.status === 'failed') {
              clearInterval(pollRef.current)
              pollRef.current = null
              setError(next.message || 'Не удалось сформировать архив')
            }
          } catch (err) {
            if (!cancelled) {
              clearInterval(pollRef.current)
              pollRef.current = null
              setError(err.message || 'Ошибка при генерации')
            }
          }
        }, 600)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Не удалось запустить генерацию')
      }
    }

    start()
    return () => {
      cancelled = true
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [open, taskId])

  if (!open) return null

  const progress = Math.min(100, Math.round(status?.progress ?? 0))
  const isDone = status?.status === 'completed'
  const isRunning = status?.status === 'processing'
  const municipalities = preview?.municipalities ?? status?.preview?.municipalities ?? []
  const activeMuni = status?.current_municipality
  const activeAgency = status?.current_agency

  const kpiItems = [
    { label: 'Муниципалитетов', value: preview?.municipalities_count ?? '—', icon: MapPin,        iconColor: '#dc2626', iconBg: '#fef2f2' },
    { label: 'Ведомств',        value: preview?.agencies_count ?? '—',       icon: Building2,     iconColor: '#ea580c', iconBg: '#fff7ed' },
    { label: 'Отчётов',         value: preview?.reports_count ?? '—',        icon: FileSpreadsheet, iconColor: '#6366f1', iconBg: '#eef2ff' },
  ]

  return createPortal(
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center p-3 sm:p-6"
      style={{ background: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col relative"
        style={{
          background: 'var(--bg-card)',
          border: '1px solid color-mix(in srgb, #dc2626 15%, var(--border))',
          borderRadius: '28px',
          boxShadow: '0 32px 80px -20px rgba(0,0,0,0.18), 0 0 0 1px color-mix(in srgb, #dc2626 8%, var(--border))',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Фоновые пятна */}
        <div aria-hidden style={{ position: 'absolute', top: '-60px', right: '-40px', width: '280px', height: '280px', borderRadius: '50%', background: 'radial-gradient(circle, #dc26261a 0%, transparent 65%)', pointerEvents: 'none' }} />
        <div aria-hidden style={{ position: 'absolute', bottom: '-40px', left: '-40px', width: '220px', height: '220px', borderRadius: '50%', background: 'radial-gradient(circle, #dc262612 0%, transparent 65%)', pointerEvents: 'none' }} />

        {/* Шапка */}
        <div className="px-5 pt-5 pb-4 flex items-start gap-3 flex-shrink-0 relative">
          <div style={{
            width: '48px', height: '48px', borderRadius: '16px', flexShrink: 0,
            background: 'linear-gradient(145deg, #ef4444 0%, #b91c1c 100%)',
            boxShadow: '0 8px 24px -8px #dc2626aa',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Archive className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1 min-w-0 pt-0.5">
            <h2 className="text-lg font-bold tracking-tight" style={{ color: 'var(--text)' }}>
              Отчёты в ведомства
            </h2>
            <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--muted)' }}>
              PDF со сводкой, темами и рекомендациями + Excel (3 листа) по каждому МО и ведомству
            </p>
            {(preview?.period_start || preview?.period_end) && (
              <span className="inline-flex items-center gap-1 mt-1.5 text-[11px] px-2 py-0.5 rounded-full font-medium"
                style={{ background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' }}>
                {preview.period_start ?? '…'} — {preview.period_end ?? '…'}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:opacity-80 flex-shrink-0"
            style={{ color: 'var(--muted)', border: '1px solid var(--border)', background: 'var(--bg-sub)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 pb-5 overflow-y-auto flex-1 space-y-4 relative">
          {/* Ошибка */}
          {error && (
            <div className="rounded-2xl px-4 py-3 text-sm" style={{ background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
              {error}
              <p className="text-xs mt-1.5 opacity-70">Убедитесь, что API перезапущен после обновления. Для demo загрузите свой Excel-файл.</p>
            </div>
          )}

          {/* KPI */}
          <div className="grid grid-cols-3 gap-3">
            {kpiItems.map(({ label, value, icon: Icon, iconColor, iconBg }) => (
              <div key={label} className="rounded-2xl px-3 py-3 text-center" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '10px', background: iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                  <Icon className="w-4 h-4" style={{ color: iconColor }} />
                </div>
                <div className="text-xl font-black tabular-nums" style={{ color: 'var(--text)' }}>{value}</div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Прогресс */}
          <div className="rounded-2xl px-4 py-3.5" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-semibold" style={{ color: 'var(--text)' }}>
                {isDone ? 'Архив сформирован' : isRunning ? 'Генерация…' : 'Подготовка…'}
              </span>
              <span className="text-sm font-black tabular-nums" style={{ color: isDone ? '#16a34a' : '#dc2626' }}>{progress}%</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
              <div
                className={`h-full rounded-full transition-all duration-300 ${isRunning ? 'dept-progress-stripe' : ''}`}
                style={{
                  width: `${progress}%`,
                  background: isDone
                    ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                    : 'linear-gradient(90deg, #ef4444, #dc2626)',
                }}
              />
            </div>
            {status?.message && (
              <p className="text-[11px] mt-2 flex items-center gap-1.5" style={{ color: 'var(--muted)' }}>
                {isRunning && <Loader2 className="w-3 h-3 animate-spin text-red-500" />}
                {isDone && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
                {status.message}
              </p>
            )}
            {status?.phase && isRunning && (
              <div className="flex gap-1.5 mt-2.5">
                {['pdf', 'excel', 'archive'].map((phase) => {
                  const active = status.phase === phase
                  return (
                    <span key={phase} className="text-[10px] px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wide" style={{
                      background: active ? '#fef2f2' : 'var(--bg-card)',
                      color: active ? '#dc2626' : 'var(--muted)',
                      border: `1px solid ${active ? '#fecaca' : 'var(--border)'}`,
                    }}>
                      {PHASE_LABELS[phase]}
                    </span>
                  )
                })}
              </div>
            )}
          </div>

          {/* Структура архива */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--muted)' }}>Структура архива</span>
              <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            </div>

            <div className="space-y-2 max-h-56 overflow-y-auto pr-0.5" style={{ scrollbarWidth: 'thin' }}>
              {municipalities.length === 0 ? (
                <div className="py-8 text-center">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-red-500" />
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>Загрузка структуры…</p>
                </div>
              ) : (
                municipalities.map((muni) => {
                  const muniActive = activeMuni === muni.name
                  return (
                    <div key={muni.name} className="rounded-2xl overflow-hidden" style={{
                      border: `1px solid ${muniActive ? '#fecaca' : 'var(--border)'}`,
                      background: muniActive ? 'color-mix(in srgb, #dc2626 4%, var(--bg))' : 'var(--bg)',
                      boxShadow: muniActive ? '0 4px 16px #dc262618' : 'none',
                    }}>
                      {/* Заголовок района */}
                      <div className="px-3.5 py-2.5 flex items-center gap-2">
                        <MapPin className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#dc2626' }} />
                        <span className="flex-1 text-xs font-bold truncate" style={{ color: 'var(--text)' }}>{muni.name}</span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0"
                          style={{ background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }}>
                          {muni.agencies?.length ?? 0} вед.
                        </span>
                      </div>

                      {/* Контакт администрации */}
                      {(muni.admin_contact_email || muni.admin_contact_phone || muni.administration) && (
                        <div className="px-3.5 pb-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px]" style={{ color: 'var(--muted)' }}>
                          {muni.administration && (
                            <span className="truncate max-w-full" title={muni.administration}>{muni.administration}</span>
                          )}
                          {muni.admin_contact_email && (
                            <a href={`mailto:${muni.admin_contact_email}?subject=${encodeURIComponent(`Отчёт ZeroProblems: ${muni.name}`)}`}
                              className="inline-flex items-center gap-1 hover:underline font-medium"
                              style={{ color: '#dc2626' }} onClick={(e) => e.stopPropagation()}>
                              <Mail className="w-3 h-3" />{muni.admin_contact_email}
                            </a>
                          )}
                          {muni.admin_contact_phone && <span>{muni.admin_contact_phone}</span>}
                        </div>
                      )}

                      {/* Ведомства */}
                      <div className="px-2 pb-2 space-y-1">
                        {sortAgenciesBySeverity(muni.agencies).map((agency) => {
                          const active = muniActive && activeAgency === agency.name
                          const sev4 = severityCount(agency, 4)
                          const sev3 = severityCount(agency, 3)
                          const pri = PRIORITY_STYLES[agency.priority] ?? null
                          return (
                            <div key={`${muni.name}-${agency.name}`} className="rounded-xl overflow-hidden" style={{
                              background: active ? 'color-mix(in srgb, #dc2626 6%, var(--bg-card))' : 'var(--bg-card)',
                              border: `1px solid ${active ? '#fecaca' : 'var(--border)'}`,
                            }}>
                              <div className="flex items-center gap-2 px-3 py-2">
                                {active && isRunning
                                  ? <Loader2 className="w-3 h-3 animate-spin flex-shrink-0 text-red-500" />
                                  : <Building2 className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                                }
                                <span className="flex-1 truncate text-[11px] font-semibold" style={{ color: 'var(--text-2)' }} title={agency.name}>
                                  {shortAgency(agency.name)}
                                </span>
                                {agency.priority && pri && (
                                  <span className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wide flex-shrink-0"
                                    style={{ background: pri.bg, color: pri.color, border: `1px solid ${pri.border}` }}>
                                    {agency.priority.slice(0, 4)}
                                  </span>
                                )}
                                <div className="flex items-center gap-1 flex-shrink-0" style={{ color: 'var(--muted)' }}>
                                  <FileType className="w-3.5 h-3.5" />
                                  <FileSpreadsheet className="w-3.5 h-3.5" />
                                </div>
                              </div>
                              {(agency.top_topic || sev4 > 0 || sev3 > 0 || agency.contact_email) && (
                                <div className="px-3 pb-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px]" style={{ color: 'var(--muted)' }}>
                                  {agency.top_topic && (
                                    <span className="truncate max-w-[12rem]" title={agency.top_topic}>{agency.top_topic}</span>
                                  )}
                                  {sev4 > 0 && <span className="font-semibold" style={{ color: '#dc2626' }}>{sev4} крит.</span>}
                                  {sev3 > 0 && <span className="font-semibold" style={{ color: '#ea580c' }}>{sev3} тяж.</span>}
                                  {agency.contact_email && (
                                    <a href={`mailto:${agency.contact_email}?subject=${encodeURIComponent(`Отчёт ZeroProblems: ${muni.name}`)}`}
                                      className="inline-flex items-center gap-1 hover:underline font-medium"
                                      style={{ color: '#dc2626' }} onClick={(e) => e.stopPropagation()}>
                                      <Mail className="w-3 h-3" />email
                                    </a>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>

        {/* Футер */}
        <div className="px-5 py-4 flex items-center gap-2.5 flex-shrink-0 relative" style={{ borderTop: '1px solid var(--border)' }}>
          {isDone && genTaskRef.current && (
            <button
              type="button"
              onClick={() => api.downloadDepartmentReportsByGenId(genTaskRef.current)}
              className="flex-1 flex items-center justify-center gap-2 text-sm font-bold text-white py-2.5 rounded-xl transition-opacity hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)', boxShadow: '0 8px 24px -8px #dc2626aa' }}
            >
              Скачать снова
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="flex-1 flex items-center justify-center gap-2 text-sm font-semibold py-2.5 rounded-xl transition-opacity hover:opacity-80"
            style={{ border: '1px solid var(--border)', color: 'var(--text-2)', background: 'var(--bg-sub)' }}
          >
            {isDone ? 'Закрыть' : 'Свернуть'}
          </button>
        </div>

        <style>{`
          @keyframes deptStripe {
            0% { background-position: 0 0; }
            100% { background-position: 28px 0; }
          }
          .dept-progress-stripe {
            background-image: linear-gradient(
              135deg,
              #ef4444 25%, #dc2626 25%,
              #dc2626 50%, #ef4444 50%,
              #ef4444 75%, #dc2626 75%
            ) !important;
            background-size: 28px 28px !important;
            animation: deptStripe 0.6s linear infinite;
          }
        `}</style>
      </div>
    </div>,
    document.body,
  )
}
