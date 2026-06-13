import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

const POLL_MS = 3000
const MAX_VISIBLE = 8

function tsMs(value) {
  if (!value) return 0
  const ms = Date.parse(value)
  return Number.isFinite(ms) ? ms : 0
}

/**
 * Live-поток реальных обращений граждан (poll /live/recent).
 */
export function useLiveFeed(enabled, { taskId = null } = {}) {
  const sinceRef = useRef(new Date().toISOString())
  const seenRef = useRef(new Set())
  const timerRef = useRef(null)
  const taskIdRef = useRef(taskId)
  taskIdRef.current = taskId

  const [events, setEvents] = useState([])
  const [received, setReceived] = useState(0)
  const [active, setActive] = useState(false)
  const [error, setError] = useState(null)

  const canPoll = Boolean(enabled)

  const pushEvent = useCallback((item) => {
    const key = item.id || item.uid
    if (key && seenRef.current.has(key)) return
    if (key) seenRef.current.add(key)
    const event = {
      ...item,
      uid: `${item.id}-${Date.now()}`,
      at: item.created_at || new Date().toISOString(),
    }
    setEvents((prev) => [event, ...prev].slice(0, MAX_VISIBLE))
    setReceived((n) => n + 1)
  }, [])

  const poll = useCallback(async () => {
    try {
      const data = await api.getLiveRecent(taskIdRef.current || null, sinceRef.current)
      const items = [...(data.items || [])].reverse()
      for (const item of items) {
        pushEvent(item)
        if (tsMs(item.created_at) > tsMs(sinceRef.current)) {
          sinceRef.current = item.created_at
        }
      }
      setError(null)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить live-поток')
    }
  }, [pushEvent])

  useEffect(() => {
    if (!canPoll) {
      setActive(false)
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = null
      return undefined
    }

    sinceRef.current = new Date().toISOString()
    seenRef.current = new Set()
    setEvents([])
    setReceived(0)
    setError(null)
    setActive(true)

    poll()
    timerRef.current = setInterval(poll, POLL_MS)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [canPoll, taskId, poll])

  const dismiss = useCallback((uid) => {
    setEvents((prev) => prev.filter((e) => e.uid !== uid))
  }, [])

  const reset = useCallback(() => {
    sinceRef.current = new Date().toISOString()
    seenRef.current = new Set()
    setEvents([])
    setReceived(0)
    setError(null)
    if (canPoll) poll()
  }, [canPoll, poll])

  const ingest = useCallback((item) => {
    pushEvent(item)
    if (tsMs(item.created_at) >= tsMs(sinceRef.current)) {
      sinceRef.current = item.created_at
    }
  }, [pushEvent])

  return {
    events,
    received,
    active,
    error,
    source: 'citizen',
    total: null,
    sourceFile: taskId ? `task:${taskId}` : 'postgres:live',
    dismiss,
    reset,
    ingest,
    canPoll,
  }
}
