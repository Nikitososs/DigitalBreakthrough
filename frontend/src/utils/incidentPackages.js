import { isIncidentResolved } from './incidentModel'

/** Только нерешённые проблемные обращения (классы 1–4). */
export function isOpenProblem(item) {
  if (!item || item.severity < 1 || item.severity > 4) return false
  return !isIncidentResolved(item)
}

function normalizeKey(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^\p{L}\d\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Объединение похожих формулировок тем (отопление / отопление в домах). */
export function topicsSimilar(a, b) {
  const na = normalizeKey(a)
  const nb = normalizeKey(b)
  if (!na || !nb) return na === nb
  if (na === nb) return true
  if (na.includes(nb) || nb.includes(na)) return true
  const wa = na.split(' ')[0]
  const wb = nb.split(' ')[0]
  return wa.length >= 4 && wa === wb
}

function mergeTopicLabels(topics) {
  const out = []
  for (const t of topics) {
    const topic = String(t || '').trim()
    if (!topic) continue
    if (out.some((u) => topicsSimilar(u, topic))) continue
    out.push(topic)
  }
  return out.sort((a, b) => a.localeCompare(b, 'ru'))
}

function severityCounts(items) {
  const counts = { 1: 0, 2: 0, 3: 0, 4: 0 }
  for (const item of items) {
    if (counts[item.severity] != null) counts[item.severity] += 1
  }
  return counts
}

function makeBundle(agencyName, group, items, topics) {
  const mergedTopics = mergeTopicLabels(topics)
  const groupLabel = group || 'Без категории'
  const label = mergedTopics.length
    ? `${groupLabel} · ${mergedTopics.slice(0, 4).join(', ')}${mergedTopics.length > 4 ? '…' : ''}`
    : groupLabel
  const topicKey = mergedTopics.join('|') || '_'
  return {
    id: `${agencyName}::${groupLabel}::${topicKey}`,
    group: groupLabel,
    topics: mergedTopics,
    label,
    items,
    count: items.length,
    severityCounts: severityCounts(items),
  }
}

/**
 * Пакеты для вкладки «Обращения»: ведомство → категории (группа тем) → обращения 1–4 класса.
 */
export function buildAgencyPackages(items) {
  const open = (items || []).filter(isOpenProblem)
  const agencyMap = new Map()

  for (const item of open) {
    const agencyName = item.agency?.name || 'Иные ведомства Омской области'
    if (!agencyMap.has(agencyName)) {
      agencyMap.set(agencyName, { agency: item.agency, byGroup: new Map() })
    }
    const group = item.group || item.category || 'Без категории'
    const bucket = agencyMap.get(agencyName)
    if (!bucket.byGroup.has(group)) bucket.byGroup.set(group, [])
    bucket.byGroup.get(group).push(item)
  }

  const packages = []
  for (const [agencyName, { agency, byGroup }] of agencyMap) {
    const bundles = []
    for (const [group, groupItems] of byGroup) {
      const topics = groupItems.map((i) => i.topic).filter(Boolean)
      const topicClusters = []
      for (const topic of topics) {
        let placed = false
        for (const cluster of topicClusters) {
          if (cluster.some((t) => topicsSimilar(t, topic))) {
            cluster.push(topic)
            placed = true
            break
          }
        }
        if (!placed) topicClusters.push([topic])
      }

      if (topicClusters.length <= 1) {
        bundles.push(makeBundle(agencyName, group, groupItems, topics))
        continue
      }

      const assigned = new Set()
      for (const cluster of topicClusters) {
        const clusterItems = groupItems.filter((item) => {
          if (assigned.has(item.id)) return false
          if (!item.topic) return false
          return cluster.some((t) => topicsSimilar(t, item.topic))
        })
        clusterItems.forEach((i) => assigned.add(i.id))
        if (clusterItems.length) bundles.push(makeBundle(agencyName, group, clusterItems, cluster))
      }

      const rest = groupItems.filter((i) => !assigned.has(i.id))
      if (rest.length) bundles.push(makeBundle(agencyName, group, rest, rest.map((i) => i.topic)))
    }

    bundles.sort((a, b) => b.count - a.count)
    const total = bundles.reduce((s, b) => s + b.count, 0)
    packages.push({ agency, agencyName, bundles, total })
  }

  packages.sort((a, b) => b.total - a.total)
  return packages
}

export function bundleSelectionState(bundle, selectedMap) {
  if (!bundle?.items?.length) return { all: false, some: false }
  let n = 0
  for (const item of bundle.items) {
    if (selectedMap.has(item.id)) n += 1
  }
  return {
    all: n === bundle.items.length,
    some: n > 0 && n < bundle.items.length,
  }
}

/** Нормализация пакетов с API (сборка уже на сервере). */
export function normalizePackagesFromApi(packages, normalizeIncident) {
  return (packages || []).map((pkg) => {
    const agencyName = pkg.agency_name || pkg.agency || 'Иные ведомства Омской области'
    const agencyEmail = pkg.agency_email || ''
    return {
      agencyName,
      agency: {
        name: agencyName,
        email: agencyEmail,
      },
      total: pkg.total ?? 0,
      bundles: (pkg.bundles || []).map((bundle) => ({
        id: bundle.id,
        group: bundle.group,
        topics: bundle.topics || [],
        label: bundle.label,
        count: bundle.count ?? (bundle.items || []).length,
        severityCounts: bundle.severity_counts || bundle.severityCounts || {},
        items: (bundle.items || []).map((row, i) => normalizeIncident(row, row.id || `pkg-${i}`)),
      })),
    }
  })
}

function mergeSeverityCounts(a = {}, b = {}) {
  const out = { 1: 0, 2: 0, 3: 0, 4: 0 }
  for (const src of [a, b]) {
    for (const [key, val] of Object.entries(src || {})) {
      const sev = Number(key)
      if (out[sev] != null) out[sev] += Number(val) || 0
    }
  }
  return out
}

/** Слияние пакетов с нескольких страниц. */
export function mergeAgencyPackages(existing, incoming) {
  const byAgency = new Map()

  for (const pkg of [...(existing || []), ...(incoming || [])]) {
    const agencyName = pkg.agencyName || pkg.agency?.name || 'Иные ведомства Омской области'
    if (!byAgency.has(agencyName)) {
      byAgency.set(agencyName, {
        agencyName,
        agency: pkg.agency || { name: agencyName, email: '' },
        bundles: new Map(),
      })
    }
    const bucket = byAgency.get(agencyName)
    if (!bucket.agency.email && pkg.agency?.email) {
      bucket.agency = { ...bucket.agency, email: pkg.agency.email }
    }

    for (const bundle of pkg.bundles || []) {
      if (!bucket.bundles.has(bundle.id)) {
        bucket.bundles.set(bundle.id, {
          ...bundle,
          items: [...(bundle.items || [])],
        })
        continue
      }
      const prev = bucket.bundles.get(bundle.id)
      const seen = new Set(prev.items.map((i) => i.id))
      for (const item of bundle.items || []) {
        if (seen.has(item.id)) continue
        prev.items.push(item)
        seen.add(item.id)
      }
      prev.count = prev.items.length
      prev.severityCounts = mergeSeverityCounts(prev.severityCounts, bundle.severityCounts)
    }
  }

  return [...byAgency.values()]
    .map((bucket) => {
      const bundles = [...bucket.bundles.values()].sort((a, b) => b.count - a.count)
      return {
        agencyName: bucket.agencyName,
        agency: bucket.agency,
        bundles,
        total: bundles.reduce((s, b) => s + b.count, 0),
      }
    })
    .sort((a, b) => b.total - a.total)
}
