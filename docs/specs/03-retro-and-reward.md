# 03. 회고와 보상

상태: implemented
관련 ADR: 0003
관련 문서: `docs/02-process.md` §2, §3

## 목적

회고를 보상의 조건으로 묶어 "몰두 → 되돌아봄"이 한 동작이 되게 한다. 보상은 서버가 설정 테이블에서 읽은 상수로 계산하고 원장에 멱등 기록한다.

## 범위

포함:
- 회고 제출 → `completed` → 코인 지급, 마을 XP 가산. 한 트랜잭션
- 일일 상한, 연속 일수 배수
- 잔액·연속 일수 조회(`/me`)

제외:
- 회고 수정 UI, 태그 관리 API(태그는 문자열 배열로 받아 upsert)
- 코인 사용(구매)은 M2

## 흐름

1. `ended` 세션에 `POST /sessions/{id}/retro`.
2. `intent`가 있으면 `intent_match` 필수. 없으면 무시.
3. 세션이 경계를 넘긴 채 유예(30분)도 지났으면 `abandoned`로 바꾸고 409.
4. 회고 저장 → 세션 `completed` → streak 계산 → 보상 계산 → `coin_ledger` 삽입 → 마을 XP += focused_minutes → 이벤트 3종.

보상 산식:
```
base      = floor(focused_minutes × rate_per_minute)
raw       = floor(base × multiplier(streak_days))
coins     = clamp(raw, 0, daily_cap − 오늘 이미 지급된 session_reward 합)
```
`multiplier`는 `streak_multipliers`에서 streak 이하의 가장 큰 키의 값, 없으면 1.0.
`streak_days`는 오늘(이 세션의 `local_date`)을 포함해 `completed` 세션이 있는 날이 연속된 수.

## API

```
POST /sessions/{id}/retro {mood: 1..4, intent_match?: yes|partly|no, tags?: [str], note?: str}
  → 201 {retro: RetroOut, reward: {coins, base, multiplier, cap_hit}, session: SessionOut}
  ; ended 아니면 409 ; intent 있는데 intent_match 없으면 422 ; 이미 회고 있으면 409
```

## 스키마 변경

`retrospectives`, `tags`, `retro_tags`, `reward_config`(시드 1행), `coin_ledger`.

## 이벤트

`retro.submitted` {mood, intent_match, tag_count, has_note}
`reward.granted` {coins, base, multiplier, cap_hit, streak_days}
`village.xp_added` {minutes, xp}

## 수용 기준

- [x] AC1. 10분 몰두한 `ended` 세션에 회고를 내면 `completed`가 되고 코인 10(rate 1.0)이 원장에 기록된다.
- [x] AC2. `running` 세션에 회고를 내면 409다.
- [x] AC3. intent가 있는 세션에 `intent_match` 없이 내면 422다. intent가 없으면 필요 없다.
- [x] AC4. 같은 세션에 두 번 내면 409이고 원장은 한 행이다.
- [x] AC5. 하루 지급 합이 `daily_cap`을 넘지 않는다. 넘치는 세션은 남은 만큼만 받고 `cap_hit=true`다.
- [x] AC6. 3일 연속 완료하면 3일째 배수가 1.1이다.
- [x] AC7. 회고 후 마을 XP가 focused_minutes만큼 는다.
- [x] AC8. 경계와 유예를 넘긴 `ended` 세션에 회고를 내면 `abandoned`가 되고 409다.
- [x] AC9. `/me`의 balance는 원장 합과 같다.

## 메모

- 회고 수정은 API만 열어 둔다(`PUT`은 M2 UI와 함께). 보상은 재계산하지 않는다.
- 초기 설정값: rate 1.0/분, daily_cap 300, 배수 {3: 1.1, 7: 1.25, 30: 1.5}. 운영 중 조정은 새 행 삽입으로.
