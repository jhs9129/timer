import { useEffect, useState } from 'react'

import { api, type Day } from './api'
import { formatDuration } from './time'

const STATUS_LABEL: Record<string, string> = {
  running: '진행 중',
  paused: '일시정지',
  ended: '회고 대기',
  completed: '완료',
  abandoned: '미완료',
}

export function TodayList({ version }: { version: string | number }) {
  const [day, setDay] = useState<Day | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .day()
      .then((d) => {
        if (!cancelled) setDay(d)
      })
      .catch(() => {
        if (!cancelled) setDay(null)
      })
    return () => {
      cancelled = true
    }
  }, [version])

  if (!day) return null
  return (
    <section aria-label="today">
      <h2>오늘 ({day.date})</h2>
      <p>
        몰두 {formatDuration(day.focused_seconds)} · 코인 +{day.coins_earned}
      </p>
      <ul>
        {day.sessions.map((s) => (
          <li key={s.id}>
            {formatDuration(s.focused_seconds)} · {STATUS_LABEL[s.status] ?? s.status}
            {s.intent ? ` · ${s.intent}` : ''}
          </li>
        ))}
      </ul>
    </section>
  )
}
