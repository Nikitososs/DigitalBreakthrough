import { isIncidentResolved } from '../utils/incidentModel'

export default function ResolvedBadge({ item, className = '' }) {
  const severity = Number(item?.severity ?? 0)
  if (severity <= 0) return null

  const resolved = isIncidentResolved(item)
  const classes = [
    'resolved-badge',
    resolved ? 'resolved-badge--yes' : 'resolved-badge--no',
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={classes}>
      {resolved ? 'Решена' : 'Не решена'}
    </span>
  )
}
