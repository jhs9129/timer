export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface Health {
  status: string
  db: string
}

export async function fetchHealth(): Promise<Health> {
  const res = await fetch(`${API_URL}/health`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as Health
}
