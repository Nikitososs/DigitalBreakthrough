/** Скользящее окно по умолчанию (дней, включительно). */
export const EMERGENCY_WINDOW_DAYS = 7

export const EMERGENCY_PRESETS = [
  { id: '1d', label: '1 дн.', days: 1 },
  { id: '7d', label: '7 дн.', days: 7 },
  { id: '30d', label: '30 дн.', days: 30 },
  { id: '90d', label: '90 дн.', days: 90 },
]

export const TIMELINE_FETCH_DEBOUNCE_MS = 1000

export function presetDays(presetId) {
  return EMERGENCY_PRESETS.find((p) => p.id === presetId)?.days ?? EMERGENCY_WINDOW_DAYS
}

/** Шаг слайдера (дней) — крупнее окно → реже позиции. */
export function sliderStepForWindow(windowDays) {
  if (windowDays <= 1) return 1
  if (windowDays <= 7) return 1
  if (windowDays <= 30) return 3
  return 7
}

export function snapOffsetDays(days, step) {
  if (step <= 1) return days
  return Math.round(days / step) * step
}

export function parseDatasetDate(value) {
  if (value == null || value === '') return null
  const s = String(value).trim()
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10)
  const dmy = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/)
  if (dmy) {
    return `${dmy[3]}-${dmy[2].padStart(2, '0')}-${dmy[1].padStart(2, '0')}`
  }
  const parsed = new Date(s)
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10)
  return null
}

export function addDaysIso(iso, days) {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function daysBetweenInclusive(startIso, endIso) {
  const a = new Date(`${startIso}T12:00:00`)
  const b = new Date(`${endIso}T12:00:00`)
  return Math.max(0, Math.round((b - a) / 86400000) + 1)
}

/** Смещение начала окна (дней от datasetStart) → created_from / created_to. */
export function windowRange(datasetStart, datasetEnd, windowDays, offsetDays) {
  if (!datasetStart || !datasetEnd) {
    return { createdFrom: null, createdTo: null, offsetDays: 0, maxOffsetDays: 0 }
  }
  const span = daysBetweenInclusive(datasetStart, datasetEnd)
  const maxOffsetDays = Math.max(0, span - windowDays)
  const clamped = Math.min(Math.max(0, offsetDays), maxOffsetDays)
  const createdFrom = addDaysIso(datasetStart, clamped)
  let createdTo = addDaysIso(createdFrom, windowDays - 1)
  if (createdTo > datasetEnd) createdTo = datasetEnd
  return { createdFrom, createdTo, offsetDays: clamped, maxOffsetDays }
}

export function formatPeriodRu(from, to) {
  if (!from || !to) return '—'
  const fmt = (iso) => {
    const [y, m, d] = iso.split('-')
    return `${d}.${m}.${y}`
  }
  return `${fmt(from)} — ${fmt(to)}`
}
