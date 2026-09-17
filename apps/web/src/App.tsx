import { useEffect, useState } from 'react'

import { fetchHealth, type Health } from './api'

type State = { kind: 'loading' } | { kind: 'ok'; health: Health } | { kind: 'error'; message: string }

export function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then((health) => {
        if (!cancelled) setState({ kind: 'ok', health })
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ kind: 'error', message: err instanceof Error ? err.message : String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main>
      <h1>My Little Village</h1>
      <p>API 상태: {describe(state)}</p>
    </main>
  )
}

function describe(state: State): string {
  switch (state.kind) {
    case 'loading':
      return '확인 중'
    case 'ok':
      return `${state.health.status} (db: ${state.health.db})`
    case 'error':
      return `연결 실패 (${state.message})`
  }
}
