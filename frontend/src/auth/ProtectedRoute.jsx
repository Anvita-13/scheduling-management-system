import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Spinner } from '../components/ui'
import { ROLE_HOME, useAuth } from './AuthContext'

/**
 * Route guard. Not signed in -> /login. Signed in with the wrong role -> that user's own home.
 * (This only hides routes; the backend enforces the same rules on every API call.)
 */
export default function ProtectedRoute({ role }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="h-full grid place-items-center"><Spinner label="Checking your session…" /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (role && user.role !== role) return <Navigate to={ROLE_HOME[user.role]} replace />
  return <Outlet />
}
