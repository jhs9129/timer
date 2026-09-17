# 02. 집중 세션 상태 머신과 heartbeat

상태: implemented
관련 ADR: 0002, 0003
관련 문서: `docs/02-process.md` §1

## 목적

몰두 시간의 진실을 서버가 갖게 한다. 클라이언트는 의도(start/pause/resume/stop)와 생존 신호(heartbeat)만 보낸다.

## 범위

포함:
- `running` `paused` `ended` 전이, 세그먼트 관리, heartbeat timeout(lazy)
- `local_date` 계산(사용자 TZ, 04:00 경계)
- 하루 세션 목록 조회

제외:
- 회고·보상 → 스펙 03
- 크론 배치(timeout 일괄, abandon) → 스펙 04
- 알림 예약 → M3

## 흐름

| 현재 | 요청 | 다음 | 부수효과 |
|---|---|---|---|
| 없음 | start | running | 세그먼트 열기, `session.started` |
| running | heartbeat | running | 열린 세그먼트 `last_seen_at = now` |
| running | pause(user/idle) | paused | 세그먼트 `ended_at = now`, `session.paused` |
| running (heartbeat 90초 이상 끊김) | 아무 요청 | paused(timeout) | 세그먼트 `ended_at = last_seen_at`, `session.paused` |
| paused | resume | running | 새 세그먼트, `session.resumed` |
| running/paused | stop | ended | 세그먼트 닫기, `focused_seconds` 확정, `session.stopped` |
| ended/completed/abandoned | heartbeat/pause/resume/stop | 409 | |

- timeout 판정은 세션을 읽는 모든 요청에서 먼저 적용한다(lazy). 크론이 일괄 처리도 한다(스펙 04).
- `focused_seconds = Σ(ended_at − started_at)`. timeout으로 닫힌 세그먼트는 `last_seen_at`까지만 센다.
- `local_date`는 start 시점에 `(now in user TZ − 4h).date()`.

## API

```
POST /sessions {mode, target_seconds?, intent?}   → 201 SessionOut ; 활성 세션 있으면 409 ; countdown인데 target 없으면 422
GET  /sessions/current                            → 200 SessionOut | 204
POST /sessions/{id}/heartbeat                     → 200 SessionOut ; ended 이후 409
POST /sessions/{id}/pause {reason}                → 200 ; running 아니면 409
POST /sessions/{id}/resume                        → 200 ; paused 아니면 409
POST /sessions/{id}/stop                          → 200 ; running/paused 아니면 409
GET  /sessions?date=YYYY-MM-DD                    → 200 DayOut
```

`SessionOut = {id, mode, target_seconds, intent, status, pause_reason, local_date, started_at, ended_at, focused_seconds, running_since, has_retro}`
`running_since`는 열린 세그먼트의 `started_at`. 클라이언트는 `focused_seconds + (now − running_since)`로 화면 타이머를 그린다.

## 스키마 변경

`focus_sessions`, `session_segments`.

## 이벤트

`session.started` `session.paused` `session.resumed` `session.stopped`.

## 수용 기준

- [x] AC1. start하면 `running` 세션과 열린 세그먼트가 하나 생기고 `session.started`가 기록된다.
- [x] AC2. 활성 세션이 있는데 start하면 409다.
- [x] AC3. countdown 모드인데 `target_seconds`가 없으면 422다.
- [x] AC4. 서버 시각이 60초 흐른 뒤 stop하면 `focused_seconds`는 60이다. 클라이언트가 보낸 값은 없다.
- [x] AC5. pause 후 시간이 흘러도 `focused_seconds`는 늘지 않고, resume 후에는 다시 는다.
- [x] AC6. 마지막 heartbeat로부터 90초를 넘긴 뒤 요청이 오면 세션은 `paused(timeout)`이고 시간은 마지막 heartbeat까지만 센다.
- [x] AC7. `ended` 세션에 heartbeat/pause/resume/stop을 보내면 409다.
- [x] AC8. Asia/Seoul 03:59에 시작한 세션의 `local_date`는 전날이다.
- [x] AC9. 다른 사용자의 세션에 접근하면 404다.
- [x] AC10. `GET /sessions?date=`는 그 날짜의 세션과 합계를 돌려준다.

## 메모

- 실행 중인 세션은 경계를 넘어도 살아 있다. 경계 처리는 heartbeat가 끊긴 뒤에 일어난다(스펙 04). `docs/02-process.md`의 당일 경계 절을 이에 맞게 갱신했다.
