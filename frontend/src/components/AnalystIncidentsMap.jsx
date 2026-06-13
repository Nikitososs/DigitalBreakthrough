import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Siren, Loader2, AlertCircle, Filter, MapPin, MapPinOff, Database, Maximize2, Minimize2, Eye, EyeOff, TrendingUp, CheckCircle2 } from 'lucide-react'
import { MapContainer, TileLayer, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import EmergencyMarkerCluster from './EmergencyMarkerCluster'
import ResolvedBadge from './ResolvedBadge'
import MunicipalityBoundariesLayer from './MunicipalityBoundariesLayer'
import GeocodeWarmupButton from './GeocodeWarmupButton'
import EmergencyTimeline from './EmergencyTimeline'
import { useBackgroundGeocode } from '../hooks/useBackgroundGeocode'
import { useEmergencyTimeline } from '../hooks/useEmergencyTimeline'
import { useLiveFeed } from '../hooks/useLiveFeed'
import { usePeriodMapMarkers, useTaskIncidents } from '../hooks/useTaskIncidents'
import { incidentInDateRange } from '../utils/incidentDateFilter'
import {
  citizenRowId,
  incidentDisplayMeta,
  isIncidentResolved,
  liveEventToIncident,
  SEVERITY_COLORS,
  SEVERITY_FILTER_OPTIONS,
  SEVERITY_LABELS,
  PROBLEM_SEVERITY_MIN,
} from '../utils/incidentModel'
import { cleanAppealText } from '../utils/cleanAppealText'
import { mapTileLayer } from '../utils/mapTiles'

const MAP_BOUNDS = L.latLngBounds([[52.5, 68.0], [59.5, 78.0]])
const MAP_CENTER = [55.8, 73.2]
const MAP_ZOOM = 6
const MAP_MIN_ZOOM = 6.5

function incidentToMapView(incident) {
  const meta = incidentDisplayMeta(incident)
  const geocoded = incident.lat != null && incident.lng != null
  return {
    id: incident.id,
    label: meta.label,
    icon: meta.icon,
    color: meta.color,
    address: incident.address || incident.municipality || 'Омская область',
    coords: geocoded ? [Number(incident.lat), Number(incident.lng)] : null,
    radius: meta.radius,
    risk: incident.text,
    severity: incident.severity,
    isLive: Boolean(incident.isLive),
    onMap: geocoded,
    geocoded,
    source: incident,
  }
}

function severityBadge(severity) {
  if (severity >= 4) return { short: '🚨 ЧП', label: SEVERITY_LABELS[4] }
  if (severity >= 3) return { short: '⚠️ Высок.', label: SEVERITY_LABELS[3] }
  return { short: `Кл. ${severity}`, label: SEVERITY_LABELS[severity] || '' }
}

function MapIncidentCard({ pin }) {
  const badge = severityBadge(pin.severity)
  const text = cleanAppealText(pin.risk)
  const preview = text.length > 280 ? `${text.slice(0, 280)}…` : text

  return (
    <div className="emergency-map-card" style={{ '--pin-color': pin.color }}>
      <div className="emergency-map-card__header">
        <span className="emergency-map-card__badge">{badge.short}</span>
        <span className="emergency-map-card__level">{badge.label} · класс {pin.severity}</span>
        {pin.source && <ResolvedBadge item={pin.source} />}
        {pin.isLive && <span className="emergency-map-card__live">LIVE</span>}
      </div>
      <div className="emergency-map-card__topic">{pin.label}</div>
      <div className="emergency-map-card__address">{pin.address}</div>
      <p className="emergency-map-card__text">{preview || 'Текст обращения не указан'}</p>
    </div>
  )
}

function createIncidentIcon(color, { active = false, geocoded = false, severity = 3 } = {}) {
  const size = active ? 40 : geocoded ? 30 : 26
  const border = active ? 3 : 2
  const emoji = severity >= 4 ? '🚨' : geocoded ? '📍' : '⚠️'
  const pulse = active
    ? `<div class="emergency-marker-pulse" style="border-color:${color}"></div>`
    : ''
  return L.divIcon({
    className: active ? 'emergency-marker emergency-marker--active' : 'emergency-marker',
    html: `
      <div class="emergency-marker-wrap" style="width:${size}px;height:${size}px;">
        ${pulse}
        <div class="emergency-marker-core" style="
          width:${size}px;height:${size}px;background:${color};border:${border}px solid #fff;
          box-shadow:0 4px 14px ${color}66, 0 0 0 ${active ? 5 : 3}px ${color}40;
          font-size:${active ? 17 : 13}px;
        ">${emoji}</div>
      </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

function MapConstraints() {
  const map = useMap()
  useEffect(() => {
    map.setMinZoom(MAP_MIN_ZOOM)
    map.setMaxBounds(MAP_BOUNDS)
    map.options.maxBoundsViscosity = 3.0
    map.options.bounceAtZoomLimits = false
    const clampZoom = () => {
      if (map.getZoom() < MAP_MIN_ZOOM) map.setZoom(MAP_MIN_ZOOM, { animate: false })
    }
    map.on('zoom', clampZoom)
    map.on('zoomend', clampZoom)
    return () => {
      map.off('zoom', clampZoom)
      map.off('zoomend', clampZoom)
    }
  }, [map])
  return null
}

function MapFlyTo({ coords, zoom = 14 }) {
  const map = useMap()
  useEffect(() => {
    if (!coords) return
    map.flyTo(coords, zoom, { duration: 0.8 })
  }, [map, coords?.[0], coords?.[1], zoom])
  return null
}

function MapInvalidateSize({ active }) {
  const map = useMap()
  useEffect(() => {
    const run = () => map.invalidateSize({ animate: false })
    const t1 = setTimeout(run, 50)
    const t2 = setTimeout(run, 300)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [active, map])
  return null
}

export default function AnalystIncidentsMap({
  dark,
  taskId = null,
  focusIncident = null,
  onFocusConsumed = null,
  showTiles = true,
  onToggleTiles = null,
  onSwitchToDistricts = null,
}) {
  const effectiveTaskId = taskId || null
  const [activeIncident, setActiveIncident] = useState(null)
  const mapWrapRef = useRef(null)
  const [mapExpanded, setMapExpanded] = useState(false)
  const [liveItems, setLiveItems] = useState([])
  const seenLiveRef = useRef(new Set())
  const [filterSev, setFilterSev] = useState(null)
  const [filterResolved, setFilterResolved] = useState(null)
  const {
    preset: timelinePreset,
    windowDays,
    datasetStart,
    datasetEnd,
    offsetDays,
    maxOffsetDays,
    createdFrom,
    createdTo,
    fetchCreatedFrom,
    fetchCreatedTo,
    fetchPending: timelineFetchPending,
    loadingMeta: timelineLoading,
    setWindowOffset,
    commitWindowOffset,
    jumpToLatest,
    selectPreset,
    ready: timelineReady,
  } = useEmergencyTimeline(effectiveTaskId, { enabled: Boolean(effectiveTaskId), initialPreset: '7d' })

  const severityMin = filterSev ?? PROBLEM_SEVERITY_MIN
  const severityMax = filterSev ?? 4
  const severityLabel = filterSev == null ? 'классы 1–4' : `класс ${filterSev}`

  const liveFeed = useLiveFeed(Boolean(effectiveTaskId), { taskId: effectiveTaskId })

  const { status: geocodeWarmup, startWarmup } = useBackgroundGeocode(effectiveTaskId, {
    enabled: Boolean(effectiveTaskId),
    autoStart: true,
    pollMs: 5000,
  })

  const { total: periodTotal, loading: countLoading } = useTaskIncidents(effectiveTaskId, {
    severityMin,
    severityMax,
    createdFrom: fetchCreatedFrom,
    createdTo: fetchCreatedTo,
    resolved: filterResolved,
    limit: 1,
    enabled: Boolean(effectiveTaskId) && timelineReady,
  })

  const { total: chpTotal } = useTaskIncidents(effectiveTaskId, {
    severityMin: 4,
    severityMax: 4,
    createdFrom: fetchCreatedFrom,
    createdTo: fetchCreatedTo,
    resolved: filterResolved,
    limit: 1,
    enabled: Boolean(effectiveTaskId) && timelineReady && filterSev == null,
  })

  const { items: mapItems, total: geocodedTotal, loading: mapLoading, error: mapError, reload: reloadMap } = usePeriodMapMarkers(
    effectiveTaskId,
    {
      severityMin,
      severityMax,
      createdFrom: fetchCreatedFrom,
      createdTo: fetchCreatedTo,
      resolved: filterResolved,
      enabled: Boolean(effectiveTaskId) && timelineReady,
    },
  )

  const loading = countLoading || mapLoading
  const error = mapError

  useEffect(() => {
    if ((geocodeWarmup?.geocoded_incidents ?? 0) > 0) reloadMap()
  }, [geocodeWarmup?.geocoded_incidents, reloadMap])

  useEffect(() => {
    setLiveItems([])
    seenLiveRef.current = new Set()
  }, [severityMin, severityMax, fetchCreatedFrom, fetchCreatedTo, filterResolved])

  useEffect(() => {
    for (const event of liveFeed.events) {
      const rowId = citizenRowId(event.id)
      if (!rowId || seenLiveRef.current.has(rowId)) continue
      seenLiveRef.current.add(rowId)
      if (event.severity < severityMin || event.severity > severityMax) continue
      const item = liveEventToIncident(event)
      if (!incidentInDateRange(item.created_at, fetchCreatedFrom, fetchCreatedTo)) continue
      if (filterResolved != null) {
        const resolved = isIncidentResolved(item)
        if (filterResolved ? !resolved : resolved) continue
      }
      setLiveItems((prev) => {
        if (prev.some((x) => x.id === item.id)) return prev
        return [item, ...prev].slice(0, 30)
      })
    }
  }, [liveFeed.events, severityMin, severityMax, fetchCreatedFrom, fetchCreatedTo, filterResolved])

  const geocodedById = useMemo(() => {
    const byId = new Map()
    for (const item of mapItems) {
      if (item.lat != null && item.lng != null) byId.set(item.id, item)
    }
    for (const item of liveItems) {
      if (item.lat != null && item.lng != null) byId.set(item.id, item)
    }
    return byId
  }, [mapItems, liveItems])

  const selectIncident = useCallback((item) => {
    const enriched = geocodedById.get(item.id) || item
    setActiveIncident(incidentToMapView(enriched))
  }, [geocodedById])

  useEffect(() => {
    if (!focusIncident?.id) return
    const fromMap = geocodedById.get(focusIncident.id)
    const base = fromMap || focusIncident
    const item = {
      ...base,
      ...(focusIncident.lat != null && focusIncident.lng != null
        ? { lat: focusIncident.lat, lng: focusIncident.lng }
        : {}),
    }
    if (item.lat == null || item.lng == null) return
    selectIncident(item)
    onFocusConsumed?.()
  }, [focusIncident, geocodedById, selectIncident, onFocusConsumed])

  const incident = activeIncident

  const mapMarkers = useMemo(
    () => [...geocodedById.values()]
      .sort((a, b) => b.severity - a.severity)
      .map((item) => incidentToMapView(item)),
    [geocodedById],
  )

  useEffect(() => {
    const onFullscreenChange = () => {
      setMapExpanded(document.fullscreenElement === mapWrapRef.current)
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const toggleMapFullscreen = useCallback(() => {
    const el = mapWrapRef.current
    if (!el) return
    if (document.fullscreenElement === el) {
      document.exitFullscreen?.()
      setMapExpanded(false)
    } else {
      setMapExpanded(true)
      el.requestFullscreen?.().catch(() => {})
    }
  }, [])

  const card = { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14 }
  const tiles = mapTileLayer(dark)
  const onMapTotal = geocodedTotal ?? 0
  const withoutCoords = Math.max(0, (periodTotal ?? 0) - onMapTotal)
  const chpInPeriod = filterSev == null ? (chpTotal ?? 0) : 0
  const incidentMunicipality = incident?.source?.municipality || incident?.source?.district || null

  if (!effectiveTaskId) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
        Загрузите файл и дождитесь анализа — обращения появятся из вашей задачи.
      </div>
    )
  }

  return (
    <div className={`flex-1 flex flex-col min-h-0 overflow-hidden emergency-screen${mapExpanded ? ' emergency-screen--map-expanded' : ''}`}>
      {error && (
        <div className="mx-4 mt-3 px-4 py-2.5 rounded-xl flex items-center gap-2 text-sm flex-shrink-0"
          style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="analyst-incidents-layout flex-1 min-h-0">
        <div className="analyst-map-main flex-1 flex flex-col min-h-0 min-w-0 p-3">
          {incident && (
            <div className="flex-shrink-0 emergency-incident-card mb-3" style={{ '--incident-color': incident.color }}>
              <div className="emergency-incident-card__top">
                <span className="emergency-incident-card__badge">
                  {incident.severity >= 4 ? '🚨 ЧП' : '⚠️ Высокая'}
                </span>
                <span className="emergency-incident-card__class">Класс {incident.severity}</span>
                {incident.source && <ResolvedBadge item={incident.source} />}
                {incident.isLive && <span className="emergency-incident-card__tag emergency-incident-card__tag--live">LIVE</span>}
              </div>
              <p className="emergency-incident-card__title">{incident.label}</p>
              <p className="emergency-incident-card__address">{incident.address}</p>
              <p className="emergency-incident-card__text">{cleanAppealText(incident.risk)}</p>
            </div>
          )}

          {mapMarkers.length > 0 || incident ? (
            <div
              ref={mapWrapRef}
              className={`flex-1 min-h-[280px] rounded-2xl overflow-hidden emergency-map-wrap shadow-md relative flex flex-col${mapExpanded ? ' emergency-map-wrap--expanded' : ''}`}
              style={card}
            >
              <div
                className="flex items-center gap-2 px-3 py-2 flex-shrink-0"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <MapPin className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                <span className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>Обращения на карте</span>
                <div className="ml-auto flex items-center gap-1 flex-shrink-0">
                  {onSwitchToDistricts && (
                    <button
                      type="button"
                      onClick={onSwitchToDistricts}
                      className="analyst-map-feed-btn"
                      title="Рейтинг муниципалитетов"
                      aria-label="Рейтинг муниципалитетов"
                    >
                      <TrendingUp className="w-5 h-5" />
                    </button>
                  )}
                  {onToggleTiles && (
                    <button
                      type="button"
                      onClick={onToggleTiles}
                      className="analyst-map-feed-btn"
                      style={{ color: showTiles ? 'var(--muted)' : '#dc2626' }}
                      title={showTiles ? 'Скрыть подложку' : 'Показать подложку'}
                      aria-label={showTiles ? 'Скрыть подложку' : 'Показать подложку'}
                    >
                      {showTiles ? <Eye className="w-5 h-5" /> : <EyeOff className="w-5 h-5" />}
                    </button>
                  )}
                  <button
                    type="button"
                    className="emergency-map-fullscreen-btn emergency-map-fullscreen-btn--inline"
                    onClick={toggleMapFullscreen}
                    title={mapExpanded ? 'Свернуть карту' : 'Карта на весь экран'}
                    aria-label={mapExpanded ? 'Свернуть карту' : 'Развернуть карту на весь экран'}
                  >
                    {mapExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div className="flex-1 min-h-0 relative">
                <div className="emergency-map-legend">
                  <span className="emergency-map-legend__item"><i className="emergency-map-legend__dot emergency-map-legend__dot--mo" /> МО</span>
                  <span className="emergency-map-legend__item"><i className="emergency-map-legend__dot emergency-map-legend__dot--pin" /> Инцидент</span>
                  <span className="emergency-map-legend__item"><i className="emergency-map-legend__dot emergency-map-legend__dot--cluster" /> Группа</span>
                </div>
                <MapContainer
                  center={MAP_CENTER}
                  zoom={MAP_ZOOM}
                  minZoom={MAP_MIN_ZOOM}
                  maxBounds={MAP_BOUNDS}
                  maxBoundsViscosity={3.0}
                  bounceAtZoomLimits={false}
                  className={dark ? 'leaflet-map--dark' : 'leaflet-map--light'}
                  style={{ width: '100%', height: '100%', minHeight: 240 }}
                  zoomControl
                >
                  <MapConstraints />
                  <MapInvalidateSize active={mapExpanded} />
                  {incident?.geocoded && incident.coords && (
                    <MapFlyTo coords={incident.coords} />
                  )}
                  {showTiles && <TileLayer url={tiles.url} attribution={tiles.attribution} />}
                  <MunicipalityBoundariesLayer
                    dark={dark}
                    highlightMunicipality={incidentMunicipality}
                  />
                  <EmergencyMarkerCluster
                    markers={mapMarkers.filter((pin) => pin.coords)}
                    activeId={incident?.id}
                    createIcon={createIncidentIcon}
                    renderPopup={(pin) => <MapIncidentCard pin={pin} />}
                    onSelect={selectIncident}
                  />
                  {incident?.geocoded && incident.coords && (
                    <Circle
                      center={incident.coords}
                      radius={incident.radius}
                      pathOptions={{ color: incident.color, fillColor: incident.color, fillOpacity: 0.12, weight: 2 }}
                    />
                  )}
                </MapContainer>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-sm rounded-2xl" style={{ color: 'var(--muted)', ...card }}>
              {loading ? 'Загрузка обращений…' : `Нет обращений (${severityLabel}) в задаче`}
            </div>
          )}
        </div>

        <aside className="analyst-map-sidebar" aria-label="Фильтры и статистика">
          <div className="analyst-map-sidebar__section">
            <div className="analyst-map-sidebar__title">
              <Filter className="w-3.5 h-3.5" aria-hidden />
              <span>Класс</span>
            </div>
            <div className="analyst-map-sidebar__filters" role="group" aria-label="Фильтр по классу">
              {SEVERITY_FILTER_OPTIONS.map((sev) => (
                <button
                  key={sev ?? 'all'}
                  type="button"
                  onClick={() => setFilterSev(sev)}
                  className={`emergency-sev-btn analyst-map-sidebar__sev-btn${filterSev === sev ? ' emergency-sev-btn--active' : ''}`}
                  style={sev !== null ? { '--sev-color': SEVERITY_COLORS[sev] } : undefined}
                  data-sev={sev ?? 'all'}
                >
                  <span className="analyst-map-sidebar__sev-dot" aria-hidden />
                  <span className="analyst-map-sidebar__sev-label">{sev === null ? 'Все классы' : SEVERITY_LABELS[sev]}</span>
                </button>
              ))}
            </div>
            <div className="analyst-map-sidebar__actions">
              {loading && (
                <span className="emergency-toolbar__loading">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  {mapLoading ? 'Геокод…' : 'Загрузка…'}
                </span>
              )}
              <GeocodeWarmupButton geocodeWarmup={geocodeWarmup} startWarmup={startWarmup} compact />
            </div>
          </div>

          <div className="analyst-map-sidebar__section">
            <div className="analyst-map-sidebar__title">
              <CheckCircle2 className="w-3.5 h-3.5" aria-hidden />
              <span>Решённость</span>
            </div>
            <div className="analyst-map-sidebar__filters" role="group" aria-label="Фильтр по решённости">
              {[
                { value: null, label: 'Все' },
                { value: true, label: 'Решённые' },
                { value: false, label: 'Открытые' },
              ].map(({ value, label }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setFilterResolved(value)}
                  className={`resolved-filter-btn analyst-map-sidebar__sev-btn${filterResolved === value ? ' resolved-filter-btn--active' : ''}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="analyst-map-sidebar__section analyst-map-sidebar__section--timeline">
            <EmergencyTimeline
              variant="sidebar"
              preset={timelinePreset}
              windowDays={windowDays}
              createdFrom={createdFrom}
              createdTo={createdTo}
              offsetDays={offsetDays}
              maxOffsetDays={maxOffsetDays}
              datasetStart={datasetStart}
              datasetEnd={datasetEnd}
              loading={timelineLoading}
              onPresetChange={selectPreset}
              fetchPending={timelineFetchPending}
              onOffsetChange={setWindowOffset}
              onOffsetCommit={commitWindowOffset}
              onJumpLatest={jumpToLatest}
            />
          </div>

          <div className="analyst-map-sidebar__section analyst-map-sidebar__kpi" aria-label="Статистика периода">
            <div className="analyst-map-sidebar__title">
              <Database className="w-3.5 h-3.5" aria-hidden />
              <span>Статистика</span>
            </div>
            <div className="emergency-kpi-cell" title={`Всего обращений за ${windowDays} дн.`}>
              <div className="emergency-kpi-cell__icon-wrap"><Database /></div>
              <div className="emergency-kpi-cell__body">
                <span className="emergency-kpi-cell__label">Всего</span>
                <span className="emergency-kpi-cell__value">{periodTotal > 0 ? periodTotal.toLocaleString('ru-RU') : '—'}</span>
                <span className="emergency-kpi-cell__sub">за {windowDays} дн.</span>
              </div>
            </div>
            <div className="emergency-kpi-cell emergency-kpi-cell--blue" title="С координатами на карте">
              <div className="emergency-kpi-cell__icon-wrap"><MapPin /></div>
              <div className="emergency-kpi-cell__body">
                <span className="emergency-kpi-cell__label">На карте</span>
                <span className="emergency-kpi-cell__value">{onMapTotal > 0 ? onMapTotal.toLocaleString('ru-RU') : '—'}</span>
                <span className="emergency-kpi-cell__sub">{periodTotal > 0 ? `из ${periodTotal.toLocaleString('ru-RU')}` : ''}</span>
              </div>
            </div>
            <div className="emergency-kpi-cell emergency-kpi-cell--muted" title="Без координат">
              <div className="emergency-kpi-cell__icon-wrap"><MapPinOff /></div>
              <div className="emergency-kpi-cell__body">
                <span className="emergency-kpi-cell__label">Без координат</span>
                <span className="emergency-kpi-cell__value">{withoutCoords > 0 ? withoutCoords.toLocaleString('ru-RU') : '—'}</span>
                {liveItems.length > 0
                  ? <span className="emergency-kpi-cell__sub" style={{ color: '#dc2626' }}>+{liveItems.length} live</span>
                  : <span className="emergency-kpi-cell__sub">&nbsp;</span>}
              </div>
            </div>
            <div className={`emergency-kpi-cell ${chpInPeriod > 0 ? 'emergency-kpi-cell--red' : 'emergency-kpi-cell--muted'}`} title="ЧП (класс 4)">
              <div className="emergency-kpi-cell__icon-wrap"><Siren /></div>
              <div className="emergency-kpi-cell__body">
                <span className="emergency-kpi-cell__label">ЧП</span>
                <span className="emergency-kpi-cell__value">{chpInPeriod > 0 ? chpInPeriod.toLocaleString('ru-RU') : '—'}</span>
                <span className="emergency-kpi-cell__sub">класс 4</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
