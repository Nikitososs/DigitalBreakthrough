import { clearAuth, getToken } from '../auth/storage'

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

let onUnauthorized = null

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

function authHeaders(extra = {}) {
  const headers = { ...extra }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function request(path, options = {}) {
  const headers = authHeaders(options.headers || {})
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401 && getToken()) {
    clearAuth()
    onUnauthorized?.()
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? JSON.stringify(body)
    } catch {
      try {
        detail = await res.text()
      } catch {
        /* ignore */
      }
    }
    const err = new Error(detail || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res.text()
}

async function authFetch(path, options = {}) {
  const headers = authHeaders(options.headers || {})
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401 && getToken()) {
    clearAuth()
    onUnauthorized?.()
  }
  return res
}

export const api = {
  login(username, password) {
    return request('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
  },

  me() {
    return request('/api/v1/auth/me')
  },

  myDashboardRoles() {
    return request('/api/v1/auth/roles')
  },

  listUsers() {
    return request('/api/v1/users')
  },

  createUser({ username, password, role }) {
    return request('/api/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role }),
    })
  },

  updateUser(userId, patch) {
    return request(`/api/v1/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
  },

  deactivateUser(userId) {
    return request(`/api/v1/users/${userId}`, { method: 'DELETE' })
  },

  health() {
    return request('/api/v1/health')
  },

  classify(items) {
    return request('/api/v1/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    })
  },

  getLiveRecent(taskId = null, since = null, limit = 20) {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (taskId) qs.set('task_id', taskId)
    if (since) qs.set('since', since)
    return request(`/api/v1/live/recent?${qs}`)
  },

  submitComplaint(taskId, payload) {
    return request(`/api/v1/tasks/${encodeURIComponent(taskId)}/complaints`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  submitComplaintLive(payload) {
    return request('/api/v1/complaints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  getTaskIncidents(taskId, {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    topic = null,
    agency = null,
    hasAddress = null,
    geocodedOnly = null,
    search = null,
    createdFrom = null,
    createdTo = null,
    resolved = null,
    limit = 300,
    offset = 0,
    geocode = false,
    geocodeCacheOnly = false,
    geocodeMaxFresh = null,
  } = {}) {
    const qs = new URLSearchParams({
      severity_min: String(severityMin),
      severity_max: String(severityMax),
      limit: String(limit),
      offset: String(offset),
    })
    if (municipality) qs.set('municipality', municipality)
    if (group) qs.set('group', group)
    if (topic) qs.set('topic', topic)
    if (agency) qs.set('agency', agency)
    if (hasAddress != null) qs.set('has_address', hasAddress ? 'true' : 'false')
    if (geocodedOnly != null) qs.set('geocoded_only', geocodedOnly ? 'true' : 'false')
    if (search) qs.set('search', search)
    if (createdFrom) qs.set('created_from', createdFrom)
    if (createdTo) qs.set('created_to', createdTo)
    if (resolved != null) qs.set('resolved', resolved ? 'true' : 'false')
    if (geocode) qs.set('geocode', 'true')
    if (geocodeCacheOnly) qs.set('geocode_cache_only', 'true')
    if (geocodeMaxFresh != null) qs.set('geocode_max_fresh', String(geocodeMaxFresh))
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/incidents?${qs}`)
  },

  getTaskIncidentPackages(taskId, {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    topic = null,
    agency = null,
    hasAddress = null,
    search = null,
    createdFrom = null,
    createdTo = null,
    resolved = null,
    limit = 100,
    offset = 0,
  } = {}) {
    const qs = new URLSearchParams({
      severity_min: String(severityMin),
      severity_max: String(severityMax),
      limit: String(limit),
      offset: String(offset),
    })
    if (municipality) qs.set('municipality', municipality)
    if (group) qs.set('group', group)
    if (topic) qs.set('topic', topic)
    if (agency) qs.set('agency', agency)
    if (hasAddress != null) qs.set('has_address', hasAddress ? 'true' : 'false')
    if (search) qs.set('search', search)
    if (createdFrom) qs.set('created_from', createdFrom)
    if (createdTo) qs.set('created_to', createdTo)
    if (resolved != null) qs.set('resolved', resolved ? 'true' : 'false')
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/incidents/packages?${qs}`)
  },

  getTaskMapMarkers(taskId, {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    topic = null,
    agency = null,
    createdFrom = null,
    createdTo = null,
    resolved = null,
    minLat = null,
    maxLat = null,
    minLng = null,
    maxLng = null,
    zoom = null,
    limit = 5000,
    offset = 0,
  } = {}) {
    const qs = new URLSearchParams({
      severity_min: String(severityMin),
      severity_max: String(severityMax),
      limit: String(limit),
      offset: String(offset),
    })
    if (municipality) qs.set('municipality', municipality)
    if (group) qs.set('group', group)
    if (topic) qs.set('topic', topic)
    if (agency) qs.set('agency', agency)
    if (createdFrom) qs.set('created_from', createdFrom)
    if (createdTo) qs.set('created_to', createdTo)
    if (resolved != null) qs.set('resolved', resolved ? 'true' : 'false')
    if (minLat != null) qs.set('min_lat', String(minLat))
    if (maxLat != null) qs.set('max_lat', String(maxLat))
    if (minLng != null) qs.set('min_lng', String(minLng))
    if (maxLng != null) qs.set('max_lng', String(maxLng))
    if (zoom != null) qs.set('zoom', String(zoom))
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/incidents/map-markers?${qs}`)
  },

  startGeocodeWarmup(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/geocode/warmup`, { method: 'POST' })
  },

  getGeocodeWarmupStatus(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/geocode/warmup`)
  },

  stopGeocodeWarmup(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/geocode/warmup`, { method: 'DELETE' })
  },

  deleteCitizenIncident(taskId, rowId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/incidents/${encodeURIComponent(rowId)}`, {
      method: 'DELETE',
    })
  },

  geocodeIncident(taskId, rowId, { cacheOnly = false } = {}) {
    const qs = cacheOnly ? '?cache_only=true' : ''
    return request(
      `/api/v1/jobs/${encodeURIComponent(taskId)}/incidents/${encodeURIComponent(rowId)}/geocode${qs}`,
      { method: 'POST' },
    )
  },

  getTaskIncidentFacets(taskId, { severityMin = 1, severityMax = 4, municipality = null, group = null, resolved = null } = {}) {
    const qs = new URLSearchParams({
      severity_min: String(severityMin),
      severity_max: String(severityMax),
    })
    if (municipality) qs.set('municipality', municipality)
    if (group) qs.set('group', group)
    if (resolved != null) qs.set('resolved', resolved ? 'true' : 'false')
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/incidents/facets?${qs}`)
  },

  getReferenceFacets({ severityMin = 0, severityMax = 4 } = {}) {
    const qs = new URLSearchParams({
      severity_min: String(severityMin),
      severity_max: String(severityMax),
    })
    return request(`/api/v1/reference/facets?${qs}`)
  },

  uploadDataset(file, params = {}) {
    const fd = new FormData()
    fd.append('file', file)
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, String(v))
    })
    const query = qs.toString()
    return request(`/api/v1/dataset/upload${query ? `?${query}` : ''}`, {
      method: 'POST',
      body: fd,
    })
  },

  getJob(taskId) {
    return request(`/api/v1/jobs/${taskId}`)
  },

  getDashboard(taskId = null) {
    const qs = taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''
    return request(`/api/v1/dashboard${qs}`)
  },

  getForecast(horizonWeeks = 4, options = {}) {
    const qs = new URLSearchParams({ horizon_weeks: String(horizonWeeks) })
    return request(`/api/v1/forecast?${qs}`, options)
  },

  generateForecastAiSummary(horizonWeeks = 4, { force = false } = {}) {
    const qs = new URLSearchParams({
      horizon_weeks: String(horizonWeeks),
      force: force ? 'true' : 'false',
    })
    return request(`/api/v1/forecast/ai-summary?${qs}`, { method: 'POST' })
  },

  getDistrictReport(taskId, districtId) {
    return request(
      `/api/v1/districts/${districtId}/report?task_id=${encodeURIComponent(taskId)}`,
    )
  },

  generateDistrictReport(taskId, districtId) {
    return request(`/api/v1/reports/generate?task_id=${encodeURIComponent(taskId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ district_id: districtId }),
    })
  },

  getGenerateStatus(genTaskId) {
    return request(`/api/v1/reports/generate/${genTaskId}`)
  },

  excelUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/excel`
  },

  excelTop10Url(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/excel/top10`
  },

  districtPdfUrl(taskId, districtId) {
    return `${BASE}/api/v1/districts/${districtId}/report.pdf?task_id=${encodeURIComponent(taskId)}`
  },

  parseContentDisposition(header) {
    if (!header) return 'zeroproblems_report.pdf'
    const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i)
    if (utf8?.[1]) {
      try {
        return decodeURIComponent(utf8[1])
      } catch {
        /* fall through */
      }
    }
    const ascii = header.match(/filename="([^"]+)"/i)
    return ascii?.[1] || 'zeroproblems_report.pdf'
  },

  async savePdfResponse(res) {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition'))
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  async downloadDistrictPdf(taskId, districtId) {
    const res = await authFetch(
      `/api/v1/districts/${districtId}/report.pdf?task_id=${encodeURIComponent(taskId)}`,
    )
    return api.savePdfResponse(res)
  },

  async downloadDistrictPdfFromData(reportData) {
    const res = await authFetch('/api/v1/reports/district/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reportData),
    })
    return api.savePdfResponse(res)
  },

  regionPdfUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/report.pdf`
  },

  async downloadRegionPdf(taskId) {
    const res = await authFetch(`/api/v1/jobs/${encodeURIComponent(taskId)}/report.pdf`)
    return api.savePdfResponse(res)
  },

  async downloadRegionPdfFromData(districts, executiveSummary = '') {
    const res = await authFetch('/api/v1/reports/region/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ districts, executive_summary: executiveSummary }),
    })
    return api.savePdfResponse(res)
  },

  async downloadExcel(taskId) {
    const res = await authFetch(`/api/v1/jobs/${encodeURIComponent(taskId)}/excel`)
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition')) || 'report.xlsx'
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  async downloadExcelTop10(taskId) {
    const res = await authFetch(`/api/v1/jobs/${encodeURIComponent(taskId)}/excel/top10`)
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch { /* ignore */ }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition')) || 'report_top10.xlsx'
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  departmentReportsZipUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments.zip`
  },

  departmentReportsDownloadUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments`
  },

  getDepartmentReportsPreview(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments/preview`)
  },

  startDepartmentReportsGenerate(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments/generate`, {
      method: 'POST',
    })
  },

  getDepartmentReportsStatus(genTaskId) {
    return request(`/api/v1/reports/departments/${encodeURIComponent(genTaskId)}`)
  },

  departmentReportsByGenUrl(genTaskId) {
    return `${BASE}/api/v1/reports/departments/${encodeURIComponent(genTaskId)}/download`
  },

  async saveZipResponse(res) {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition')) || 'zeroproblems_vedomstva.zip'
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  async downloadDepartmentReportsZip(taskId) {
    let res = await authFetch(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments.zip`)
    if (res.status === 404) {
      res = await authFetch(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments`)
    }
    return api.saveZipResponse(res)
  },

  async downloadDepartmentReportsByGenId(genTaskId) {
    const res = await authFetch(`/api/v1/reports/departments/${encodeURIComponent(genTaskId)}/download`)
    return api.saveZipResponse(res)
  },

  composeEmail(incidents, agencyName, agencyEmail, bundleLabel = null) {
    return request('/api/v1/operator/compose-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incidents,
        agency_name: agencyName,
        agency_email: agencyEmail,
        bundle_label: bundleLabel || undefined,
      }),
    })
  },

  getArchiveJobs() {
    return request('/api/v1/archive/jobs')
  },

  importArchiveJob(taskId) {
    return request(`/api/v1/archive/jobs/${encodeURIComponent(taskId)}/import`, {
      method: 'POST',
    })
  },

  deleteArchiveJob(taskId) {
    return request(`/api/v1/archive/jobs/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    })
  },

  deleteCachedJobs(taskIds) {
    return request('/api/v1/archive/cache/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_ids: taskIds }),
    })
  },

}
