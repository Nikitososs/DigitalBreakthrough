import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { normalizeIncident } from '../utils/incidentModel'
import { mergeAgencyPackages, normalizePackagesFromApi } from '../utils/incidentPackages'
import {
  clearPackagesCache,
  readPackagesCache,
  writePackagesCache,
} from '../utils/incidentPackagesCache'

export function useTaskIncidents(taskId, options = {}) {
  const {
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
    limit = 80,
    offset = 0,
    geocode = false,
    geocodeCacheOnly = false,
    geocodeMaxFresh = null,
    enabled = true,
    pollMs = 0,
  } = options

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const reload = useCallback(() => setRefreshToken((t) => t + 1), [])

  useEffect(() => {
    if (!enabled || !taskId) {
      setItems([])
      setTotal(0)
      setError('')
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')

    api
      .getTaskIncidents(taskId, {
        severityMin,
        severityMax,
        municipality,
        group,
        topic,
        agency,
        hasAddress,
        geocodedOnly,
        search,
        createdFrom,
        createdTo,
        resolved,
        limit,
        offset,
        geocode,
        geocodeCacheOnly,
        geocodeMaxFresh,
      })
      .then((data) => {
        if (cancelled) return
        const normalized = (data.items || []).map((row, i) => normalizeIncident(row, `api-${offset + i}`))
        setItems(normalized)
        setTotal(data.total ?? normalized.length)
      })
      .catch((err) => {
        if (cancelled) return
        setItems([])
        setTotal(0)
        setError(err.message || 'Не удалось загрузить обращения')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [
    taskId,
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    geocodedOnly,
    search,
    createdFrom,
    createdTo,
    resolved,
    limit,
    offset,
    geocode,
    geocodeCacheOnly,
    geocodeMaxFresh,
    enabled,
    refreshToken,
  ])

  useEffect(() => {
    if (!enabled || !taskId || !pollMs) return undefined
    const timer = setInterval(reload, pollMs)
    return () => clearInterval(timer)
  }, [enabled, taskId, pollMs, reload])

  return { items, total, loading, error, reload }
}

/** Постраничная подгрузка при скролле (offset накапливается). */
export function useTaskIncidentsInfinite(taskId, options = {}) {
  const {
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
    limit = 80,
    geocode = false,
    enabled = true,
  } = options

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const filterKey = JSON.stringify({
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    search,
    createdFrom,
    createdTo,
    resolved,
    geocode,
    refreshToken,
  })

  useEffect(() => {
    setItems([])
    setOffset(0)
    setTotal(0)
    setError('')
  }, [taskId, filterKey, enabled])

  useEffect(() => {
    if (!enabled || !taskId) {
      setLoading(false)
      setLoadingMore(false)
      return undefined
    }

    let cancelled = false
    const isAppend = offset > 0
    if (isAppend) setLoadingMore(true)
    else setLoading(true)
    setError('')

    api
      .getTaskIncidents(taskId, {
        severityMin,
        severityMax,
        municipality,
        group,
        topic,
        agency,
        hasAddress,
        search,
        createdFrom,
        createdTo,
        resolved,
        limit,
        offset,
        geocode,
      })
      .then((data) => {
        if (cancelled) return
        const normalized = (data.items || []).map((row, i) => normalizeIncident(row, `api-${offset + i}`))
        setTotal(data.total ?? normalized.length)
        setItems((prev) => {
          if (offset === 0) return normalized
          const seen = new Set(prev.map((row) => row.id))
          return [...prev, ...normalized.filter((row) => !seen.has(row.id))]
        })
      })
      .catch((err) => {
        if (cancelled) return
        if (offset === 0) {
          setItems([])
          setTotal(0)
        }
        setError(err.message || 'Не удалось загрузить обращения')
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
          setLoadingMore(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [
    taskId,
    filterKey,
    offset,
    limit,
    enabled,
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    search,
    createdFrom,
    createdTo,
    resolved,
    geocode,
  ])

  const hasMore = enabled && Boolean(taskId) && items.length < total

  const loadMore = useCallback(() => {
    if (loading || loadingMore || !hasMore) return
    setOffset(items.length)
  }, [loading, loadingMore, hasMore, items.length])

  const reload = useCallback(() => setRefreshToken((t) => t + 1), [])

  return { items, total, loading, loadingMore, error, hasMore, loadMore, reload }
}

const PACKAGE_PAGE_SIZE = 80
const BACKGROUND_PREFETCH_MS = 400

/** Пакеты обращений — быстрая первая страница, фоновая догрузка, кеш sessionStorage. */
export function useTaskIncidentPackagesInfinite(taskId, options = {}) {
  const {
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
    limit = PACKAGE_PAGE_SIZE,
    enabled = true,
    bootstrap = true,
    backgroundPrefetch = true,
  } = options

  const [packagePages, setPackagePages] = useState([])
  const [total, setTotal] = useState(0)
  const [loaded, setLoaded] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [backgroundLoading, setBackgroundLoading] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)
  const [fetchNonce, setFetchNonce] = useState(0)
  const bootstrapRef = useRef(bootstrap)
  const loadedRef = useRef(loaded)
  const totalRef = useRef(total)
  const packagePagesRef = useRef(packagePages)

  useEffect(() => {
    bootstrapRef.current = bootstrap
  }, [bootstrap])

  useEffect(() => {
    loadedRef.current = loaded
    totalRef.current = total
    packagePagesRef.current = packagePages
  }, [loaded, total, packagePages])

  const filtersKey = JSON.stringify({
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    search,
    createdFrom,
    createdTo,
    resolved,
    limit,
  })

  const reload = useCallback(() => {
    clearPackagesCache(taskId, filtersKey)
    setRefreshToken((t) => t + 1)
  }, [taskId, filtersKey])

  const resetKey = `${taskId}|${filtersKey}|${refreshToken}`

  useEffect(() => {
    if (!taskId || !enabled) return

    const cached = readPackagesCache(taskId, filtersKey)
    if (cached?.packagePages?.length) {
      setPackagePages(cached.packagePages)
      setTotal(cached.total ?? 0)
      setLoaded(cached.loaded ?? 0)
      setError('')
      if ((cached.loaded ?? 0) < (cached.total ?? 0)) {
        setFetchNonce((n) => n + 1)
      }
      return
    }

    setPackagePages([])
    setTotal(0)
    setLoaded(0)
    setError('')
    setFetchNonce(0)
  }, [resetKey, enabled, taskId, filtersKey])

  useEffect(() => {
    if (!taskId || !enabled || !bootstrap) return
    if (packagePages.length > 0 || fetchNonce > 0) return
    setFetchNonce(1)
  }, [taskId, enabled, bootstrap, packagePages.length, fetchNonce])

  const persistCache = useCallback(
    (pages, nextTotal, nextLoaded) => {
      if (!taskId) return
      writePackagesCache(taskId, filtersKey, {
        packagePages: pages,
        total: nextTotal,
        loaded: nextLoaded,
      })
    },
    [taskId, filtersKey],
  )

  useEffect(() => {
    if (!enabled || !taskId || fetchNonce === 0) {
      return undefined
    }

    if (loadedRef.current >= totalRef.current && totalRef.current > 0) {
      return undefined
    }

    const requestOffset = loadedRef.current
    const isInitial = requestOffset === 0 && packagePagesRef.current.length === 0
    if (isInitial && !bootstrapRef.current) {
      return undefined
    }

    let cancelled = false
    const isAppend = requestOffset > 0
    const inBackground = isAppend && !bootstrapRef.current

    if (isAppend) {
      if (inBackground) setBackgroundLoading(true)
      else setLoadingMore(true)
    } else {
      setLoading(true)
    }
    setError('')

    api
      .getTaskIncidentPackages(taskId, {
        severityMin,
        severityMax,
        municipality,
        group,
        topic,
        agency,
        hasAddress,
        search,
        createdFrom,
        createdTo,
        resolved,
        limit,
        offset: requestOffset,
      })
      .then((data) => {
        if (cancelled) return
        const incoming = data.packages || []
        const pageLoaded = data.loaded ?? 0
        const nextTotal = data.total ?? 0
        const nextLoaded = requestOffset === 0 ? pageLoaded : requestOffset + pageLoaded
        setTotal(nextTotal)
        setLoaded(nextLoaded)
        setPackagePages((prev) => {
          const nextPages = requestOffset === 0 ? [incoming] : [...prev, incoming]
          persistCache(nextPages, nextTotal, nextLoaded)
          return nextPages
        })
      })
      .catch((err) => {
        if (cancelled) return
        if (requestOffset === 0) {
          setPackagePages([])
          setTotal(0)
          setLoaded(0)
        }
        setError(err.message || 'Не удалось загрузить обращения')
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
          setLoadingMore(false)
          setBackgroundLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [
    fetchNonce,
    resetKey,
    enabled,
    limit,
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    search,
    createdFrom,
    createdTo,
    resolved,
    persistCache,
  ])

  const packages = useMemo(() => {
    let merged = []
    for (const page of packagePages) {
      merged = mergeAgencyPackages(merged, normalizePackagesFromApi(page, normalizeIncident))
    }
    return merged
  }, [packagePages])

  const hasMore = enabled && Boolean(taskId) && loaded < total

  const loadMore = useCallback(() => {
    if (loading || loadingMore || backgroundLoading || !hasMore) return
    setFetchNonce((n) => n + 1)
  }, [loading, loadingMore, backgroundLoading, hasMore])

  useEffect(() => {
    if (!backgroundPrefetch || !enabled || !taskId) return undefined
    if (loading || loadingMore || backgroundLoading || !hasMore) return undefined
    if (packagePages.length === 0) return undefined

    const timer = setTimeout(() => setFetchNonce((n) => n + 1), BACKGROUND_PREFETCH_MS)
    return () => clearTimeout(timer)
  }, [
    backgroundPrefetch,
    enabled,
    taskId,
    loading,
    loadingMore,
    backgroundLoading,
    hasMore,
    loaded,
    packagePages.length,
  ])

  return {
    packages,
    total,
    loaded,
    loading,
    loadingMore,
    backgroundLoading,
    error,
    hasMore,
    loadMore,
    reload,
  }
}

/** @deprecated используйте useTaskIncidentPackagesInfinite */
export function useTaskIncidentPackages(taskId, options = {}) {
  const {
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
    enabled = true,
  } = options

  const [packages, setPackages] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const reload = useCallback(() => setRefreshToken((t) => t + 1), [])

  const filterKey = JSON.stringify({
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    hasAddress,
    search,
    createdFrom,
    createdTo,
    resolved,
    refreshToken,
  })

  useEffect(() => {
    if (!enabled || !taskId) {
      setPackages([])
      setTotal(0)
      setError('')
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')

    api
      .getTaskIncidentPackages(taskId, {
        severityMin,
        severityMax,
        municipality,
        group,
        topic,
        agency,
        hasAddress,
        search,
        createdFrom,
        createdTo,
        resolved,
      })
      .then((data) => {
        if (cancelled) return
        setPackages(data.packages || [])
        setTotal(data.total ?? 0)
      })
      .catch((err) => {
        if (cancelled) return
        setPackages([])
        setTotal(0)
        setError(err.message || 'Не удалось загрузить обращения')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [taskId, filterKey, enabled, severityMin, severityMax, municipality, group, topic, agency, hasAddress, search, createdFrom, createdTo, resolved])

  return { packages, total, loading, error, reload }
}

/** Маркеры карты только для видимой области (bbox + zoom). */
export function useViewportMapMarkers(taskId, viewport, options = {}) {
  const {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    topic = null,
    agency = null,
    createdFrom = null,
    createdTo = null,
    resolved = null,
    enabled = true,
    debounceMs = 350,
  } = options

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const reload = useCallback(() => setRefreshToken((t) => t + 1), [])

  const viewportKey = viewport
    ? [
        viewport.min_lat?.toFixed(3),
        viewport.max_lat?.toFixed(3),
        viewport.min_lng?.toFixed(3),
        viewport.max_lng?.toFixed(3),
        viewport.zoom,
      ].join('|')
    : ''

  useEffect(() => {
    if (!enabled || !taskId || !viewport) {
      setItems([])
      setTotal(0)
      setError('')
      setLoading(false)
      return undefined
    }

    let cancelled = false
    const timer = setTimeout(() => {
      setLoading(true)
      setError('')

      api
        .getTaskMapMarkers(taskId, {
          severityMin,
          severityMax,
          municipality,
          group,
          topic,
          agency,
          createdFrom,
          createdTo,
          resolved,
          minLat: viewport.min_lat,
          maxLat: viewport.max_lat,
          minLng: viewport.min_lng,
          maxLng: viewport.max_lng,
          zoom: viewport.zoom,
          limit: 5000,
          offset: 0,
        })
        .then((data) => {
          if (cancelled) return
          const normalized = (data.items || []).map((row, i) => normalizeIncident(row, `map-${i}`))
          setItems(normalized)
          setTotal(data.total ?? normalized.length)
        })
        .catch((err) => {
          if (cancelled) return
          setItems([])
          setTotal(0)
          setError(err.message || 'Не удалось загрузить метки карты')
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, debounceMs)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [
    taskId,
    viewportKey,
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    createdFrom,
    createdTo,
    resolved,
    enabled,
    debounceMs,
    refreshToken,
    viewport,
  ])

  return { items, total, loading, error, reload }
}

/** Все geocoded-метки за период (пагинация без bbox). Для экстренного режима с фиксированным окном дат. */
export function usePeriodMapMarkers(taskId, options = {}) {
  const {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    topic = null,
    agency = null,
    createdFrom = null,
    createdTo = null,
    resolved = null,
    enabled = true,
    chunkSize = 2000,
  } = options

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const reload = useCallback(() => setRefreshToken((t) => t + 1), [])

  const periodKey = `${createdFrom || ''}|${createdTo || ''}|${refreshToken}`

  useEffect(() => {
    if (!enabled || !taskId || !createdFrom || !createdTo) {
      setItems([])
      setTotal(0)
      setError('')
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')
    setItems([])
    setTotal(0)

    const baseParams = {
      severityMin,
      severityMax,
      municipality,
      group,
      topic,
      agency,
      createdFrom,
      createdTo,
      resolved,
      limit: chunkSize,
    }

    ;(async () => {
      try {
        const first = await api.getTaskMapMarkers(taskId, { ...baseParams, offset: 0 })
        if (cancelled) return
        const totalCount = first.total ?? (first.items || []).length
        let merged = (first.items || []).map((row, i) => normalizeIncident(row, `map-${i}`))

        if (totalCount > merged.length) {
          const offsets = []
          for (let off = chunkSize; off < totalCount; off += chunkSize) {
            offsets.push(off)
          }
          const pages = await Promise.all(
            offsets.map((offset) => api.getTaskMapMarkers(taskId, { ...baseParams, offset })),
          )
          if (cancelled) return
          for (const page of pages) {
            const base = merged.length
            const batch = (page.items || []).map((row, i) => normalizeIncident(row, `map-${base + i}`))
            const seen = new Set(merged.map((r) => r.id))
            merged = [...merged, ...batch.filter((r) => !seen.has(r.id))]
          }
        }

        if (!cancelled) {
          setItems(merged)
          setTotal(totalCount)
        }
      } catch (err) {
        if (!cancelled) {
          setItems([])
          setTotal(0)
          setError(err.message || 'Не удалось загрузить метки карты')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    taskId,
    periodKey,
    severityMin,
    severityMax,
    municipality,
    group,
    topic,
    agency,
    createdFrom,
    createdTo,
    resolved,
    enabled,
    chunkSize,
  ])

  return { items, total, loading, error, reload }
}

/** @deprecated Для экстренного режима — usePeriodMapMarkers. */
export function useTaskIncidentsGeocodedMap(taskId, options = {}) {
  return usePeriodMapMarkers(taskId, options)
}
