/** Нормализация даты обращения и проверка диапазона (ISO, DD.MM.YYYY, …). */

export function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export function daysAgoIso(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

export function parseIncidentDate(value) {
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

export function incidentInDateRange(createdAt, from, to) {
  if (!from && !to) return true
  const key = parseIncidentDate(createdAt)
  if (!key) return false
  if (from && key < from) return false
  if (to && key > to) return false
  return true
}

export const DATE_PRESETS = [
  { id: 'all', label: 'Все' },
  { id: '1d', label: '1 дн.' },
  { id: '7d', label: '7 дн.' },
  { id: '30d', label: '30 дн.' },
  { id: '90d', label: '90 дн.' },
  { id: 'custom', label: 'Период' },
]

export function presetToRange(presetId) {
  if (presetId === 'all') return { from: '', to: '' }
  if (presetId === '1d') return { from: daysAgoIso(1), to: todayIso() }
  if (presetId === '7d') return { from: daysAgoIso(7), to: todayIso() }
  if (presetId === '30d') return { from: daysAgoIso(30), to: todayIso() }
  if (presetId === '90d') return { from: daysAgoIso(90), to: todayIso() }
  return null
}
