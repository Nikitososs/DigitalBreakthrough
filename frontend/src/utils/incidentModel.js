import { cleanAppealText } from './cleanAppealText'
import { getMunicipalityBounds, getMunicipalityCoords } from './municipalityCoords'

export const SEVERITY_COLORS = {
  0: '#94a3b8',
  1: '#84cc16',
  2: '#eab308',
  3: '#f97316',
  4: '#dc2626',
}

export const SEVERITY_LABELS = {
  0: 'Шум',
  1: 'Низкая',
  2: 'Средняя',
  3: 'Высокая',
  4: 'Критическая',
}

/** Минимальный класс для списков/карт (без «Шум»). */
export const PROBLEM_SEVERITY_MIN = 1

/** Кнопки фильтра по тяжести: null = все проблемные классы. */
export const SEVERITY_FILTER_OPTIONS = [null, 4, 3, 2, 1]

export function normalizeIncident(item, fallbackId) {
  const severity = Number(item.severity ?? 0)
  const agencyName = item.agency || item.agency_name || 'Иные ведомства Омской области'
  const municipality = item.municipality || item.district || ''
  const settlement = item.settlement || item.населенный_пункт || ''
  const street = item.street || item.улица || ''
  const house = item.house || item.дом || ''
  const hasAddress = Boolean(item.has_address ?? street)
  const address = item.address
    || [street, house && `д. ${house}`, settlement || municipality].filter(Boolean).join(', ')
    || municipality

  return {
    id: String(item.id ?? fallbackId),
    text: cleanAppealText(item.text),
    severity,
    label: item.label || SEVERITY_LABELS[severity] || '',
    district: municipality,
    municipality,
    settlement,
    street,
    house,
    address,
    hasAddress,
    lat: item.lat ?? null,
    lng: item.lng ?? null,
    group: cleanAppealText(item.group || ''),
    topic: cleanAppealText(item.topic || ''),
    category: item.topic || item.group || '',
    agency: {
      name: agencyName,
      email: item.agency_email || '',
    },
    municipality_admin: item.municipality_admin || null,
    municipality_email: item.municipality_email || null,
    municipality_phone: item.municipality_phone || null,
    isLive: Boolean(item.isLive),
    created_at: item.created_at || null,
    outcome: item.outcome || item.итог || null,
    manually_resolved: Boolean(item.manually_resolved),
    closed_at: item.closed_at || null,
  }
}

const CLOSED_EMPTY = new Set(['nan', 'none', '<na>'])
const RESOLVED_OUTCOMES = new Set(['решено', 'разъяснено', 'перенаправлено'])

/** Совпадает с backend app.resolved: итог AD или ручная отметка. */
export function isIncidentResolved(item) {
  if (item?.manually_resolved) return true
  const text = String(item?.outcome ?? item?.итог ?? '').trim().toLowerCase()
  if (!text || CLOSED_EMPTY.has(text)) return false
  if (RESOLVED_OUTCOMES.has(text)) return true
  return [...RESOLVED_OUTCOMES].some((kw) => text.startsWith(kw))
}

function hashUnit(seed, slot) {
  let h = 2166136261 ^ slot
  const str = String(seed)
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0) / 4294967296
}

function spreadInBounds(bounds, seed) {
  const pad = 0.06
  const latMin = bounds.south + (bounds.north - bounds.south) * pad
  const latMax = bounds.north - (bounds.north - bounds.south) * pad
  const lngMin = bounds.west + (bounds.east - bounds.west) * pad
  const lngMax = bounds.east - (bounds.east - bounds.west) * pad
  return [
    latMin + (latMax - latMin) * hashUnit(seed, 1),
    lngMin + (lngMax - lngMin) * hashUnit(seed, 2),
  ]
}

export function resolveIncidentCoords(incident, approximate = false) {
  if (incident.lat != null && incident.lng != null) {
    return [Number(incident.lat), Number(incident.lng)]
  }
  const municipality = incident.municipality || incident.district
  if (!approximate) {
    return getMunicipalityCoords(municipality)
  }
  const seed = `${incident.id}|${incident.street || ''}|${incident.house || ''}|${incident.settlement || ''}`
  const bounds = getMunicipalityBounds(municipality)
  if (bounds) return spreadInBounds(bounds, seed)
  const base = getMunicipalityCoords(municipality)
  const spread = 0.04
  return [
    base[0] + (hashUnit(seed, 1) - 0.5) * spread,
    base[1] + (hashUnit(seed, 2) - 0.5) * spread,
  ]
}

export const CITIZEN_ROW_PREFIX = 'citizen-'
const CITIZEN_ROW_RE = /^citizen-[a-f0-9]{12}$/

/** Нормализует row_id гражданского обращения (убирает суффикс uid из live-потока). */
export function citizenRowId(id) {
  const raw = String(id || '').trim()
  if (!raw.startsWith(CITIZEN_ROW_PREFIX)) return raw
  const match = raw.match(/^(citizen-[a-f0-9]{12})/)
  return match ? match[1] : raw
}

export function isCitizenRowId(id) {
  return CITIZEN_ROW_RE.test(citizenRowId(id))
}

export function liveEventToIncident(event) {
  const rowId = citizenRowId(event.id || event.uid)
  return normalizeIncident(
    {
      ...event,
      id: rowId,
      isLive: true,
    },
    rowId,
  )
}

export function incidentDisplayMeta(incident) {
  const severity = incident.severity ?? 2
  const color = SEVERITY_COLORS[severity] || '#f97316'
  const icon = severity >= 4 ? '🚨' : severity >= 3 ? '⚠️' : '📋'
  return {
    label: incident.topic || incident.category || incident.label || 'Обращение гражданина',
    color,
    icon,
    radius: severity >= 4 ? 400 : severity >= 3 ? 280 : 200,
  }
}
