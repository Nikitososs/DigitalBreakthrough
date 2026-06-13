const MEMORY = new Map()
const SESSION_PREFIX = 'omsk-pulse:pkg:'
const MAX_AGE_MS = 30 * 60 * 1000

export function packagesCacheKey(taskId, filtersKey) {
  return `${taskId || ''}::${filtersKey || ''}`
}

export function readPackagesCache(taskId, filtersKey) {
  const key = packagesCacheKey(taskId, filtersKey)
  const mem = MEMORY.get(key)
  if (mem && Date.now() - mem.fetchedAt < MAX_AGE_MS) return mem

  try {
    const raw = sessionStorage.getItem(SESSION_PREFIX + key)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.fetchedAt || Date.now() - parsed.fetchedAt > MAX_AGE_MS) {
      sessionStorage.removeItem(SESSION_PREFIX + key)
      return null
    }
    MEMORY.set(key, parsed)
    return parsed
  } catch {
    return null
  }
}

export function writePackagesCache(taskId, filtersKey, snapshot) {
  const key = packagesCacheKey(taskId, filtersKey)
  const payload = { ...snapshot, fetchedAt: Date.now() }
  MEMORY.set(key, payload)
  try {
    sessionStorage.setItem(SESSION_PREFIX + key, JSON.stringify(payload))
  } catch {
    // sessionStorage переполнен — остаётся in-memory кеш
  }
}

export function clearPackagesCache(taskId, filtersKey) {
  const key = packagesCacheKey(taskId, filtersKey)
  MEMORY.delete(key)
  try {
    sessionStorage.removeItem(SESSION_PREFIX + key)
  } catch {
    /* ignore */
  }
}
