import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import liveDemoFeed from '../data/liveDemoFeed.json'

const ITEMS = liveDemoFeed?.items || []
const DEFAULT_INTERVAL_MS = 3000

function cleanDemoText(value) {
  let text = String(value || '').trim()
  if (text.startsWith("'") && text.endsWith("'")) text = text.slice(1, -1).trim()
  if (text.startsWith('"') && text.endsWith('"')) text = text.slice(1, -1).trim()
  return text
}

function itemToPayload(item) {
  return {
    text: cleanDemoText(item.text),
    group: item.group || '',
    topic: item.topic || '',
    municipality: item.municipality || 'Омск г.о.',
    settlement: item.settlement || '',
    street: item.street || '',
    house: item.house || '',
  }
}

/** Циклически отправляет обращения из liveDemoFeed.json на POST /api/v1/complaints. */
export function useLiveDemoPlayback({ enabled = true, intervalMs = DEFAULT_INTERVAL_MS, onSubmitted } = {}) {
  const indexRef = useRef(0)
  const activeRef = useRef(false)
  const timerRef = useRef(null)
  const sendingRef = useRef(false)
  const onSubmittedRef = useRef(onSubmitted)
  onSubmittedRef.current = onSubmitted

  const [active, setActive] = useState(false)
  const [sent, setSent] = useState(0)
  const [error, setError] = useState(null)

  const canRun = enabled && ITEMS.length > 0

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const runCycleRef = useRef(null)

  runCycleRef.current = async () => {
    if (!activeRef.current || !canRun || sendingRef.current) return

    const item = ITEMS[indexRef.current % ITEMS.length]
    indexRef.current += 1
    const payload = itemToPayload(item)

    if (payload.text.length < 10) {
      timerRef.current = setTimeout(() => runCycleRef.current?.(), intervalMs)
      return
    }

    sendingRef.current = true
    try {
      const res = await api.submitComplaintLive(payload)
      setSent((n) => n + 1)
      setError(null)
      onSubmittedRef.current?.(res?.incident)
    } catch (err) {
      setError(err.message || 'Не удалось отправить demo-обращение')
    } finally {
      sendingRef.current = false
    }

    if (activeRef.current && canRun) {
      timerRef.current = setTimeout(() => runCycleRef.current?.(), intervalMs)
    }
  }

  const stop = useCallback(() => {
    activeRef.current = false
    setActive(false)
    clearTimer()
  }, [clearTimer])

  const start = useCallback(() => {
    if (!canRun) return
    activeRef.current = true
    setActive(true)
    setError(null)
  }, [canRun])

  const toggle = useCallback(() => {
    if (activeRef.current) stop()
    else start()
  }, [start, stop])

  useEffect(() => {
    activeRef.current = active
    if (!active || !canRun) {
      clearTimer()
      return undefined
    }

    runCycleRef.current?.()

    return clearTimer
  }, [active, canRun, intervalMs, clearTimer])

  useEffect(() => () => clearTimer(), [clearTimer])

  return {
    active,
    sent,
    total: ITEMS.length,
    error,
    canRun,
    sourceFile: liveDemoFeed?.source_file || 'liveDemoFeed.json',
    start,
    stop,
    toggle,
  }
}
