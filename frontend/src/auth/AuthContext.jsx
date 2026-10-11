import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api'
import { setUnauthorizedHandler } from '../api/client'
import { tokenStorage } from '../services/tokenStorage'

const AuthContext = createContext(null)

export const ROLE_HOME = { ADMIN: '/admin', FACULTY: '/faculty', STUDENT: '/student' }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStorage.get()))

  const logout = useCallback(() => {
    tokenStorage.clear()
    setUser(null)
  }, [])

  useEffect(() => { setUnauthorizedHandler(logout) }, [logout])

  // Restore the session from a stored token (the server re-validates it).
  useEffect(() => {
    if (!tokenStorage.get()) return
    authApi.me().then(setUser).catch(() => tokenStorage.clear()).finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await authApi.login(email, password)
    tokenStorage.set(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
