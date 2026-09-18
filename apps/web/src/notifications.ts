import { notificationApi } from './api'

export type PushSupport =
  | { kind: 'supported' }
  | { kind: 'unsupported'; reason: string }
  | { kind: 'ios_needs_install' }

/** iOS Safari only delivers Web Push to sites added to the home screen (standalone PWA). */
export function detectPushSupport(
  nav: Navigator = navigator,
  win: Window & { MSStream?: unknown } = window,
): PushSupport {
  const isIOS = /iPad|iPhone|iPod/.test(nav.userAgent) && !win.MSStream
  const standalone =
    ('standalone' in nav && Boolean((nav as Navigator & { standalone?: boolean }).standalone)) ||
    (typeof win.matchMedia === 'function' && win.matchMedia('(display-mode: standalone)').matches)
  if (isIOS && !standalone) return { kind: 'ios_needs_install' }
  if (!('serviceWorker' in nav)) return { kind: 'unsupported', reason: 'service worker 미지원' }
  if (!('PushManager' in win)) return { kind: 'unsupported', reason: '푸시 미지원 브라우저' }
  if (!('Notification' in win)) return { kind: 'unsupported', reason: '알림 미지원 브라우저' }
  return { kind: 'supported' }
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null
  try {
    return await navigator.serviceWorker.register('/sw.js')
  } catch {
    return null
  }
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'))
  const out = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i)
  return out
}

/** Ask permission, subscribe with the server's VAPID key and register the subscription. */
export async function enablePush(): Promise<{ ok: true } | { ok: false; reason: string }> {
  const support = detectPushSupport()
  if (support.kind !== 'supported') {
    return { ok: false, reason: support.kind === 'ios_needs_install' ? 'iPhone에서는 홈 화면에 추가한 뒤 켤 수 있어요.' : support.reason }
  }
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return { ok: false, reason: '알림 권한이 거부되었어요.' }
  const registration = (await registerServiceWorker()) ?? (await navigator.serviceWorker.ready)
  const { key } = await notificationApi.vapidKey()
  if (!key) return { ok: false, reason: '서버에 푸시 키가 설정되지 않았어요.' }
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    }))
  const json = subscription.toJSON()
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
    return { ok: false, reason: '구독 정보를 만들지 못했어요.' }
  }
  await notificationApi.addPushSubscription({
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent.slice(0, 256),
  })
  return { ok: true }
}

export async function disablePush(): Promise<void> {
  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.getRegistration()
    const subscription = await registration?.pushManager.getSubscription()
    if (subscription) {
      await notificationApi.removePushSubscription(subscription.endpoint).catch(() => undefined)
      await subscription.unsubscribe()
    }
  }
  await notificationApi.patchPrefs({ push: false })
}

/** Local notification while the tab is open. The server push is the backup for closed tabs. */
export function notifyLocally(title: string, body: string): void {
  if (!('Notification' in window) || Notification.permission !== 'granted') return
  try {
    new Notification(title, { body })
  } catch {
    // Some browsers only allow notifications from the service worker; the push path covers those.
  }
}
