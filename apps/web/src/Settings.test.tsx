import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Settings } from './Settings'
import { detectPushSupport } from './notifications'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('detectPushSupport', () => {
  it('asks iOS Safari users to install first', () => {
    const nav = { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari' } as Navigator
    const win = { matchMedia: () => ({ matches: false }) } as unknown as Window
    expect(detectPushSupport(nav, win)).toEqual({ kind: 'ios_needs_install' })
  })

  it('treats an installed iOS PWA as supported when APIs exist', () => {
    const nav = {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari',
      standalone: true,
      serviceWorker: {},
    } as unknown as Navigator
    const win = { matchMedia: () => ({ matches: true }), PushManager: {}, Notification: {} } as unknown as Window
    expect(detectPushSupport(nav, win)).toEqual({ kind: 'supported' })
  })

  it('reports missing APIs on other browsers', () => {
    const nav = { userAgent: 'Mozilla/5.0 (X11; Linux x86_64)' } as Navigator
    const win = { matchMedia: () => ({ matches: false }) } as unknown as Window
    expect(detectPushSupport(nav, win).kind).toBe('unsupported')
  })
})

describe('Settings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads prefs and patches the weekly email consent', async () => {
    const calls: { key: string; body: unknown }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const key = `${init?.method ?? 'GET'} ${url.replace(/^https?:\/\/[^/]+/, '')}`
        calls.push({ key, body: init?.body ? JSON.parse(String(init.body)) : null })
        if (key === 'GET /me/notifications') {
          return json({ push: false, email_weekly: calls.some((c) => c.key.startsWith('PATCH')), reminder_local_time: null })
        }
        if (key === 'PATCH /me/notifications') return json({ push: false, email_weekly: true, reminder_local_time: null })
        throw new Error(`unexpected fetch: ${key}`)
      }),
    )
    render(<Settings onClose={() => undefined} />)
    const weekly = await screen.findByLabelText('월요일 아침 주간 요약 이메일')
    expect(weekly).not.toBeChecked()
    fireEvent.click(weekly)
    await waitFor(() => expect(calls.some((c) => c.key === 'PATCH /me/notifications')).toBe(true))
    expect(calls.find((c) => c.key === 'PATCH /me/notifications')?.body).toEqual({ email_weekly: true })
    await waitFor(() => expect(screen.getByLabelText('월요일 아침 주간 요약 이메일')).toBeChecked())
  })
})
