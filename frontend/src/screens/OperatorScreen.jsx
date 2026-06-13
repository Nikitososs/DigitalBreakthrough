import { useState, useMemo, useEffect, useRef } from 'react'
import {
  CheckSquare,
  Square,
  Send,
  Filter,
  X,
  CheckCircle2,
  Loader2,
  Copy,
  Mail,
  AlertCircle,
  Search,
  RotateCcw,
  MapPin,
} from 'lucide-react'
import { api } from '../api/client'
import LiveDemoPanel from '../components/LiveDemoPanel'
import IncidentPackageList from '../components/IncidentPackageList'
import SearchableSelect from '../components/SearchableSelect'
import { LIVE_TASK_ID } from '../constants'
import { useLiveFeed } from '../hooks/useLiveFeed'
import { useIncidentFacets } from '../hooks/useIncidentFacets'
import GeocodeWarmupButton from '../components/GeocodeWarmupButton'
import IncidentDateFilter from '../components/IncidentDateFilter'
import { useBackgroundGeocode } from '../hooks/useBackgroundGeocode'
import { useIncidentDateFilter } from '../hooks/useIncidentDateFilter'
import { useTaskIncidentPackagesInfinite } from '../hooks/useTaskIncidents'
import { incidentInDateRange } from '../utils/incidentDateFilter'
import {
  citizenRowId,
  isCitizenRowId,
  liveEventToIncident,
  normalizeIncident,
  SEVERITY_FILTER_OPTIONS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
  PROBLEM_SEVERITY_MIN,
} from '../utils/incidentModel'
import { isOpenProblem } from '../utils/incidentPackages'

