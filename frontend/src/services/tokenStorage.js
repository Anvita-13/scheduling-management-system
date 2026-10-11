// Keeps the JWT in sessionStorage (cleared when the tab closes). Wrapped in try/catch so the app
// still works when storage is blocked.
const KEY = 'scheduling.token'

export const tokenStorage = {
  get() {
    try { return sessionStorage.getItem(KEY) } catch { return null }
  },
  set(token) {
    try { sessionStorage.setItem(KEY, token) } catch { /* ignore */ }
  },
  clear() {
    try { sessionStorage.removeItem(KEY) } catch { /* ignore */ }
  },
}
