/** Учётные роли (JWT / users.role). Вкладки дашборда — отдельно. */

export const USER_ROLES = [
  { value: 'admin', label: 'Администратор', hint: 'Полный доступ, база, пользователи, все вкладки' },
  { value: 'analyst', label: 'Аналитик', hint: 'Аналитика, прогноз, карта инцидентов' },
  { value: 'operator', label: 'Оператор', hint: 'Обращения, live-поток, письма в ведомства' },
]

export const ROLE_LABELS = Object.fromEntries(USER_ROLES.map((r) => [r.value, r.label]))

/** Старые записи emergency → analyst (до миграции БД). */
export function normalizeUserRole(role) {
  if (role === 'emergency') return 'analyst'
  return role || ''
}

export function roleLabel(role) {
  return ROLE_LABELS[normalizeUserRole(role)] || role || '—'
}

export function isAnalyticsUser(user) {
  const role = normalizeUserRole(user?.role)
  return role === 'admin' || role === 'analyst'
}

export function isOperatorUser(user) {
  return normalizeUserRole(user?.role) === 'operator'
}

export function isAdminUser(user) {
  return normalizeUserRole(user?.role) === 'admin'
}

/** Вкладки верхнего меню дашборда (не путать с users.role). */
export function visibleDashboardTabsForUser(user, baseTabs) {
  if (!user) return baseTabs
  const role = normalizeUserRole(user.role)
  if (role === 'admin') return baseTabs
  if (role === 'analyst') return baseTabs.filter((t) => t.id === 'analyst' || t.id === 'forecast')
  if (role === 'operator') return baseTabs.filter((t) => t.id === 'operator')
  return baseTabs.filter((t) => t.id === role)
}

export function defaultDashboardTabForUser(user) {
  if (!user) return 'analyst'
  const role = normalizeUserRole(user.role)
  if (role === 'operator') return 'operator'
  return 'analyst'
}
