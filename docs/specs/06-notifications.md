# 06. 알림: 예약, Web Push, 주간 이메일

상태: implemented
관련 ADR: 0005
관련 문서: `docs/02-process.md` §5, `docs/specs/04-dispatch-batch.md`

## 목적

탭이 닫혀 있어도 "이제 마무리하세요"와 "회고를 남기세요"가 도착하게 한다. 알림은 몰두를 돕는 최소한만 둔다. 마케팅성 알림은 만들지 않는다.

## 범위

포함:
- `scheduled_notifications` 큐와 `/internal/dispatch`의 발송 단계
- Web Push(VAPID) 구독 등록·해제, 푸시 동의
- 카운트다운 도달, 회고 대기, 일일 리마인더(선택), 주간 요약 이메일(동의 시)
- 발송 어댑터 분리: 운영(pywebpush, Resend) / 미설정(logging) / 테스트(recording)

제외:
- SMS(유료), 앱 내 알림함
- 이메일 수신 확인·클릭 추적

## 흐름

| kind | 채널 | 예약 | 취소 | dedupe_key |
|---|---|---|---|---|
| `countdown_reached` | push | countdown start 시 `due = now + target_seconds` | stop, abandon | 없음 |
| `retro_pending` | push | stop 시 `due = now + 30분` | retro submit, abandon | 없음 |
| `daily_reminder` | push | 크론 tick에서 사용자 로컬 시각이 `reminder_local_time` 이후 10분 창 안이면 즉시 | 설정 해제 | `daily:{user}:{local_date}` |
| `weekly_summary` | email | 월요일 08:00 로컬 이후 10분 창 | 동의 철회 | `weekly:{user}:{iso_year}-W{iso_week}` |

- 발송: `due_at <= now AND sent_at IS NULL AND cancelled_at IS NULL AND attempts < 5`를 `due_at` 순으로 최대 N건. 성공 → `sent_at`; 실패 → `attempts += 1, last_error`. 이벤트 `notification.sent {kind, channel, ok, error}`.
- 푸시는 사용자의 모든 활성 구독에 보낸다. 하나라도 성공하면 ok. 엔드포인트가 404/410이면 그 구독을 `revoked_at`. 활성 구독이 없으면 재시도 없이 `no subscription`으로 종료.
- 푸시 동의(`consents.kind = push`)를 철회하면 모든 구독을 revoke하고 대기 중인 push 알림을 취소한다.
- 탭이 열려 있으면 클라이언트가 즉시 `Notification`을 띄운다. 서버는 이를 모르므로 **중복 알림을 허용한다**. 사용자가 두 번 보는 것이 못 보는 것보다 낫다.
- 어댑터: `VAPID_PRIVATE_KEY`가 없으면 push는 `LoggingSender`(ok=False, `not configured`). `RESEND_API_KEY`가 없으면 email도 같다. 이 경우에도 큐·이벤트는 정상 동작하므로 개발 환경에서 흐름을 확인할 수 있다.

## API

```
GET    /push/vapid-public-key                → {key}
POST   /push/subscriptions {endpoint, keys{p256dh, auth}, user_agent?} → 201 {id} ; 같은 endpoint면 갱신·복구
DELETE /push/subscriptions?endpoint=          → 204
GET    /me/notifications                     → {push, email_weekly, reminder_local_time}
PATCH  /me/notifications {push?, email_weekly?, reminder_local_time?: "HH:MM"|null} → 동일 ; 형식 오류 422
POST   /internal/dispatch                    → {timed_out, abandoned, scheduled, sent, failed}
```

## 스키마 변경

`users.reminder_local_time time null`, `consents`, `push_subscriptions`, `scheduled_notifications`(`channel`, `dedupe_key` 추가). `docs/03-data-model.md` 갱신.

## 이벤트

- `notification.scheduled` {kind, channel, due_at}
- `notification.cancelled` {kind, reason}
- `notification.sent` {kind, channel, ok, error}
- `consent.changed` {kind, granted}
- `push_subscription.changed` {action: add|remove|revoke}

## 수용 기준

- [x] AC1. countdown 세션을 시작하면 `countdown_reached`가 `started_at + target_seconds`에 예약되고, stop하면 취소된다.
- [x] AC2. stop하면 `retro_pending`이 30분 뒤로 예약되고, 회고를 내면 취소된다. abandon되면 두 종류 모두 취소된다.
- [x] AC3. 구독을 등록하면 201, 같은 endpoint를 다시 등록하면 키가 갱신되고 행은 하나다. 삭제하면 revoked.
- [x] AC4. due에 도달한 push 알림은 dispatch에서 RecordingSender로 1회 발송되고 `sent_at`이 찍히며 `notification.sent ok=true`가 기록된다. due 전에는 발송되지 않는다.
- [x] AC5. 발송 실패 시 attempts가 늘고 5회 후에는 더 시도하지 않는다.
- [x] AC6. 엔드포인트가 410을 돌려주면 구독이 revoked되고 알림은 `no subscription`으로 실패한다.
- [x] AC7. `reminder_local_time=10:00`인 사용자는 10:00 KST tick에서 리마인더 1건이 생성·발송되고, 같은 날 재tick에서는 중복되지 않으며, 다음 날 다시 생성된다.
- [x] AC8. `email_weekly` 동의한 사용자는 월요일 08:00 KST tick에서 이메일 1건을 받고 본문에 지난 7일 몰두 분·세션 수·코인이 들어 있다. 동의가 없으면 발송되지 않는다.
- [x] AC9. 잘못된 `reminder_local_time`은 422다.
- [x] AC10. 푸시 동의를 철회하면 대기 중인 push 알림이 취소되고 구독이 revoked된다.

## 메모

- iOS Safari는 홈 화면에 추가한 PWA에서만 푸시가 온다. 클라이언트가 이를 감지해 안내한다(`src/notifications.ts`).
- VAPID 키는 `make vapid-keys`로 만든다. 운영 환경 변수에 넣고 저장소에는 넣지 않는다.
- 주간 요약 발송에는 Resend에서 도메인 인증이 필요하다. 인증 전에는 Resend가 계정 소유자 주소로만 보내 준다.
