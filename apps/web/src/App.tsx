import { useCallback, useEffect, useState } from 'react'

import { ApiError, api, type Me } from './api'
import { Focus } from './Focus'
import { Login } from './Login'
import { PublicVillage } from './village/PublicVillage'
import { Village } from './village/Village'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'ready'; me: Me }
  | { kind: 'error'; message: string }

/** Minimal routing without a router: focus mode is the default screen; the village is separate. */
export function route(pathname: string): { page: 'focus' } | { page: 'village' } | { page: 'public'; slug: string } {
  const match = /^\/v\/([^/]+)\/?$/.exec(pathname)
  if (match) return { page: 'public', slug: decodeURIComponent(match[1]) }
  if (pathname === '/village' || pathname === '/village/') return { page: 'village' }
  return { page: 'focus' }
}

export function App({ pathname = window.location.pathname }: { pathname?: string }) {
  const current = route(pathname)
  if (current.page === 'public') return <PublicVillage slug={current.slug} />
  return <Authed page={current.page} />
}

function Authed({ page }: { page: 'focus' | 'village' }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  const loadMe = useCallback(async () => {
    try {
      const me = await api.me()
      setState({ kind: 'ready', me })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setState({ kind: 'anonymous' })
      else setState({ kind: 'error', message: err instanceof Error ? err.message : String(err) })
    }
  }, [])

  useEffect(() => {
    void loadMe()
  }, [loadMe])

  switch (state.kind) {
    case 'loading':
      return <main>불러오는 중</main>
    case 'anonymous':
      return <Login onLoggedIn={loadMe} />
    case 'error':
      return (
        <main>
          <p>API에 연결할 수 없습니다 ({state.message})</p>
          <button onClick={() => void loadMe()}>다시 시도</button>
        </main>
      )
    case 'ready':
      if (page === 'village') return <Village />
      return (
        <Focus
          me={state.me}
          refreshMe={loadMe}
          onLogout={async () => {
            await api.logout()
            setState({ kind: 'anonymous' })
          }}
        />
      )
  }
}
