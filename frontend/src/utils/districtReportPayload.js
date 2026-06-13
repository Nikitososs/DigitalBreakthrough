/** UI district → тело DistrictReport для API (PDF и др.). */

export function districtToReportPayload(district) {
  const themes = (district.problems || [])
    .filter((p) => p.count > 0)
    .filter((p) => p.resolvedPct == null || p.resolvedPct < 100)

  const unresolvedTotal = themes.reduce((s, p) => s + p.count, 0)
    || (district.problemCount != null && district.resolvedCount != null
      ? Math.max(0, district.problemCount - district.resolvedCount)
      : district.problems?.reduce((s, p) => s + p.count, 0) ?? 0)

  const severity = (district.severityStat || [])
    .filter((s) => s.severity > 0 && s.count > 0)

  return {
    district_id: district.id,
    district_name: district.name,
    score: district.score,
    analytical_summary: district.summary || '',
    total_incidents: district.totalIncidents ?? unresolvedTotal,
    top_category: district.topProblem || '—',
    categories_count: themes.length,
    resolved_pct: district.resolvedPct ?? null,
    resolved_count: district.resolvedCount ?? null,
    problem_count: district.problemCount ?? null,
    themes_stat: themes.map((p) => ({
      group_name: p.category,
      count: p.count,
      percentage: unresolvedTotal
        ? Math.round((p.count / unresolvedTotal) * 1000) / 10
        : 0,
      total_count: p.totalCount ?? p.count,
      resolved_pct: p.resolvedPct ?? null,
    })),
    severity_stat: severity.map((s) => ({
      severity: s.severity,
      label: s.label,
      count: s.count,
      percentage: s.percentage,
    })),
    incident_examples: (district.examples || [])
      .map((e) => (typeof e === 'string'
        ? { text: e, severity: 1, label: 'Низкая' }
        : { text: e.text, severity: e.severity, label: e.label }))
      .filter((e) => e.severity > 0),
  }
}
