import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function useIncidentFacets(taskId, options = {}) {
  const {
    severityMin = 1,
    severityMax = 4,
    municipality = null,
    group = null,
    resolved = null,
    enabled = true,
  } = options

  const [facets, setFacets] = useState({
    groups: [],
    topics: [],
    municipalities: [],
    agencies: [],
    with_address: 0,
    total: 0,
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled || !taskId) {
      setFacets({ groups: [], topics: [], municipalities: [], agencies: [], with_address: 0, total: 0 })
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)

    api
      .getTaskIncidentFacets(taskId, { severityMin, severityMax, municipality, group, resolved })
      .then((data) => {
        if (cancelled) return
        setFacets({
          groups: data.groups || [],
          topics: data.topics || [],
          municipalities: data.municipalities || [],
          agencies: data.agencies || [],
          with_address: data.with_address ?? 0,
          total: data.total ?? 0,
        })
      })
      .catch(() => {
        if (cancelled) return
        setFacets({ groups: [], topics: [], municipalities: [], agencies: [], with_address: 0, total: 0 })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [taskId, severityMin, severityMax, municipality, group, resolved, enabled])

  return { facets, loading }
}
