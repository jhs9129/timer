import { useEffect, useRef, useState } from 'react'

/** Re-renders every `ms`; returns the current epoch millis. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), ms)
    return () => window.clearInterval(id)
  }, [ms])
  return now
}

/** Calls `fn` every `ms` while `active`. */
export function useInterval(fn: () => void, ms: number, active: boolean): void {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => ref.current(), ms)
    return () => window.clearInterval(id)
  }, [ms, active])
}

/**
 * Idle detection for the focus screen: fires `onIdle` when the tab is hidden or when no
 * keyboard/mouse/touch input arrives for `idleMs`. Only armed while `active`.
 */
export function useIdleDetector(active: boolean, idleMs: number, onIdle: () => void): void {
  const cb = useRef(onIdle)
  cb.current = onIdle
  useEffect(() => {
    if (!active) return
    let timer = window.setTimeout(() => cb.current(), idleMs)
    const bump = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => cb.current(), idleMs)
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') cb.current()
    }
    const events: (keyof DocumentEventMap)[] = ['keydown', 'mousemove', 'mousedown', 'touchstart', 'scroll']
    events.forEach((e) => document.addEventListener(e, bump, { passive: true }))
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearTimeout(timer)
      events.forEach((e) => document.removeEventListener(e, bump))
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [active, idleMs])
}
