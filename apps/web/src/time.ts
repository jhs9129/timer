export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Seconds focused right now: server-confirmed seconds plus the open segment drawn locally. */
export function liveFocusedSeconds(
  focusedSeconds: number,
  runningSince: string | null,
  now: number,
): number {
  if (!runningSince) return focusedSeconds
  const elapsed = (now - Date.parse(runningSince)) / 1000
  return focusedSeconds + Math.max(0, elapsed)
}