export default function OperatorScreen({
  dark,
  initialDistrict,
  taskId = null,
  municipalityOptions = [],
  onShowOnMap = null,
  loadEnabled = true,
  sharedLiveFeed = null,
}) {
  const [selectedMap, setSelectedMap] = useState(() => new Map())
  const [filterSev, setFilterSev] = useState(null)
  const [filterDistrict, setFilterDistrict] = useState(initialDistrict || '')
  const [filterGroup, setFilterGroup] = useState('')
  const [filterTopic, setFilterTopic] = useState('')
  const [filterAgency, setFilterAgency] = useState('')
  const [onlyWithAddress, setOnlyWithAddress] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [sent, setSent] = useState(new Set())
  const scrollRef = useRef(null)
  const [sendModal, setSendModal] = useState(null)
  const [successMsg, setSuccessMsg] = useState('')
  const [composing, setComposing] = useState(false)
  const [emailDraft, setEmailDraft] = useState(null)
  const [emailDraftKey, setEmailDraftKey] = useState(null)
  const [expandedAgencies, setExpandedAgencies] = useState(() => new Set())
  const [expandedBundles, setExpandedBundles] = useState(() => new Set())
  const [copied, setCopied] = useState(false)
  const isLiveTask = taskId === LIVE_TASK_ID
  const [liveItems, setLiveItems] = useState([])
  const [removedIds, setRemovedIds] = useState(() => new Set())
  const [patchedItems, setPatchedItems] = useState(() => new Map())
  const [geocodingId, setGeocodingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const seenLiveRef = useRef(new Set())
  const {
    preset: datePreset,
    customFrom,
    customTo,
    createdFrom,
    createdTo,
    dateFilterActive,
    handlePresetChange,
    setCustomFrom,
    setCustomTo,
    resetDateFilter,
  } = useIncidentDateFilter()

  const effectiveTaskId = taskId || null
  const { status: geocodeWarmup, startWarmup: startGeocodeWarmup } = useBackgroundGeocode(effectiveTaskId, {
    enabled: Boolean(effectiveTaskId),
    autoStart: false,
    pollMs: 5000,
  })
  const internalLiveFeed = useLiveFeed(!sharedLiveFeed && Boolean(effectiveTaskId), {
    taskId: isLiveTask ? LIVE_TASK_ID : effectiveTaskId,
  })
  const liveFeed = sharedLiveFeed || internalLiveFeed
  const severityMin = filterSev ?? PROBLEM_SEVERITY_MIN
  const severityMax = filterSev ?? 4
  const { facets } = useIncidentFacets(effectiveTaskId, {
    enabled: Boolean(effectiveTaskId),
    severityMin,
    severityMax,
    municipality: filterDistrict || null,
    group: filterGroup || null,
    resolved: false,
  })
  const {
    packages: agencyPackages,
    total,
    loaded,
    loading,
    loadingMore,
    backgroundLoading,
    error,
    hasMore,
    loadMore,
    reload,
  } = useTaskIncidentPackagesInfinite(effectiveTaskId, {
    enabled: Boolean(effectiveTaskId),
    bootstrap: loadEnabled,
    backgroundPrefetch: true,
    severityMin,
    severityMax,
    municipality: filterDistrict || null,
    group: filterGroup || null,
    topic: filterTopic || null,
    agency: filterAgency || null,
    hasAddress: onlyWithAddress || null,
    search: searchQuery || null,
    createdFrom,
    createdTo,
    resolved: false,
  })

  useEffect(() => {
    const timer = setTimeout(() => setSearchQuery(searchInput.trim()), 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  useEffect(() => {
    if (initialDistrict) setFilterDistrict(initialDistrict)
  }, [initialDistrict])

  useEffect(() => {
    for (const event of liveFeed.events) {
      const rowId = citizenRowId(event.id)
      if (!rowId || seenLiveRef.current.has(rowId)) continue
      seenLiveRef.current.add(rowId)
      const item = liveEventToIncident(event)
      setLiveItems((prev) => {
        if (prev.some((x) => x.id === item.id)) return prev
        return [item, ...prev].slice(0, 40)
      })
    }
  }, [liveFeed.events])

  useEffect(() => {
    if (!isLiveTask || liveFeed.received === 0) return undefined
    const timer = setTimeout(reload, 2000)
    return () => clearTimeout(timer)
  }, [isLiveTask, liveFeed.received, reload])

  const pageItems = useMemo(() => {
    const byId = new Map()
    const mergeItem = (item) => {
      const key = citizenRowId(item.id) || item.id
      if (removedIds.has(key)) return
      const patch = patchedItems.get(key) || patchedItems.get(item.id)
      const merged = patch ? { ...item, ...patch } : item
      const prev = byId.get(key)
      if (prev) {
        byId.set(key, { ...prev, ...merged })
      } else {
        byId.set(key, merged)
      }
    }
    for (const pkg of agencyPackages) {
      for (const bundle of pkg.bundles) {
        for (const item of bundle.items) mergeItem(item)
      }
    }
    for (const item of liveItems) {
      if (!incidentInDateRange(item.created_at, createdFrom, createdTo)) continue
      if (item.severity < severityMin || item.severity > severityMax) continue
      mergeItem(item)
    }
    return [...byId.values()]
      .filter(isOpenProblem)
      .sort((a, b) => b.severity - a.severity)
  }, [agencyPackages, liveItems, removedIds, patchedItems, createdFrom, createdTo, severityMin, severityMax])
  const openLoadedCount = pageItems.length

  useEffect(() => {
    if (geocodeWarmup?.geocoded_incidents > 0) reload()
  }, [geocodeWarmup?.geocoded_incidents, reload])

  const handleDeleteCitizen = async (item, e) => {
    e.stopPropagation()
    const rowId = citizenRowId(item.id)
    if (!isLiveTask || !isCitizenRowId(rowId)) return
    if (!window.confirm('Удалить это обращение из live-потока?')) return
    setDeletingId(rowId)
    try {
      await api.deleteCitizenIncident(LIVE_TASK_ID, rowId)
      setRemovedIds((prev) => new Set(prev).add(rowId))
      setLiveItems((prev) => prev.filter((x) => citizenRowId(x.id) !== rowId))
      setSelectedMap((prev) => {
        const next = new Map(prev)
        next.delete(item.id)
        next.delete(rowId)
        return next
      })
      reload()
      setSuccessMsg('Обращение удалено')
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err) {
      alert(err.message || 'Не удалось удалить обращение')
    } finally {
      setDeletingId(null)
    }
  }

  const handleGeocodeIncident = async (item, e) => {
    e.stopPropagation()
    if (!effectiveTaskId || !item.hasAddress) return
    const rowId = citizenRowId(item.id)
    setGeocodingId(rowId)
    try {
      const row = await api.geocodeIncident(effectiveTaskId, rowId, { cacheOnly: false })
      const updated = normalizeIncident(row, rowId)
      const patch = { lat: updated.lat, lng: updated.lng }
      setPatchedItems((prev) => new Map(prev).set(rowId, patch))
      setLiveItems((prev) => prev.map((x) => (citizenRowId(x.id) === rowId ? { ...x, ...patch } : x)))
      setSuccessMsg('Геокод получен и сохранён в кэш')
      setTimeout(() => setSuccessMsg(''), 3000)
      reload()
    } catch (err) {
      alert(err.message || 'Не удалось получить координаты')
    } finally {
      setGeocodingId(null)
    }
  }

  const handleShowOnMap = (item, e) => {
    e.stopPropagation()
    if (item.lat == null || item.lng == null) return
    onShowOnMap?.(item)
  }

  const districts = useMemo(() => {
    if (facets.municipalities?.length) return facets.municipalities
    const fromDashboard = municipalityOptions.map((name) => String(name).trim()).filter(Boolean)
    if (fromDashboard.length) return [...new Set(fromDashboard)].sort()
    return [...new Set(pageItems.map((i) => i.district).filter(Boolean))].sort()
  }, [facets.municipalities, municipalityOptions, pageItems])

  const activeFilterCount = [
    filterSev !== null,
    Boolean(filterDistrict),
    Boolean(filterGroup),
    Boolean(filterTopic),
    Boolean(filterAgency),
    onlyWithAddress,
    Boolean(searchQuery),
    dateFilterActive,
  ].filter(Boolean).length

  const resetFilters = () => {
    setFilterSev(null)
    setFilterDistrict(initialDistrict || '')
    setFilterGroup('')
    setFilterTopic('')
    setFilterAgency('')
    setOnlyWithAddress(false)
    setSearchInput('')
    setSearchQuery('')
    resetDateFilter()
  }

  const filterComboCls = 'text-xs px-2 py-1.5 rounded-lg w-full border outline-none focus:ring-1 focus:ring-red-500/20'

  const selectStyle = {
    background: 'var(--bg-sub)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
  }

  const loadedCount = loaded

  useEffect(() => {
    setFilterTopic('')
  }, [filterGroup])

  const toggle = (item) => {
    setSelectedMap((prev) => {
      const next = new Map(prev)
      if (next.has(item.id)) next.delete(item.id)
      else next.set(item.id, item)
      return next
    })
  }

  const allPageSelected = pageItems.length > 0 && pageItems.every((item) => selectedMap.has(item.id))

  const toggleBundleSelect = (bundle) => {
    const allSelected = bundle.items.every((item) => selectedMap.has(item.id))
    setSelectedMap((prev) => {
      const next = new Map(prev)
      if (allSelected) {
        bundle.items.forEach((item) => next.delete(item.id))
      } else {
        bundle.items.forEach((item) => next.set(item.id, item))
      }
      return next
    })
  }

  const toggleAgencyExpand = (agencyName) => {
    setExpandedAgencies((prev) => {
      const next = new Set(prev)
      if (next.has(agencyName)) next.delete(agencyName)
      else next.add(agencyName)
      return next
    })
  }

  const toggleBundleExpand = (bundleId) => {
    setExpandedBundles((prev) => {
      const next = new Set(prev)
      if (next.has(bundleId)) next.delete(bundleId)
      else next.add(bundleId)
      return next
    })
  }

  const handleSendBundle = (bundle) => {
    if (!bundle.items.length) return
    const agency = bundle.items[0].agency
    setSendModal([{ agency, items: bundle.items, bundleLabel: bundle.label }])
    handleCompose({ agency, items: bundle.items, bundleLabel: bundle.label }, `${agency.name}::${bundle.id}`)
  }

  const handleComposeBundle = (bundle, agency) => {
    handleCompose(
      { agency, items: bundle.items, bundleLabel: bundle.label },
      `${agency.name}::${bundle.id}`,
    )
  }

  const toggleAll = () => {
    setSelectedMap((prev) => {
      const next = new Map(prev)
      if (allPageSelected) {
        pageItems.forEach((item) => next.delete(item.id))
      } else {
        pageItems.forEach((item) => next.set(item.id, item))
      }
      return next
    })
  }

  const selectedItems = useMemo(() => [...selectedMap.values()], [selectedMap])
  const selectedCount = selectedItems.length

  const groupByAgency = (items) => {
    const map = {}
    for (const item of items) {
      const key = item.agency.name
      if (!map[key]) map[key] = { agency: item.agency, items: [] }
      map[key].items.push(item)
    }
    return Object.values(map)
  }

  const handleSend = () => {
    if (!selectedItems.length) return
    setSendModal(groupByAgency(selectedItems))
  }

  const confirmSend = () => {
    setSent((prev) => {
      const next = new Set(prev)
      selectedItems.forEach((i) => next.add(i.id))
      return next
    })
    setSelectedMap(new Map())
    setSendModal(null)
    setEmailDraft(null)
    setSuccessMsg(`Пакет из ${selectedItems.length} обращений отправлен в ведомства`)
    setTimeout(() => setSuccessMsg(''), 4000)
  }

  const handleCompose = async (group, draftKey = group.agency.name) => {
    setComposing(draftKey)
    setEmailDraft(null)
    setEmailDraftKey(null)
    setCopied(false)
    try {
      const incidents = group.items.map((i) => ({
        text: i.text,
        severity: i.severity,
        label: i.label,
        district: i.district,
        category: i.group || i.category,
        topic: i.topic || '',
      }))
      const result = await api.composeEmail(
        incidents,
        group.agency.name,
        group.agency.email,
        group.bundleLabel || null,
      )
      setEmailDraft(result)
      setEmailDraftKey(draftKey)
    } catch {
      setEmailDraft({
        subject: 'Ошибка генерации',
        body: 'Не удалось получить ответ от LLM. Проверьте соединение с Ollama.',
      })
      setEmailDraftKey(draftKey)
    } finally {
      setComposing(false)
    }
  }

  const handleCopy = () => {
    if (!emailDraft) return
    navigator.clipboard.writeText(`Тема: ${emailDraft.subject}\n\n${emailDraft.body}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const card = { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12 }

  if (!effectiveTaskId) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
        Загрузите файл и дождитесь завершения анализа — обращения появятся из вашей задачи.
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

      {/* ── Тулбар ─────────────────────────────────────────── */}
      <div className="operator-toolbar">
        <div className="operator-toolbar__card">

          {/* Строка 1: заголовок + фильтры по тяжести + кнопка отправки */}
          <div className="operator-toolbar__row">
            <span className="operator-toolbar__title">
              Обращения · нерешённые
              <span className="operator-toolbar__count">
                {openLoadedCount.toLocaleString('ru-RU')} открытых
                {hasMore
                  ? ` · загружено ${loadedCount.toLocaleString('ru-RU')} из ${total.toLocaleString('ru-RU')}`
                  : total !== openLoadedCount
                    ? ` · всего ${total.toLocaleString('ru-RU')}`
                    : ''}
              </span>
              {(loading || loadingMore) && <Loader2 className="w-3.5 h-3.5 animate-spin text-red-500" />}
              {backgroundLoading && !loading && !loadingMore && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-sub)', color: 'var(--muted)' }}>
                  фон · {loadedCount.toLocaleString('ru-RU')}/{total.toLocaleString('ru-RU')}
                </span>
              )}
            </span>

            <div className="flex items-center gap-1.5 flex-wrap" role="group" aria-label="Фильтр по классу">
              <Filter className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--muted)' }} />
              {SEVERITY_FILTER_OPTIONS.map((sev) => (
                <button
                  key={sev ?? 'all'}
                  type="button"
                  onClick={() => setFilterSev(sev)}
                  className={`emergency-sev-btn${filterSev === sev ? ' emergency-sev-btn--active' : ''}`}
                  style={filterSev === sev && sev !== null ? { '--sev-color': SEVERITY_COLORS[sev] } : undefined}
                  data-sev={sev ?? 'all'}
                >
                  {sev === null ? 'Все' : SEVERITY_LABELS[sev]}
                </button>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2 flex-shrink-0">
              {selectedCount > 0 && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
                  style={{ background: '#fee2e2', color: '#dc2626' }}>
                  {selectedCount} выбрано
                </span>
              )}
              <button
                type="button"
                onClick={handleSend}
                disabled={!selectedCount}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                style={{
                  background: selectedCount ? '#dc2626' : 'var(--bg-sub)',
                  color: selectedCount ? '#fff' : 'var(--muted)',
                  cursor: selectedCount ? 'pointer' : 'not-allowed',
                  border: selectedCount ? 'none' : '1px solid var(--border)',
                  boxShadow: selectedCount ? '0 2px 8px #dc262640' : 'none',
                }}
              >
                <Send className="w-3.5 h-3.5" />
                Отправить в ведомство
              </button>
            </div>
          </div>

          {/* Строка 2: дата + поиск + фильтры */}
          <div className="operator-toolbar__row operator-toolbar__filters">
            <IncidentDateFilter
              preset={datePreset}
              onPresetChange={handlePresetChange}
              from={customFrom}
              to={customTo}
              onFromChange={setCustomFrom}
              onToChange={setCustomTo}
              compact
            />

            <div className="emergency-toolbar__divider" style={{ height: '24px', width: '1px', background: 'var(--border)', flexShrink: 0 }} />

            <div className="relative min-w-[180px] max-w-xs flex-1">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted)' }} />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Поиск по тексту, адресу, теме…"
                className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg"
                style={selectStyle}
              />
            </div>

            <SearchableSelect
              value={filterDistrict}
              onChange={setFilterDistrict}
              options={districts}
              placeholder="Все МО"
              className="min-w-[130px] max-w-[180px]"
              inputClassName={filterComboCls}
              commitOnPick
            />

            <SearchableSelect
              value={filterGroup}
              onChange={setFilterGroup}
              options={facets.groups}
              placeholder="Все группы"
              className="min-w-[120px] max-w-[170px]"
              inputClassName={filterComboCls}
              commitOnPick
            />

            <SearchableSelect
              value={filterTopic}
              onChange={setFilterTopic}
              options={facets.topics}
              placeholder="Все темы"
              className="min-w-[140px] max-w-[200px]"
              inputClassName={filterComboCls}
              commitOnPick
            />

            <select
              value={filterAgency}
              onChange={(e) => setFilterAgency(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg max-w-[200px]"
              style={selectStyle}
            >
              <option value="">Все ведомства</option>
              {facets.agencies.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>

            <button
              type="button"
              onClick={() => setOnlyWithAddress((v) => !v)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all"
              style={{
                ...selectStyle,
                background: onlyWithAddress ? '#dbeafe' : selectStyle.background,
                color: onlyWithAddress ? '#1d4ed8' : 'var(--text-2)',
                borderColor: onlyWithAddress ? '#93c5fd' : selectStyle.border,
              }}
            >
              <MapPin className="w-3.5 h-3.5" />
              С адресом{facets.with_address ? ` · ${facets.with_address.toLocaleString('ru-RU')}` : ''}
            </button>

            {effectiveTaskId && (
              <GeocodeWarmupButton geocodeWarmup={geocodeWarmup} startWarmup={startGeocodeWarmup} compact />
            )}

            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={resetFilters}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold"
                style={{ color: 'var(--muted)', background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Сбросить ({activeFilterCount})
              </button>
            )}
          </div>

        </div>
      </div>

      {/* ── Уведомления ────────────────────────────────────── */}
      {error && (
        <div className="mx-4 mt-3 px-4 py-2.5 rounded-xl flex items-center gap-2 text-sm"
          style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {successMsg && (
        <div className="mx-4 mt-3 px-4 py-2.5 rounded-xl flex items-center gap-2 text-sm font-medium"
          style={{ background: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0' }}>
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {successMsg}
        </div>
      )}

      {/* ── Пакеты по ведомствам (аккордеон) ───────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
        {loading && !pageItems.length && (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-sm" style={{ color: 'var(--muted)' }}>
            <Loader2 className="w-5 h-5 animate-spin" />
            Загрузка обращений…
          </div>
        )}

        {!loading && openLoadedCount > 0 && (
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <button type="button" onClick={toggleAll} className="flex items-center gap-2 text-xs" style={{ color: 'var(--muted)' }}>
              {allPageSelected
                ? <CheckSquare className="w-4 h-4 text-red-600" />
                : <Square className="w-4 h-4" />}
              Выбрать все загруженные ({openLoadedCount})
            </button>
            {hasMore && (
              <button
                type="button"
                onClick={loadMore}
                disabled={loading || loadingMore}
                className="ml-auto px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-50"
                style={{ background: '#dc2626', color: '#fff' }}
              >
                {loadingMore ? 'Загрузка…' : `Загрузить ещё (${loadedCount.toLocaleString('ru-RU')} / ${total.toLocaleString('ru-RU')})`}
              </button>
            )}
          </div>
        )}

        {!loading && !openLoadedCount && hasMore && (
          <div className="flex justify-center py-8">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
              style={{ background: '#dc2626', color: '#fff' }}
            >
              {loadingMore ? 'Загрузка…' : 'Загрузить обращения'}
            </button>
          </div>
        )}

        <IncidentPackageList
          packages={agencyPackages}
          selectedMap={selectedMap}
          expandedAgencies={expandedAgencies}
          expandedBundles={expandedBundles}
          onToggleAgency={toggleAgencyExpand}
          onToggleBundleExpand={toggleBundleExpand}
          onToggleBundleSelect={toggleBundleSelect}
          onToggleItem={toggle}
          onSendBundle={handleSendBundle}
          onComposeBundle={handleComposeBundle}
          composingKey={composing}
          sent={sent}
          geocodingId={geocodingId}
          deletingId={deletingId}
          isLiveTask={isLiveTask}
          onGeocode={handleGeocodeIncident}
          onDeleteCitizen={handleDeleteCitizen}
          onShowOnMap={onShowOnMap}
        />

        {backgroundLoading && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs" style={{ color: 'var(--muted)' }}>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Фоновая догрузка · {loadedCount.toLocaleString('ru-RU')} / {total.toLocaleString('ru-RU')}
          </div>
        )}

        {!loading && !loadingMore && hasMore && openLoadedCount > 0 && !backgroundLoading && (
          <div className="flex justify-center py-3">
            <button
              type="button"
              onClick={loadMore}
              className="px-4 py-2 rounded-lg text-xs font-semibold"
              style={{ background: 'var(--bg-sub)', color: 'var(--text)', border: '1px solid var(--border)' }}
            >
              Загрузить ещё · {loadedCount.toLocaleString('ru-RU')} / {total.toLocaleString('ru-RU')}
            </button>
          </div>
        )}

        {!hasMore && loadedCount > 0 && !loading && (
          <p className="text-center text-xs py-4" style={{ color: 'var(--muted)' }}>
            {openLoadedCount.toLocaleString('ru-RU')} открытых обращений в {agencyPackages.length} ведомствах
          </p>
        )}
      </div>

      {!sharedLiveFeed && <LiveDemoPanel enabled={Boolean(effectiveTaskId)} feed={liveFeed} />}

      {sendModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => { setSendModal(null); setEmailDraft(null) }}
        >
          <div
            className="w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', maxHeight: '90vh' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
              <h2 className="font-bold text-base" style={{ color: 'var(--text)' }}>
                Отправить в ведомства · {selectedItems.length} обращений
              </h2>
              <button type="button" onClick={() => { setSendModal(null); setEmailDraft(null) }}>
                <X className="w-5 h-5" style={{ color: 'var(--muted)' }} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {sendModal.map((group) => (
                <div key={`${group.agency.name}-${group.bundleLabel || ''}`} className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-between gap-2 px-4 py-3" style={{ background: 'var(--bg-sub)' }}>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>
                        {group.agency.name}
                      </div>
                      {group.bundleLabel && (
                        <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-2)' }}>
                          {group.bundleLabel}
                        </div>
                      )}
                      {group.agency.email ? (
                        <div className="flex items-center gap-1 text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
                          <Mail className="w-3 h-3 flex-shrink-0" />
                          {group.agency.email}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">
                        {group.items.length} обр.
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCompose(group, group.bundleLabel ? `${group.agency.name}::${group.bundleLabel}` : group.agency.name)}
                        disabled={!!composing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                        style={{
                          background: composing ? 'var(--bg-sub)' : '#2563eb',
                          color: composing ? 'var(--muted)' : '#fff',
                        }}
                      >
                        {composing
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : <Mail className="w-3.5 h-3.5" />}
                        {composing ? 'Генерация...' : 'Письмо AI'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              {composing && !emailDraft && (
                <div className="flex flex-col items-center gap-2 py-6" style={{ color: 'var(--muted)' }}>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-sm">LLM генерирует письмо...</span>
                </div>
              )}

              {emailDraft && (
                <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #3b82f6', background: '#eff6ff' }}>
                  <div className="flex items-center justify-between px-4 py-2.5"
                    style={{ borderBottom: '1px solid #bfdbfe', background: '#dbeafe' }}>
                    <span className="text-xs font-bold text-blue-700">Сгенерированное письмо</span>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold"
                      style={{ background: copied ? '#16a34a' : '#2563eb', color: '#fff' }}
                    >
                      <Copy className="w-3.5 h-3.5" />
                      {copied ? 'Скопировано!' : 'Копировать'}
                    </button>
                  </div>
                  <div className="px-4 py-3">
                    <div className="text-xs font-semibold text-blue-800 mb-1">Тема:</div>
                    <div className="text-sm font-medium text-blue-900 mb-3">{emailDraft.subject}</div>
                    <div className="text-xs font-semibold text-blue-800 mb-1">Текст письма:</div>
                    <pre className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed" style={{ fontFamily: 'inherit' }}>
                      {emailDraft.body}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2 justify-end px-6 py-4" style={{ borderTop: '1px solid var(--border)' }}>
              <button
                type="button"
                onClick={() => { setSendModal(null); setEmailDraft(null) }}
                className="px-4 py-2 rounded-xl text-sm"
                style={{ background: 'var(--bg-sub)', color: 'var(--muted)' }}
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={confirmSend}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold"
                style={{ background: '#dc2626', color: '#fff' }}
              >
                <Send className="w-4 h-4" />
                Подтвердить отправку
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
