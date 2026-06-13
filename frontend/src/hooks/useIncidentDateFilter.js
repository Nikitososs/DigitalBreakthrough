import { useCallback, useMemo, useState } from 'react'
import { presetToRange } from '../utils/incidentDateFilter'

export function useIncidentDateFilter(initialPreset = 'all') {
  const [preset, setPreset] = useState(initialPreset)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const handlePresetChange = useCallback((id) => {
    setPreset(id)
    if (id !== 'custom') {
      setCustomFrom('')
      setCustomTo('')
    }
  }, [])

  const { createdFrom, createdTo } = useMemo(() => {
    if (preset === 'custom') {
      return {
        createdFrom: customFrom || null,
        createdTo: customTo || null,
      }
    }
    const range = presetToRange(preset)
    if (!range) return { createdFrom: null, createdTo: null }
    return {
      createdFrom: range.from || null,
      createdTo: range.to || null,
    }
  }, [preset, customFrom, customTo])

  const resetDateFilter = useCallback(() => {
    setPreset('all')
    setCustomFrom('')
    setCustomTo('')
  }, [])

  return {
    preset,
    customFrom,
    customTo,
    createdFrom,
    createdTo,
    dateFilterActive: preset !== 'all',
    handlePresetChange,
    setCustomFrom,
    setCustomTo,
    resetDateFilter,
  }
}
