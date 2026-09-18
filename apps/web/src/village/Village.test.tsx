import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App, route } from '../App'
import type { Item, PublicVillage, Village } from '../api'

const ITEMS: Item[] = [
  { code: 'tree_oak', name: '참나무', category: 'tree', layer: 'object', price: 60, width: 1, height: 1, unlock_level: 1 },
  { code: 'prop_well', name: '우물', category: 'prop', layer: 'object', price: 200, width: 2, height: 2, unlock_level: 2 },
]

const VILLAGE: Village = {
  slug: 'abc',
  name: 'Jane의 마을',
  width: 16,
  height: 16,
  level: 1,
  xp: 10,
  next_level_xp: 600,
  balance: 100,
  inventory: [],
  placements: [
    { id: 'p1', item_code: 'tree_oak', category: 'tree', layer: 'object', x: 2, y: 3, rotation: 0, width: 1, height: 1 },
  ],
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function mockFetch(routes: Record<string, () => Response>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const key = `${init?.method ?? 'GET'} ${url.replace(/^https?:\/\/[^/]+/, '')}`
      calls.push(key)
      const handler = routes[key]
      if (!handler) throw new Error(`unexpected fetch: ${key}`)
      return handler()
    }),
  )
  return calls
}

describe('route', () => {
  it('maps paths to pages', () => {
    expect(route('/')).toEqual({ page: 'focus' })
    expect(route('/village')).toEqual({ page: 'village' })
    expect(route('/v/abc')).toEqual({ page: 'public', slug: 'abc' })
    expect(route('/v/abc/extra')).toEqual({ page: 'focus' })
  })
})

describe('Village', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the grid, placements and shop; buying refreshes inventory', async () => {
    let village = VILLAGE
    const calls = mockFetch({
      'GET /me': () => json({ id: 'u1', email: 'a@b.c', display_name: 'Jane', timezone: 'Asia/Seoul', balance: 100, streak_days: 0, village: { slug: 'abc', name: 'x', xp: 10, level: 1 } }),
      'GET /villages/me': () => json(village),
      'GET /shop/items': () => json(ITEMS),
      'POST /shop/purchase': () => {
        village = { ...village, balance: 40, inventory: [{ item_code: 'tree_oak', qty: 1 }] }
        return json({ inventory: village.inventory, balance: 40 })
      },
    })
    render(<App pathname="/village" />)
    expect(await screen.findByRole('grid', { name: 'village grid' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'tree_oak at 2,3' })).toBeInTheDocument()
    const buyButtons = screen.getAllByRole('button', { name: '구매' })
    expect(buyButtons[1]).toBeDisabled() // prop_well: level 2 and too expensive
    fireEvent.click(buyButtons[0])
    await waitFor(() => expect(calls).toContain('POST /shop/purchase'))
    expect(await screen.findByRole('button', { name: 'tree_oak × 1' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '상점 · 코인 40' })).toBeInTheDocument()
  })

  it('shows a public village without logging in', async () => {
    const pub: PublicVillage = { slug: 'abc', name: '공개 마을', width: 16, height: 16, level: 2, xp: 700, placements: [] }
    const calls = mockFetch({ 'GET /v/abc': () => json(pub) })
    render(<App pathname="/v/abc" />)
    expect(await screen.findByText('공개 마을')).toBeInTheDocument()
    expect(calls).not.toContain('GET /me')
  })

  it('shows a friendly message for a missing public village', async () => {
    mockFetch({ 'GET /v/nope': () => json({ error: { code: 'not_found', message: 'village not found' } }, 404) })
    render(<App pathname="/v/nope" />)
    expect(await screen.findByText('그런 마을은 없어요.')).toBeInTheDocument()
  })
})
