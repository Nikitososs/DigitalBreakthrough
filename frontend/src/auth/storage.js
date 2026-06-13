const TOKEN_KEY = 'zeroproblems_token'
const USER_KEY = 'zeroproblems_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAdmin(user) {
  return user?.role === 'admin'
}
