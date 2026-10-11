import { useCallback, useEffect, useRef, useState } from 'react'

/** Load data on mount (and whenever `deps` change). Exposes loading/error and a `reload` function. */
export function useApi(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const alive = useRef(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const load = useCallback(async (silent = false) => {
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fnRef.current()
      if (alive.current) setState({ data, loading: false, error: null })
    } catch (error) {
      if (alive.current) setState((s) => ({ data: silent ? s.data : null, loading: false, error }))
    }
  }, [])

  useEffect(() => {
    alive.current = true
    load()
    return () => { alive.current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  // Stable function identities so callers can safely use them in effect dependency lists.
  const reload = useCallback(() => load(true), [load])
  const reset = useCallback(() => load(false), [load])
  return { ...state, reload, reset }
}

/** Wrap an async action: tracks `busy`, reports errors/success through the toast helper. */
export function useAction(toast) {
  const [busy, setBusy] = useState(false)
  const run = useCallback(async (fn, { success, onDone } = {}) => {
    setBusy(true)
    try {
      const res = await fn()
      if (success) toast.success(typeof success === 'function' ? success(res) : success)
      if (onDone) await onDone(res)
      return res
    } catch (e) {
      toast.error(e.message)
      return undefined
    } finally {
      setBusy(false)
    }
  }, [toast])
  return { busy, run }
}
