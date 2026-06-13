import {
  Building2,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Loader2,
  Mail,
  Map as MapIcon,
  MapPin,
  MinusSquare,
  RotateCcw,
  Send,
  Square,
  Trash2,
} from 'lucide-react'
import ResolvedBadge from './ResolvedBadge'
import { citizenRowId, isCitizenRowId, SEVERITY_COLORS } from '../utils/incidentModel'
import { bundleSelectionState } from '../utils/incidentPackages'

function SeverityPills({ counts }) {
  return (
    <div className="flex flex-wrap gap-1">
      {[4, 3, 2, 1].map((sev) => (
        counts[sev] > 0 ? (
          <span
            key={sev}
            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
            style={{ background: `${SEVERITY_COLORS[sev]}22`, color: SEVERITY_COLORS[sev] }}
          >
            {sev}: {counts[sev]}
          </span>
        ) : null
      ))}
    </div>
  )
}

export default function IncidentPackageList({
  packages,
  selectedMap,
  expandedAgencies,
  expandedBundles,
  onToggleAgency,
  onToggleBundleExpand,
  onToggleBundleSelect,
  onToggleItem,
  onSendBundle,
  onComposeBundle,
  composingKey,
  sent,
  geocodingId,
  deletingId,
  isLiveTask,
  onGeocode,
  onDeleteCitizen,
  onShowOnMap,
}) {
  if (!packages.length) {
    return (
      <p className="text-center text-sm py-16" style={{ color: 'var(--muted)' }}>
        Нет открытых (нерешённых) обращений по выбранным фильтрам
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {packages.map((pkg) => {
        const agencyOpen = expandedAgencies.has(pkg.agencyName)
        return (
          <section
            key={pkg.agencyName}
            className="rounded-xl overflow-hidden"
            style={{ border: '1px solid var(--border)', background: 'var(--bg-card)' }}
          >
            <button
              type="button"
              onClick={() => onToggleAgency(pkg.agencyName)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left"
              style={{ background: 'var(--bg-sub)' }}
            >
              {agencyOpen
                ? <ChevronDown className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                : <ChevronRight className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />}
              <Building2 className="w-4 h-4 flex-shrink-0 text-red-600" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>
                  {pkg.agencyName}
                </div>
                {pkg.agency?.email ? (
                  <div className="text-xs truncate" style={{ color: 'var(--muted)' }}>{pkg.agency.email}</div>
                ) : null}
              </div>
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 flex-shrink-0">
                {pkg.total} откр.
              </span>
              <span className="text-xs flex-shrink-0" style={{ color: 'var(--muted)' }}>
                {pkg.bundles.length} кат.
              </span>
            </button>

            {agencyOpen && (
              <div className="px-3 py-2 space-y-2">
                {pkg.bundles.map((bundle) => {
                  const bundleOpen = expandedBundles.has(bundle.id)
                  const sel = bundleSelectionState(bundle, selectedMap)
                  const composeKey = `${pkg.agencyName}::${bundle.id}`
                  return (
                    <div
                      key={bundle.id}
                      className="rounded-lg overflow-hidden"
                      style={{ border: '1px solid var(--border)' }}
                    >
                      <div
                        className="flex items-center gap-2 px-3 py-2.5"
                        style={{ background: sel.all ? '#fef2f2' : 'var(--bg-card)' }}
                      >
                        <button
                          type="button"
                          onClick={() => onToggleBundleSelect(bundle)}
                          className="flex-shrink-0"
                          title="Выбрать все обращения категории"
                        >
                          {sel.all
                            ? <CheckSquare className="w-4 h-4 text-red-600" />
                            : sel.some
                              ? <MinusSquare className="w-4 h-4 text-red-500" />
                              : <Square className="w-4 h-4" style={{ color: 'var(--muted)' }} />}
                        </button>
                        <button
                          type="button"
                          onClick={() => onToggleBundleExpand(bundle.id)}
                          className="flex items-center gap-2 min-w-0 flex-1 text-left"
                        >
                          {bundleOpen
                            ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                            : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--muted)' }} />}
                          <div className="min-w-0">
                            <div className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
                              {bundle.label}
                            </div>
                            <SeverityPills counts={bundle.severityCounts} />
                          </div>
                        </button>
                        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 flex-shrink-0">
                          {bundle.count}
                        </span>
                        <button
                          type="button"
                          onClick={() => onSendBundle(bundle)}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold flex-shrink-0"
                          style={{ background: '#dc2626', color: '#fff' }}
                          title="Отправить пакет в ведомство"
                        >
                          <Send className="w-3 h-3" />
                          Пакет
                        </button>
                        <button
                          type="button"
                          onClick={() => onComposeBundle(bundle, pkg.agency)}
                          disabled={!!composingKey}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold flex-shrink-0"
                          style={{
                            background: composingKey === composeKey ? 'var(--bg-sub)' : '#2563eb',
                            color: composingKey === composeKey ? 'var(--muted)' : '#fff',
                            opacity: composingKey && composingKey !== composeKey ? 0.5 : 1,
                          }}
                        >
                          {composingKey === composeKey
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Mail className="w-3 h-3" />}
                          AI
                        </button>
                      </div>

                      {bundleOpen && (
                        <div className="px-2 pb-2 space-y-1.5">
                          {bundle.items.map((item) => {
                            const isSent = sent.has(item.id)
                            const isSelected = selectedMap.has(item.id)
                            const color = SEVERITY_COLORS[item.severity]
                            return (
                              <div
                                key={item.id}
                                onClick={() => !isSent && onToggleItem(item)}
                                className={[
                                  'operator-incident',
                                  isSelected ? 'operator-incident--selected' : '',
                                  item.isLive ? 'operator-incident--live' : '',
                                  isSent ? 'operator-incident--sent' : '',
                                ].filter(Boolean).join(' ')}
                                style={{ '--sev-color': color }}
                              >
                                <div className="operator-incident__bar" />
                                <div className="operator-incident__check">
                                  {isSent
                                    ? <CheckSquare className="w-4 h-4 text-emerald-500" />
                                    : isSelected
                                      ? <CheckSquare className="w-4 h-4 text-red-600" />
                                      : <Square className="w-4 h-4" style={{ color: 'var(--muted)' }} />}
                                </div>
                                <div className="operator-incident__body">
                                  <div className="operator-incident__meta">
                                    {item.isLive && <span className="operator-incident__live-badge">● LIVE</span>}
                                    <span className="operator-incident__badge">{item.label} · {item.severity}</span>
                                    <ResolvedBadge item={item} />
                                    <span className="operator-incident__district">{item.district}</span>
                                    {item.topic && (
                                      <>
                                        <span className="operator-incident__sep">·</span>
                                        <span className="operator-incident__category">{item.topic}</span>
                                      </>
                                    )}
                                    {item.hasAddress && (
                                      <span className="operator-incident__address">📍 {item.street || 'адрес'}</span>
                                    )}
                                    {isSent && <span className="operator-incident__sent-badge">✓ Отправлено</span>}
                                  </div>
                                  <p className="operator-incident__text">{item.text}</p>
                                </div>
                                {(item.hasAddress || (isLiveTask && isCitizenRowId(item.id))) && (
                                  <div className="operator-incident__actions" onClick={(e) => e.stopPropagation()}>
                                    {item.hasAddress && (
                                      item.lat == null ? (
                                        <button
                                          type="button"
                                          disabled={geocodingId === citizenRowId(item.id)}
                                          onClick={(e) => onGeocode(item, e)}
                                          className="operator-action-btn operator-action-btn--geo"
                                        >
                                          {geocodingId === citizenRowId(item.id)
                                            ? <Loader2 className="w-3 h-3 animate-spin" />
                                            : <MapPin className="w-3 h-3" />}
                                        </button>
                                      ) : (
                                        <>
                                          {onShowOnMap && (
                                            <button
                                              type="button"
                                              onClick={(e) => onShowOnMap(item, e)}
                                              className="operator-action-btn operator-action-btn--map"
                                            >
                                              <MapIcon className="w-3 h-3" />
                                            </button>
                                          )}
                                          <button
                                            type="button"
                                            disabled={geocodingId === citizenRowId(item.id)}
                                            onClick={(e) => onGeocode(item, e)}
                                            className="operator-action-btn operator-action-btn--geo"
                                          >
                                            {geocodingId === citizenRowId(item.id)
                                              ? <Loader2 className="w-3 h-3 animate-spin" />
                                              : <RotateCcw className="w-3 h-3" />}
                                          </button>
                                        </>
                                      )
                                    )}
                                    {isLiveTask && isCitizenRowId(item.id) && (
                                      <button
                                        type="button"
                                        disabled={deletingId === citizenRowId(item.id)}
                                        onClick={(e) => onDeleteCitizen(item, e)}
                                        className="operator-action-btn operator-action-btn--del"
                                      >
                                        {deletingId === citizenRowId(item.id)
                                          ? <Loader2 className="w-3 h-3 animate-spin" />
                                          : <Trash2 className="w-3 h-3" />}
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
