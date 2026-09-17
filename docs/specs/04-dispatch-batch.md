# 04. 크론 디스패치: timeout 일괄 처리와 abandon

상태: implemented
관련 ADR: 0005
관련 문서: `docs/02-process.md` §1.4, §1.6, `docs/04-deployment.md`

## 목적

무료 인스턴스 1개에서 워커 없이 배치를 돌린다. 외부 크론이 1분마다 호출하는 엔드포인트 하나가 timeout 판정과 abandon 처리를 수행한다. 알림 발송은 M3에서 같은 엔드포인트에 추가한다.

## 범위

포함:
- `POST /internal/dispatch` (헤더 `X-Cron-Secret`)
- heartbeat가 끊긴 `running` 세션 → `paused(timeout)`
- 경계를 넘기고 유예(30분)가 지난 `paused`/`ended` 세션 → `abandoned`
- 처리 건수 상한(기본 200)과 결과 카운트 응답

제외:
- 알림 발송 → M3

## 흐름

1. 시크릿 검증. 불일치 401.
2. timeout: 열린 세그먼트 `last_seen_at < now − 90s`인 `running` 세션을 최대 N건 `paused(timeout)`.
3. abandon: `status ∈ {paused, ended}` 이고 `updated_at < now − 30분`인 세션 중, 사용자 TZ 기준 오늘 `local_date`보다 `session.local_date`가 작은 것을 최대 N건 `abandoned`. 열린 세그먼트가 있으면 `last_seen_at`에 닫는다.
4. `{timed_out: n, abandoned: m}` 반환. 30초 안에 끝나야 한다.

## API

```
POST /internal/dispatch   헤더 X-Cron-Secret   → 200 {timed_out, abandoned} ; 401
```

## 이벤트

`session.paused` {reason: timeout}, `session.abandoned` {last_status, focused_seconds}

## 수용 기준

- [x] AC1. 시크릿이 틀리면 401이고 아무것도 바뀌지 않는다.
- [x] AC2. heartbeat가 90초 넘게 끊긴 `running` 세션이 `paused(timeout)`이 되고 시간은 마지막 heartbeat까지만 센다.
- [x] AC3. 전날 `ended`로 남은 세션이 경계+유예 뒤 `abandoned`가 되고 `session.abandoned`가 기록된다.
- [x] AC4. heartbeat가 살아 있는 `running` 세션은 경계를 넘어도 그대로다.
- [x] AC5. 방금 `ended`된(유예 안 지난) 세션은 경계를 넘었어도 abandon되지 않는다.

## 메모

- 사용자 TZ별 "오늘"은 세션마다 사용자 행을 조인해 계산한다. 사용자 수가 커지면 TZ별로 묶어 처리한다.
