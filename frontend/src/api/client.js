import { tokenStorage } from '../services/tokenStorage'

const BASE = import.meta.env.VITE_API_URL || '/api'

export class ApiError extends Error {
  constructor(message, status, code, body) {
    super(message)
    this.status = status
    this.code = code
    this.body = body
  }
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

function describe(body, fallback) {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ')
  return fallback
}

/** Single place every HTTP call goes through. Returns parsed JSON (or null for 204). */
export async function request(method, path, { body, params } = {}) {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  Object.entries(params || {}).forEach(([k, v]) => v != null && url.searchParams.set(k, v))

  const headers = { Accept: 'application/json' }
  const token = tokenStorage.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0, 'NETWORK')
  }
  if (res.status === 204) return null
  let data = null
  try { data = await res.json() } catch { /* empty body */ }

  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized()
    throw new ApiError(describe(data, `Request failed (${res.status})`), res.status, data?.code, data)
  }
  return data
}

export const get = (path, params) => request('GET', path, { params })
export const post = (path, body, params) => request('POST', path, { body: body ?? {}, params })
export const put = (path, body) => request('PUT', path, { body })
export const patch = (path, body) => request('PATCH', path, { body })
export const del = (path) => request('DELETE', path)
