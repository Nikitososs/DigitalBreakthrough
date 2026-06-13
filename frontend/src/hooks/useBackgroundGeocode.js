import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'

/** Опрашивает статус фонового прогрева геокодов. autoStart=false — только по кнопке. */
export function useBackgroundGeocode(taskId, { enabled = true, autoStart = true, pollMs = 6000 } = {}) {
  const [status, setStatus] = useState(null)

  const refresh = useCallback(() => {
    if (!taskId) return Promise.resolve()
    return api.getGeocodeWarmupStatus(taskId).then(setStatus).catch(() => {})
  }, [taskId])

  const startWarmup = useCallback(async () => {
    if (!taskId) return null
    const data = await api.startGeocodeWarmup(taskId)
    setStatus(data)
    return data
  }, [taskId])

  useEffect(() => {
    if (!enabled || !taskId) {
      setStatus(null)
      return undefined
    }

    let cancelled = false

    const boot = async () => {
      if (autoStart) {
        try {
          const data = await api.startGeocodeWarmup(taskId)
          if (!cancelled) setStatus(data)
        } catch {
          if (!cancelled) await refresh()
        }
      } else {
        await refresh()
      }
    }
    boot()

    const timer = setInterval(() => {
      refresh()
    }, pollMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [taskId, enabled, autoStart, pollMs, refresh])

  return { status, startWarmup, refresh }
}
