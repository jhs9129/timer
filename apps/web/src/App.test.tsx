import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows API health once loaded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ status: 'ok', db: 'ok' }), { status: 200 })),
    )
    render(<App />)
    expect(await screen.findByText(/API 상태: ok \(db: ok\)/)).toBeInTheDocument()
  })

  it('shows an error when the API is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('network down')
      }),
    )
    render(<App />)
    expect(await screen.findByText(/연결 실패 \(network down\)/)).toBeInTheDocument()
  })
})
