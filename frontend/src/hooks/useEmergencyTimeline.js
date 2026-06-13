import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import {
  TIMELINE_FETCH_DEBOUNCE_MS,
  parseDatasetDate,
  presetDays,
  sliderStepForWindow,
  snapOffsetDays,
  windowRange,
} from '../utils/emergencyTimeline'

/**
 * Скользящее окно (1/7/30/90 дн.). Слайдер с шагами; API-запросы — с debounce или сразу по отпусканию.
 */
export function useEmergencyTimeline(taskId, { enabled = true, initialPreset = '7d' } = {}) {
  const [datasetStart, setDatasetStart] = useState(null)
  const [datasetEnd, setDatasetEnd] = useState(null)
  const [preset, setPreset] = useState(initialPreset)
  const [offsetDays, setOffsetDays] = useState(0)
  const [fetchOffsetDays, setFetchOffsetDays] = useState(0)
  const [loadingMeta, setLoadingMeta] = useState(false)
  const [fetchPending, setFetchPending] = useState(false)
  const debounceRef = useRef(null)

  const windowDays = presetDays(preset)
  const sliderStep = sliderStepForWindow(windowDays)

  const displayRange = useMemo(
    () => windowRange(datasetStart, datasetEnd, windowDays, offsetDays),
    [datasetStart, datasetEnd, windowDays, offsetDays],
  )

  const fetchRange = useMemo(
    () => windowRange(datasetStart, datasetEnd, windowDays, fetchOffsetDays),
    [datasetStart, datasetEnd, windowDays, fetchOffsetDays],
  )

  const pendingOffsetRef = useRef(0)

  const flushFetch = useCallback((days) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    const max = windowRange(datasetStart, datasetEnd, windowDays, 0).maxOffsetDays
    const snapped = snapOffsetDays(Math.max(0, Math.min(days, max)), sliderStep)
    setFetchPending(false)
    setOffsetDays(snapped)
    setFetchOffsetDays(snapped)
    pendingOffsetRef.current = snapped
  }, [datasetStart, datasetEnd, windowDays, sliderStep])

  const scheduleFetch = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setFetchPending(true)
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null
      flushFetch(pendingOffsetRef.current)
    }, TIMELINE_FETCH_DEBOUNCE_MS)
  }, [flushFetch])

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  useEffect(() => {
    if (!enabled || !taskId) {
      setDatasetStart(null)
      setDatasetEnd(null)
      setOffsetDays(0)
      setFetchOffsetDays(0)
      return undefined
    }

    let cancelled = false
    setLoadingMeta(true)

    api
      .getDashboard(taskId)
      .then((data) => {
        if (cancelled) return
        const start = parseDatasetDate(data?.start_date)
        const end = parseDatasetDate(data?.end_date)
        setDatasetStart(start)
        setDatasetEnd(end)
        if (start && end) {
          const days = presetDays(preset)
          const { maxOffsetDays } = windowRange(start, end, days, 0)
          setOffsetDays(maxOffsetDays)
          setFetchOffsetDays(maxOffsetDays)
        } else {
          setOffsetDays(0)
          setFetchOffsetDays(0)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDatasetStart(null)
          setDatasetEnd(null)
          setOffsetDays(0)
          setFetchOffsetDays(0)
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingMeta(false)
      })

    return () => {
      cancelled = true
    }
  }, [taskId, enabled])

  const setWindowOffset = useCallback((days) => {
    const max = displayRange.maxOffsetDays
    const clamped = Math.max(0, Math.min(days, max))
    pendingOffsetRef.current = clamped
    setOffsetDays(clamped)
    scheduleFetch()
  }, [displayRange.maxOffsetDays, scheduleFetch])

  const commitWindowOffset = useCallback(() => {
    flushFetch(pendingOffsetRef.current)
  }, [flushFetch])

  const jumpToLatest = useCallback(() => {
    const max = displayRange.maxOffsetDays
    pendingOffsetRef.current = max
    flushFetch(max)
  }, [displayRange.maxOffsetDays, flushFetch])

  const selectPreset = useCallback((presetId) => {
    setPreset(presetId)
    if (datasetStart && datasetEnd) {
      const days = presetDays(presetId)
      const step = sliderStepForWindow(days)
      const { maxOffsetDays } = windowRange(datasetStart, datasetEnd, days, 0)
      pendingOffsetRef.current = maxOffsetDays
      flushFetch(maxOffsetDays)
    }
  }, [datasetStart, datasetEnd, flushFetch])

  useEffect(() => {
    if (!datasetStart || !datasetEnd) return
    const max = windowRange(datasetStart, datasetEnd, windowDays, 0).maxOffsetDays
    setOffsetDays((prev) => {
      const clamped = Math.min(prev, max)
      return snapOffsetDays(clamped, sliderStep)
    })
    setFetchOffsetDays((prev) => Math.min(prev, max))
  }, [windowDays, datasetStart, datasetEnd, sliderStep])

  return {
    preset,
    windowDays,
    sliderStep,
    datasetStart,
    datasetEnd,
    offsetDays: displayRange.offsetDays,
    maxOffsetDays: displayRange.maxOffsetDays,
    createdFrom: displayRange.createdFrom,
    createdTo: displayRange.createdTo,
    fetchCreatedFrom: fetchRange.createdFrom,
    fetchCreatedTo: fetchRange.createdTo,
    fetchPending,
    loadingMeta,
    setWindowOffset,
    commitWindowOffset,
    jumpToLatest,
    selectPreset,
    ready: Boolean(fetchRange.createdFrom && fetchRange.createdTo),
  }
}
