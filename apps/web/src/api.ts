export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

export interface Health {
  status: string
  db: string
}

export interface Me {
  id: string
  email: string
  display_name: string
  timezone: string
  balance: number
  streak_days: number
  village: { slug: string; name: string; xp: number; level: number }
}

export type SessionStatus = 'running' | 'paused' | 'ended' | 'completed' | 'abandoned'

export interface Session {
  id: string
  mode: 'stopwatch' | 'countdown'
  target_seconds: number | null
  intent: string | null
  status: SessionStatus
  pause_reason: 'user' | 'idle' | 'timeout' | null
  local_date: string
  started_at: string
  ended_at: string | null
  focused_seconds: number
  running_since: string | null
  has_retro: boolean
}

export interface Day {
  date: string
  sessions: Session[]
  focused_seconds: number
  coins_earned: number
}

export interface RetroInput {
  mood: 1 | 2 | 3 | 4
  intent_match?: 'yes' | 'partly' | 'no'
  tags?: string[]
  note?: string
}

export interface RetroResult {
  retro: { id: string; mood: number; intent_match: string | null; tags: string[]; note: string | null }
  reward: { coins: number; base: number; multiplier: number; cap_hit: boolean; streak_days: number }
  session: Session
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    ...init,
  })
  if (res.status === 204) return undefined as T
  const body = (await res.json().catch(() => null)) as
    | { error?: { code: string; message: string } }
    | T
    | null
  if (!res.ok) {
    const err = (body as { error?: { code: string; message: string } } | null)?.error
    throw new ApiError(res.status, err?.code ?? 'http_error', err?.message ?? `HTTP ${res.status}`)
  }
  return body as T
}

const post = <T>(path: string, data?: unknown) =>
  request<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) })

export const api = {
  health: () => request<Health>('/health'),
  me: () => request<Me>('/me'),
  patchMe: (data: { timezone?: string; display_name?: string }) =>
    request<Me>('/me', { method: 'PATCH', body: JSON.stringify(data) }),
  devLogin: (email: string) => post<Me>('/auth/dev-login', { email }),
  logout: () => post<void>('/auth/logout'),
  current: () => request<Session | undefined>('/sessions/current'),
  start: (data: { mode: 'stopwatch' | 'countdown'; target_seconds?: number; intent?: string }) =>
    post<Session>('/sessions', data),
  heartbeat: (id: string) => post<Session>(`/sessions/${id}/heartbeat`),
  pause: (id: string, reason: 'user' | 'idle') => post<Session>(`/sessions/${id}/pause`, { reason }),
  resume: (id: string) => post<Session>(`/sessions/${id}/resume`),
  stop: (id: string) => post<Session>(`/sessions/${id}/stop`),
  retro: (id: string, data: RetroInput) => post<RetroResult>(`/sessions/${id}/retro`, data),
  day: (date?: string) => request<Day>(`/sessions${date ? `?date=${date}` : ''}`),
}

export interface Item {
  code: string
  name: string
  category: 'ground' | 'tree' | 'prop' | 'building'
  layer: 'ground' | 'object'
  price: number
  width: number
  height: number
  unlock_level: number
}

export interface InventoryEntry {
  item_code: string
  qty: number
}

export interface Placement {
  id: string
  item_code: string
  category: Item['category']
  layer: Item['layer']
  x: number
  y: number
  rotation: number
  width: number
  height: number
}

export interface PublicVillage {
  slug: string
  name: string
  width: number
  height: number
  level: number
  xp: number
  placements: Placement[]
}

export interface Village extends PublicVillage {
  inventory: InventoryEntry[]
  balance: number
  next_level_xp: number | null
}

export const villageApi = {
  mine: () => request<Village>('/villages/me'),
  rename: (name: string) => request<Village>('/villages/me', { method: 'PATCH', body: JSON.stringify({ name }) }),
  public: (slug: string) => request<PublicVillage>(`/v/${encodeURIComponent(slug)}`),
  items: () => request<Item[]>('/shop/items'),
  purchase: (item_code: string) =>
    post<{ inventory: InventoryEntry[]; balance: number }>('/shop/purchase', { item_code }),
  place: (item_code: string, x: number, y: number, rotation = 0) =>
    post<Placement>('/villages/me/placements', { item_code, x, y, rotation }),
  move: (id: string, x: number, y: number, rotation?: number) =>
    request<Placement>(`/villages/me/placements/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ x, y, rotation }),
    }),
  remove: (id: string) => request<void>(`/villages/me/placements/${id}`, { method: 'DELETE' }),
}

export interface NotificationPrefs {
  push: boolean
  email_weekly: boolean
  reminder_local_time: string | null
}

export const notificationApi = {
  vapidKey: () => request<{ key: string }>('/push/vapid-public-key'),
  addPushSubscription: (data: {
    endpoint: string
    keys: { p256dh: string; auth: string }
    user_agent?: string
  }) => post<{ id: string }>('/push/subscriptions', data),
  removePushSubscription: (endpoint: string) =>
    request<void>(`/push/subscriptions?endpoint=${encodeURIComponent(endpoint)}`, { method: 'DELETE' }),
  prefs: () => request<NotificationPrefs>('/me/notifications'),
  patchPrefs: (data: Partial<NotificationPrefs>) =>
    request<NotificationPrefs>('/me/notifications', { method: 'PATCH', body: JSON.stringify(data) }),
}

export const googleLoginUrl = `${API_URL}/auth/google/start`
