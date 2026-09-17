import { useState } from 'react'

import { api, type RetroInput, type RetroResult, type Session } from './api'
import { formatDuration } from './time'

const MOODS: { value: 1 | 2 | 3 | 4; label: string }[] = [
  { value: 1, label: '아쉬워요' },
  { value: 2, label: '보통이에요' },
  { value: 3, label: '잘했어요' },
  { value: 4, label: '최고예요' },
]

export function RetroForm({
  session,
  onSubmitted,
}: {
  session: Session
  onSubmitted: (result: RetroResult) => Promise<void>
}) {
  const [mood, setMood] = useState<1 | 2 | 3 | 4 | null>(null)
  const [intentMatch, setIntentMatch] = useState<'yes' | 'partly' | 'no' | null>(null)
  const [tags, setTags] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const needsIntent = Boolean(session.intent)
  const ready = mood !== null && (!needsIntent || intentMatch !== null)

  return (
    <form
      aria-label="retro"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!ready || mood === null) return
        setBusy(true)
        setError(null)
        const input: RetroInput = {
          mood,
          intent_match: needsIntent && intentMatch ? intentMatch : undefined,
          tags: tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean),
          note: note.trim() || undefined,
        }
        try {
          await onSubmitted(await api.retro(session.id, input))
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err))
        } finally {
          setBusy(false)
        }
      }}
    >
      <h2>회고</h2>
      <p>{formatDuration(session.focused_seconds)} 몰두했어요. 어땠나요?</p>
      <div role="radiogroup" aria-label="mood">
        {MOODS.map((m) => (
          <button
            key={m.value}
            type="button"
            aria-pressed={mood === m.value}
            onClick={() => setMood(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>
      {needsIntent && (
        <div role="radiogroup" aria-label="intent">
          <p>"{session.intent}"에 몰두했나요?</p>
          {(
            [
              ['yes', '네'],
              ['partly', '일부만'],
              ['no', '아니요'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={intentMatch === value}
              onClick={() => setIntentMatch(value)}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <input
        placeholder="태그 (쉼표로 구분, 선택)"
        value={tags}
        onChange={(e) => setTags(e.target.value)}
      />
      <textarea
        placeholder="한 줄 메모 (선택)"
        maxLength={300}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={!ready || busy}>
        회고 완료하고 보상 받기
      </button>
    </form>
  )
}
