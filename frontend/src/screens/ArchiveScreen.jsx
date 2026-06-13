import { useCallback, useEffect, useMemo, useState } from 'react'
import { Database, FileSpreadsheet, Loader2, Trash2, Upload, ArrowLeft, Import, Radio, Copy } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import UserMenu from '../components/UserMenu'
import { api } from '../api/client'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function JobCard({
  job,
  variant,
  onOpen,
  onImport,
  onDelete,
  busy,
  selectable,
  selected,
  onToggleSelect,
  readOnly = false,
}) {
  const isImportable = variant === 'importable'
  const isLive = variant === 'live'
  const isDuplicate = variant === 'duplicate' || job.is_duplicate
  const isDupCandidate = job.is_duplicate_candidate && !isDuplicate
  const openTaskId = isDuplicate && job.duplicate_of_task_id ? job.duplicate_of_task_id : job.task_id
  return (
    <div
      className="rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3"
      style={{
        background: isDuplicate ? '#fff7ed' : 'var(--bg-card)',
        border: isDuplicate
          ? '1px solid rgba(234,88,12,0.45)'
          : isDupCandidate
            ? '1px dashed rgba(234,88,12,0.35)'
            : '1px solid var(--border)',
      }}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        {selectable && (
          <label className="flex items-center pt-2 flex-shrink-0 cursor-pointer">
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(job.task_id)}
              className="w-4 h-4 rounded accent-red-600"
            />
          </label>
        )}
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: isImportable
              ? (isDupCandidate ? 'rgba(234,88,12,0.12)' : 'var(--bg-sub)')
              : isLive
                ? 'rgba(59,130,246,0.12)'
                : isDuplicate
                  ? 'rgba(234,88,12,0.15)'
                  : 'rgba(220,38,38,0.1)',
          }}
        >
          {isImportable
            ? (isDupCandidate
              ? <Copy className="w-5 h-5 text-orange-600" />
              : <FileSpreadsheet className="w-5 h-5" style={{ color: 'var(--muted)' }} />)
            : isLive
              ? <Radio className="w-5 h-5 text-blue-600" />
              : isDuplicate
                ? <Copy className="w-5 h-5 text-orange-600" />
                : <Database className="w-5 h-5 text-red-600" />}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-sm truncate" style={{ color: 'var(--text)' }}>
              {job.filename || `Задача ${job.task_id}`}
            </p>
            {isDuplicate && (
              <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700">
                Дубликат
              </span>
            )}
            {isDupCandidate && (
              <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-orange-50 text-orange-600 border border-orange-200">
                Уже в базе
              </span>
            )}
          </div>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            ID {job.task_id}
            {isDuplicate && job.duplicate_of_task_id && ` · оригинал ${job.duplicate_of_task_id}`}
            {!isDuplicate && job.incident_count > 0 && ` · ${job.incident_count.toLocaleString('ru-RU')} обращений`}
            {isDuplicate && job.rows_total > 0 && ` · ${job.rows_total.toLocaleString('ru-RU')} строк (не импортировано)`}
            {job.rows_total > 0 && job.incident_count === 0 && !isDuplicate && ` · ${job.rows_total.toLocaleString('ru-RU')} строк`}
          </p>
          <p className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>
            {isLive
              ? `Live-поток · ${formatDate(job.stored_at || job.created_at)}`
              : isImportable
                ? `В кэше · ${formatDate(job.created_at)}`
                : `В базе · ${formatDate(job.stored_at || job.created_at)}`}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {isImportable ? (
          readOnly ? null : (
          <>
            {!isDupCandidate && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onImport(job.task_id)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-white bg-red-600 hover:opacity-90 disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Import className="w-3.5 h-3.5" />}
                В базу
              </button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => onDelete(job.task_id)}
              className="p-2 rounded-xl hover:bg-red-50 text-red-600 disabled:opacity-50"
              title="Удалить из кэша"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </>
          )
        ) : isLive ? (
          <button
            type="button"
            onClick={() => onOpen(openTaskId)}
            className="px-3 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:opacity-90"
          >
            Открыть все
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onOpen(openTaskId)}
              className="px-3 py-2 rounded-xl text-xs font-semibold text-white bg-red-600 hover:opacity-90"
            >
              {isDuplicate ? 'Открыть оригинал' : 'Открыть'}
            </button>
            {!readOnly && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onDelete(job.task_id)}
                className="p-2 rounded-xl hover:bg-red-50 text-red-600 disabled:opacity-50"
                title="Удалить из базы"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function ArchiveScreen({
  onOpenJob,
  onBack,
  onNewUpload,
  dark,
  onToggleTheme,
  authUser,
  onLogout,
  onOpenAdmin,
}) {
  const readOnly = authUser?.role !== 'admin'
  const [jobs, setJobs] = useState([])
  const [duplicates, setDuplicates] = useState([])
  const [liveJob, setLiveJob] = useState(null)
  const [importable, setImportable] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [selectedCache, setSelectedCache] = useState(() => new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    api.getArchiveJobs()
      .then((data) => {
        setJobs(data.jobs || [])
        setDuplicates(data.duplicates || [])
        setLiveJob(data.live_job || null)
        setImportable(data.importable || [])
        setSelectedCache((prev) => {
          const ids = new Set((data.importable || []).map((j) => j.task_id))
          return new Set([...prev].filter((id) => ids.has(id)))
        })
      })
      .catch((err) => setError(err.message || 'Не удалось загрузить базу'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const importableIds = useMemo(
    () => importable.map((j) => j.task_id),
    [importable],
  )

  const allCacheSelected = importableIds.length > 0
    && importableIds.every((id) => selectedCache.has(id))

  const toggleCacheSelect = (taskId) => {
    setSelectedCache((prev) => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  const toggleSelectAllCache = () => {
    if (allCacheSelected) {
      setSelectedCache(new Set())
    } else {
      setSelectedCache(new Set(importableIds))
    }
  }

  const handleImport = async (taskId) => {
    setBusyId(taskId)
    try {
      await api.importArchiveJob(taskId)
      setSelectedCache((prev) => {
        const next = new Set(prev)
        next.delete(taskId)
        return next
      })
      load()
    } catch (err) {
      setError(err.message || 'Ошибка импорта')
    } finally {
      setBusyId(null)
    }
  }

  const handleDeleteFromDb = async (taskId) => {
    if (!window.confirm('Удалить задачу из базы? Файлы в cache не удаляются.')) return
    setBusyId(taskId)
    try {
      await api.deleteArchiveJob(taskId)
      load()
    } catch (err) {
      setError(err.message || 'Ошибка удаления')
    } finally {
      setBusyId(null)
    }
  }

  const handleDeleteFromCache = async (taskId) => {
    if (!window.confirm('Удалить задачу из кэша? Файлы будут удалены безвозвратно.')) return
    setBusyId(taskId)
    try {
      await api.deleteCachedJobs([taskId])
      setSelectedCache((prev) => {
        const next = new Set(prev)
        next.delete(taskId)
        return next
      })
      load()
    } catch (err) {
      setError(err.message || 'Ошибка удаления из кэша')
    } finally {
      setBusyId(null)
    }
  }

  const handleDeleteSelectedCache = async () => {
    const ids = [...selectedCache]
    if (ids.length === 0) return
    if (!window.confirm(`Удалить ${ids.length} задач(и) из кэша? Файлы будут удалены безвозвратно.`)) return
    setBulkDeleting(true)
    setError('')
    try {
      await api.deleteCachedJobs(ids)
      setSelectedCache(new Set())
      load()
    } catch (err) {
      setError(err.message || 'Ошибка удаления из кэша')
    } finally {
      setBulkDeleting(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="px-4 py-3 flex items-center gap-3 border-b"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}
      >
        <button
          type="button"
          onClick={onBack}
          className="p-2 rounded-xl hover:opacity-80"
          style={{ color: 'var(--muted)' }}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Database className="w-5 h-5 text-red-600 flex-shrink-0" />
          <div>
            <h1 className="text-sm font-bold" style={{ color: 'var(--text)' }}>База обращений</h1>
            <p className="text-[11px]" style={{ color: 'var(--muted)' }}>Все обработанные выгрузки</p>
          </div>
        </div>
        <UserMenu user={authUser} onLogout={onLogout} onOpenAdmin={onOpenAdmin} />
        {!readOnly && (
          <button
            type="button"
            onClick={onNewUpload}
            className="hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold"
            style={{ background: 'var(--bg-sub)', color: 'var(--text)' }}
          >
            <Upload className="w-3.5 h-3.5" />
            Новый анализ
          </button>
        )}
        <ThemeToggle dark={dark} onToggle={onToggleTheme} />
      </header>

      <main className="flex-1 p-4 max-w-3xl mx-auto w-full space-y-6">
        {error && (
          <div className="text-sm text-red-600 px-3 py-2 rounded-xl bg-red-50 border border-red-100">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20 gap-2 text-sm" style={{ color: 'var(--muted)' }}>
            <Loader2 className="w-5 h-5 animate-spin text-red-500" />
            Загрузка…
          </div>
        ) : (
          <>
            {liveJob && (
              <section>
                <h2 className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--muted)' }}>
                  Обращения из формы
                </h2>
                <p className="text-[11px] mb-3" style={{ color: 'var(--muted)' }}>
                  Все поданные через /submit гражданские обращения (live-поток)
                </p>
                <JobCard
                  job={liveJob}
                  variant="live"
                  onOpen={onOpenJob}
                  onImport={handleImport}
                  onDelete={handleDeleteFromDb}
                  busy={false}
                  readOnly={readOnly}
                />
              </section>
            )}

            <section>
              <h2 className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
                В базе ({jobs.length})
              </h2>
              {jobs.length === 0 ? (
                <p className="text-sm py-8 text-center rounded-2xl" style={{ color: 'var(--muted)', background: 'var(--bg-sub)' }}>
                  Пока пусто. После анализа Excel данные сохраняются автоматически, или импортируйте из кэша ниже.
                </p>
              ) : (
                <div className="space-y-2">
                  {jobs.map((job) => (
                    <JobCard
                      key={job.task_id}
                      job={job}
                      variant="stored"
                      onOpen={onOpenJob}
                      onImport={handleImport}
                      onDelete={handleDeleteFromDb}
                      busy={busyId === job.task_id}
                      readOnly={readOnly}
                    />
                  ))}
                </div>
              )}
            </section>

            {duplicates.length > 0 && (
              <section>
                <h2 className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--muted)' }}>
                  Дубликаты ({duplicates.length})
                </h2>
                <p className="text-[11px] mb-3" style={{ color: 'var(--muted)' }}>
                  Повторная загрузка того же файла — обращения в базу не попали
                </p>
                <div className="space-y-2">
                  {duplicates.map((job) => (
                    <JobCard
                      key={job.task_id}
                      job={job}
                      variant="duplicate"
                      onOpen={onOpenJob}
                      onImport={handleImport}
                      onDelete={handleDeleteFromDb}
                      busy={busyId === job.task_id}
                      readOnly={readOnly}
                    />
                  ))}
                </div>
              </section>
            )}

            {importable.length > 0 && (
              <section>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
                  <div>
                    <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Можно импортировать из кэша ({importable.length})
                    </h2>
                    <p className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>
                      Завершённые задачи, ещё не перенесённые в базу
                    </p>
                  </div>
                  {!readOnly && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--muted)' }}>
                        <input
                          type="checkbox"
                          checked={allCacheSelected}
                          onChange={toggleSelectAllCache}
                          className="w-4 h-4 rounded accent-red-600"
                        />
                        Выбрать все
                      </label>
                      {selectedCache.size > 0 && (
                        <button
                          type="button"
                          disabled={bulkDeleting}
                          onClick={handleDeleteSelectedCache}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-red-600 border border-red-200 hover:bg-red-50 disabled:opacity-50"
                        >
                          {bulkDeleting
                            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            : <Trash2 className="w-3.5 h-3.5" />}
                          Удалить выбранные ({selectedCache.size})
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  {importable.map((job) => (
                    <JobCard
                      key={job.task_id}
                      job={job}
                      variant="importable"
                      onOpen={onOpenJob}
                      onImport={handleImport}
                      onDelete={handleDeleteFromCache}
                      busy={busyId === job.task_id || bulkDeleting}
                      selectable={!readOnly}
                      selected={selectedCache.has(job.task_id)}
                      onToggleSelect={toggleCacheSelect}
                      readOnly={readOnly}
                    />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
