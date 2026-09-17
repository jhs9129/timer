import { useState } from 'react'

import { api, googleLoginUrl } from './api'

export function Login({ onLoggedIn }: { onLoggedIn: () => Promise<void> }) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  return (
    <main>
      <h1>My Little Village</h1>
      <p>몰두한 시간을 기록하고, 되돌아보고, 마을을 가꿉니다.</p>
      <a href={googleLoginUrl}>
        <button>Google로 시작하기</button>
      </a>
      {import.meta.env.DEV && (
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            setError(null)
            try {
              await api.devLogin(email)
              await onLoggedIn()
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err))
            }
          }}
        >
          <h2>개발용 로그인</h2>
          <input
            type="email"
            placeholder="dev@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button type="submit">dev-login</button>
          {error && <p role="alert">{error}</p>}
        </form>
      )}
    </main>
  )
}
