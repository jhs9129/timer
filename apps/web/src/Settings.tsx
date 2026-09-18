import { useEffect, useState } from 'react'

import { notificationApi, type NotificationPrefs } from './api'
import { detectPushSupport, disablePush, enablePush } from './notifications'

export function Settings({ onClose }: { onClose: () => void }) {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const support = detectPushSupport()

  useEffect(() => {
    notificationApi
      .prefs()
      .then(setPrefs)
      .catch((err: unknown) => setMessage(err instanceof Error ? err.message : String(err)))
  }, [])

  if (!prefs) return <section aria-label="settings">{message ?? '설정을 불러오는 중'}</section>

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setMessage(null)
    try {
      await fn()
      setPrefs(await notificationApi.prefs())
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="settings">
      <h2>알림 설정</h2>
      <p>
        <label>
          <input
            type="checkbox"
            checked={prefs.push}
            disabled={busy || support.kind === 'unsupported'}
            onChange={(e) =>
              void run(async () => {
                if (e.target.checked) {
                  const result = await enablePush()
                  if (!result.ok) setMessage(result.reason)
                } else {
                  await disablePush()
                }
              })
            }
          />
          브라우저 푸시 (카운트다운 도달, 회고 대기)
        </label>
        {support.kind === 'ios_needs_install' && (
          <span> · iPhone은 공유 → "홈 화면에 추가" 후 켤 수 있어요.</span>
        )}
        {support.kind === 'unsupported' && <span> · {support.reason}</span>}
      </p>
      <p>
        <label>
          매일 리마인더 시각
          <input
            type="time"
            value={prefs.reminder_local_time?.slice(0, 5) ?? ''}
            disabled={busy || !prefs.push}
            onChange={(e) =>
              void run(() =>
                notificationApi.patchPrefs({ reminder_local_time: e.target.value || null }).then(() => undefined),
              )
            }
          />
        </label>
        {!prefs.push && <span> · 푸시를 켜면 쓸 수 있어요.</span>}
      </p>
      <p>
        <label>
          <input
            type="checkbox"
            checked={prefs.email_weekly}
            disabled={busy}
            onChange={(e) =>
              void run(() =>
                notificationApi.patchPrefs({ email_weekly: e.target.checked }).then(() => undefined),
              )
            }
          />
          월요일 아침 주간 요약 이메일
        </label>
      </p>
      {message && <p role="alert">{message}</p>}
      <button type="button" onClick={onClose}>
        닫기
      </button>
    </section>
  )
}
