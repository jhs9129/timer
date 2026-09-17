import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import type { Day, Me, Session } from './api'

const ME: Me = {
  id: 'u1',
  email: 'jane@example.com',
  display_name: 'Jane',
  timezone: 'Asia/Seoul',
  balance: 42,
  streak_days: 3,
  village: { slug: 'abc', name: 'Jane의 마을', xp: 120 },
}

const DAY: Day = { date: '2026-09-17', sessions: [], focused_seconds: 0, coins_earned: 0 }

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Routes fetch calls by "METHOD path"; unmatched calls fail loudly. */
function mockFetch(routes: Record<string, () => Response>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const path = url.replace(/^https?:\/\/[^/]+/, '')
      const key = `${init?.method ?? 'GET'} ${path}`
      calls.push(key)
      const handler = routes[key]
      if (!handler) throw new Error(`unexpected fetch: ${key}`)
      return handler()
    }),
  )
  return calls
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the login screen when the API answers 401', async () => {
    mockFetch({
      'GET /me': () => json({ error: { code: 'unauthorized', message: 'login required' } }, 401),
    })
    render(<App />)
    expect(await screen.findByText('Google로 시작하기')).toBeInTheDocument()
  })

  it('shows the start form when logged in without an active session', async () => {
    mockFetch({
      'GET /me': () => json(ME),
      'GET /sessions/current': () => new Response(null, { status: 204 }),
      'GET /sessions': () => json(DAY),
    })
    render(<App />)
    expect(await screen.findByRole('form', { name: 'start' })).toBeInTheDocument()
    expect(screen.getByText(/코인 42/)).toBeInTheDocument()
  })

  it('starts a session and renders the running timer', async () => {
    const running: Session = {
      id: 's1',
      mode: 'stopwatch',
      target_seconds: null,
      intent: 'write tests',
      status: 'running',
      pause_reason: null,
      local_date: '2026-09-17',
      started_at: new Date().toISOString(),
      ended_at: null,
      focused_seconds: 0,
      running_since: new Date().toISOString(),
      has_retro: false,
    }
    const calls = mockFetch({
      'GET /me': () => json(ME),
      'GET /sessions/current': () => new Response(null, { status: 204 }),
      'GET /sessions': () => json(DAY),
      'POST /sessions': () => json(running, 201),
    })
    render(<App />)
    const form = await screen.findByRole('form', { name: 'start' })
    fireEvent.change(screen.getByPlaceholderText(/무엇에 몰두할까요/), { target: { value: 'write tests' } })
    fireEvent.submit(form)
    expect(await screen.findByText('몰두 중: write tests')).toBeInTheDocument()
    expect(screen.getByText('일시정지')).toBeInTheDocument()
    expect(calls).toContain('POST /sessions')
  })

  it('shows the retro form after the session ends', async () => {
    const ended: Session = {
      id: 's1',
      mode: 'stopwatch',
      target_seconds: null,
      intent: null,
      status: 'ended',
      pause_reason: null,
      local_date: '2026-09-17',
      started_at: new Date().toISOString(),
      ended_at: new Date().toISOString(),
      focused_seconds: 600,
      running_since: null,
      has_retro: false,
    }
    mockFetch({
      'GET /me': () => json(ME),
      'GET /sessions/current': () => json(ended),
      'GET /sessions': () => json(DAY),
    })
    render(<App />)
    expect(await screen.findByRole('form', { name: 'retro' })).toBeInTheDocument()
    expect(screen.getByText(/10:00 몰두했어요/)).toBeInTheDocument()
  })
})
