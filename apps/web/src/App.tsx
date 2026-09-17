import { useCallback, useEffect, useState } from 'react'

import { ApiError, api, type Me } from './api'
import { Focus } from './Focus'
import { Login } from './Login'

type State =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'ready'; me: Me }
  | { kind: 'error'; message: string }

export function App() {
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
