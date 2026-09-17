import { useCallback, useEffect, useState } from 'react'

import { api, type Me, type RetroResult, type Session } from './api'
import { useIdleDetector, useInterval, useNow } from './hooks'
import { RetroForm } from './RetroForm'
import { formatDuration, liveFocusedSeconds } from './time'
import { TodayList } from './TodayList'

const HEARTBEAT_MS = 30_000
const IDLE_MS = 5 * 60_000

interface Props {
  me: Me
  refreshMe: () => Promise<void>
  onLogout: () => Promise<void>
}

export function Focus({ me, refreshMe, onLogout }: Props) {
  const [session, setSession] = useState<Session | null | undefined>(undefined)
  const [lastReward, setLastReward] = useState<RetroResult['reward'] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dayVersion, setDayVersion] = useState(0)
  const now = useNow(1000)

  const call = useCallback(async (fn: () => Promise<Session | undefined>) => {
    setError(null)
    try {
      const next = await fn()
      setSession(next ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void call(() => api.current())
  }, [call])

  const running = session?.status === 'running'
  useInterval(() => void call(() => api.heartbeat(session!.id)), HEARTBEAT_MS, running)
  useIdleDetector(running, IDLE_MS, () => void call(() => api.pause(session!.id, 'idle')))

  if (session === undefined) return <main>불러오는 중</main>

  const focused = session ? liveFocusedSeconds(session.focused_seconds, session.running_since, now) : 0
  const countdownLeft =
    session?.mode === 'countdown' && session.target_seconds ? session.target_seconds - focused : null

  return (
    <main>
      <header>
        <strong>{me.display_name}</strong> · 코인 {me.balance} · 연속 {me.streak_days}일 · 마을 XP{' '}
        {me.village.xp}
        <button onClick={() => void onLogout()}>로그아웃</button>
      </header>

      {error && <p role="alert">{error}</p>}

      {!session && <StartForm onStart={(data) => call(() => api.start(data))} />}

      {session && (session.status === 'running' || session.status === 'paused') && (
        <section aria-label="timer">
          {session.intent && <p>몰두 중: {session.intent}</p>}
          <p style={{ fontSize: '3rem', fontVariantNumeric: 'tabular-nums' }}>
            {formatDuration(focused)}
          </p>
          {countdownLeft !== null && (
            <p>{countdownLeft > 0 ? `남은 시간 ${formatDuration(countdownLeft)}` : '목표 시간 도달. 마무리하세요.'}</p>
          )}
          {session.status === 'paused' && (
            <p>
              일시정지됨
              {session.pause_reason === 'idle' && ' (자리를 비운 것 같아요)'}
              {session.pause_reason === 'timeout' && ' (연결이 끊겼어요)'}
            </p>
          )}
          {session.status === 'running' ? (
            <button onClick={() => void call(() => api.pause(session.id, 'user'))}>일시정지</button>
          ) : (
            <button onClick={() => void call(() => api.resume(session.id))}>다시 시작</button>
          )}
          <button onClick={() => void call(() => api.stop(session.id))}>종료</button>
        </section>
      )}

      {session && session.status === 'ended' && (
        <RetroForm
          session={session}
          onSubmitted={async (result) => {
            setLastReward(result.reward)
            setSession(null)
            setDayVersion((v) => v + 1)
            await refreshMe()
          }}
        />
      )}

      {lastReward && (
        <p role="status">
          +{lastReward.coins} 코인 (기본 {lastReward.base} × {lastReward.multiplier}
          {lastReward.cap_hit ? ', 일일 상한 도달' : ''}) · 연속 {lastReward.streak_days}일
        </p>
      )}

      <TodayList version={dayVersion + (session?.status ?? '')} />
    </main>
  )
}

function StartForm({
  onStart,
}: {
  onStart: (data: { mode: 'stopwatch' | 'countdown'; target_seconds?: number; intent?: string }) => Promise<void>
}) {
  const [mode, setMode] = useState<'stopwatch' | 'countdown'>('stopwatch')
  const [minutes, setMinutes] = useState(25)
  const [intent, setIntent] = useState('')
  return (
    <form
      aria-label="start"
      onSubmit={(e) => {
        e.preventDefault()
        void onStart({
          mode,
          target_seconds: mode === 'countdown' ? minutes * 60 : undefined,
          intent: intent.trim() || undefined,
        })
      }}
    >
      <label>
        <input type="radio" checked={mode === 'stopwatch'} onChange={() => setMode('stopwatch')} />
        스톱워치
      </label>
      <label>
        <input type="radio" checked={mode === 'countdown'} onChange={() => setMode('countdown')} />
        카운트다운
      </label>
      {mode === 'countdown' && (
        <label>
          분
          <input
            type="number"
            min={1}
            max={480}
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
          />
        </label>
      )}
      <input
        placeholder="무엇에 몰두할까요? (선택)"
        maxLength={120}
        value={intent}
        onChange={(e) => setIntent(e.target.value)}
      />
      <button type="submit">시작하기</button>
    </form>
  )
}
