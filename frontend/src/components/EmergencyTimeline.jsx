import { CalendarRange, ChevronLeft, ChevronRight } from 'lucide-react'
import { EMERGENCY_PRESETS, formatPeriodRu } from '../utils/emergencyTimeline'

export default function EmergencyTimeline({
  preset,
  windowDays,
  createdFrom,
  createdTo,
  offsetDays,
  maxOffsetDays,
  datasetStart,
  datasetEnd,
  loading = false,
  fetchPending = false,
  onPresetChange,
  onOffsetChange,
  onOffsetCommit,
  onJumpLatest,
  variant = 'inline',
}) {
  const canSlide = maxOffsetDays > 0 && !loading
  const isSidebar = variant === 'sidebar'

  const step = (delta) => {
    if (!canSlide) return
    const stepDays = Math.max(1, Math.round(windowDays / 12))
    onOffsetChange(offsetDays + delta * stepDays)
    onOffsetCommit?.()
  }

  const presets = (
    <div className={`emergency-timeline__presets${isSidebar ? ' emergency-timeline__presets--stack' : ''}`}>
      {!isSidebar && <CalendarRange className="emergency-timeline__icon" aria-hidden />}
      {EMERGENCY_PRESETS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onPresetChange(p.id)}
          className={`emergency-timeline__preset${preset === p.id ? ' emergency-timeline__preset--active' : ''}`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )

  const period = (
    <div className={`emergency-timeline__period${isSidebar ? ' emergency-timeline__period--badge' : ''}`}>
      <span className="emergency-timeline__period-range">
        {loading ? '…' : formatPeriodRu(createdFrom, createdTo)}
        {fetchPending && !loading && <span className="emergency-timeline__pending"> · …</span>}
      </span>
    </div>
  )

  const controls = (
    <div className="emergency-timeline__controls">
      <button
        type="button"
        disabled={!canSlide || offsetDays <= 0}
        onClick={() => step(-1)}
        className="emergency-timeline__nav"
        aria-label="Раньше"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>
      <div className="emergency-timeline__slider-wrap">
        <input
          type="range"
          min={0}
          max={maxOffsetDays || 0}
          step={1}
          value={offsetDays}
          disabled={!canSlide}
          onChange={(e) => onOffsetChange(Number(e.target.value))}
          onMouseUp={onOffsetCommit}
          onTouchEnd={onOffsetCommit}
          onKeyUp={onOffsetCommit}
          className="emergency-timeline__slider"
          title={datasetStart && datasetEnd ? `${datasetStart} — ${datasetEnd}` : 'Период задачи'}
        />
      </div>
      <button
        type="button"
        disabled={!canSlide || offsetDays >= maxOffsetDays}
        onClick={() => step(1)}
        className="emergency-timeline__nav"
        aria-label="Позже"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
      {canSlide && (
        <button
          type="button"
          className="emergency-timeline__now"
          onClick={onJumpLatest}
          title={`Последние ${windowDays} дн.`}
        >
          Сейчас
        </button>
      )}
    </div>
  )

  if (isSidebar) {
    return (
      <div className="emergency-timeline emergency-timeline--sidebar">
        <div className="analyst-map-sidebar__title">
          <CalendarRange className="w-3.5 h-3.5" aria-hidden />
          <span>Период</span>
        </div>
        {presets}
        {period}
        {controls}
      </div>
    )
  }

  return (
    <div className="emergency-timeline">
      <div className="emergency-timeline__top">
        {presets}
        {period}
      </div>
      {controls}
    </div>
  )
}
