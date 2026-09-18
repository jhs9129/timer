# 02. 서비스 프로세스

## 1. 집중 세션

### 1.1 상태 머신

```
idle ──start──▶ running ──pause / idle-detect / heartbeat timeout──▶ paused ──resume──▶ running
                  │                                                     │
                  └──────────────── stop ───────────────────────────────┘──▶ ended ──retro submit──▶ completed
                  │
                  └── 당일 경계(04:00, 사용자 TZ)까지 stop 없음 ──▶ abandoned
```

| 상태 | 의미 | 진입 조건 |
|---|---|---|
| `running` | 몰두 중. 활성 세그먼트가 열려 있다 | start, resume |
| `paused` | 일시정지. 활성 세그먼트가 닫혔다 | pause(사용자), idle(클라이언트 감지), timeout(서버 heartbeat 끊김) |
| `ended` | 사용자가 종료를 눌렀다. 회고 대기 | stop |
| `completed` | 회고까지 제출됐다. 보상 확정 | retro submit |
| `abandoned` | 당일 경계까지 stop 또는 회고 없음. 보상 0 | 배치 작업 |

규칙:
- 사용자당 동시에 `running` 또는 `paused`인 세션은 하나다. 새 start는 기존 세션이 `ended` 이상이어야 허용한다.
- `ended` 세션은 당일 경계 전까지 회고를 제출할 수 있다. 경계가 지나면 `abandoned`.
- `abandoned`는 되돌릴 수 없다. 회고도 받지 않는다.

### 1.2 모드

| 모드 | 동작 |
|---|---|
| `stopwatch` | 열린 시간. 사용자가 stop을 누를 때까지 |
| `countdown` | `target_seconds` 설정. 도달 시 알림. 자동 stop은 하지 않고 사용자가 stop을 누른다 |

카운트다운이 도달해도 자동으로 끝내지 않는 이유: 회고를 사용자가 자기 의지로 시작하게 하기 위해서다. 알림은 "이제 마무리하세요"이지 "끝났습니다"가 아니다.

### 1.3 시작 입력

- `mode`(필수), `target_seconds`(countdown일 때 필수)
- `intent`(선택, 120자): 무엇에 몰두할지 한 줄. 비어 있으면 회고에서 `intent_match`를 묻지 않는다.

### 1.4 시간 계산 (서버 권위)

- 클라이언트는 `running` 동안 30초 간격으로 `POST /sessions/{id}/heartbeat`를 보낸다.
- 서버는 세션당 `session_segments`를 관리한다. start/resume이 세그먼트를 열고, pause/stop이 닫는다. heartbeat는 열린 세그먼트의 `last_seen_at`을 갱신한다.
- heartbeat가 `HEARTBEAT_TIMEOUT`(기본 90초) 넘게 없으면 서버가 세그먼트를 `last_seen_at`에 닫고 세션을 `paused(reason=timeout)`으로 바꾼다. 이 판정은 다음 요청 처리 시 또는 1분 크론에서 lazy하게 수행한다.
- `focused_seconds = Σ (segment.ended_at − segment.started_at)`.
- 클라이언트가 보낸 어떤 시각·경과값도 집계에 쓰지 않는다. 클라이언트 표시용 타이머는 서버의 `focused_seconds`와 `running_since`를 받아 로컬에서 그린다.

### 1.5 유휴 감지 (클라이언트)

- 탭이 `hidden`이 되거나 입력(키보드·마우스·터치)이 `IDLE_MINUTES`(기본 5분) 동안 없으면 클라이언트가 `POST /sessions/{id}/pause {reason: "idle"}`을 보낸다.
- 다시 입력이 감지되면 자동 resume하지 않는다. 사용자에게 "다시 시작할까요?"를 묻는다.
- 탭을 열어둔 채 방치하면 유휴 감지 전까지는 누적된다. 이것은 의도된 정책이다(비전 문서의 비목적 참고).

### 1.6 당일 경계

- 사용자 프로필의 타임존 기준 04:00이 하루의 시작이다. 03:59에 시작한 세션의 `local_date`는 전날이다.
- 세션의 `local_date`는 시작 시점에 서버가 계산해 저장한다. 이후 타임존을 바꿔도 과거 값은 바뀌지 않는다.
- **heartbeat가 살아 있는 `running` 세션은 경계를 넘어도 유지된다.** 03:30에 시작해 05:00까지 몰두한 세션은 끊기지 않고, `local_date`는 전날로 남아 전날의 상한에 포함된다.
- 경계를 넘긴 `paused`/`ended` 세션은 마지막 변경으로부터 30분의 유예가 지나면 크론이 `abandoned`로 바꾼다. 유예는 03:55에 종료하고 04:10에 회고하는 경우를 살리기 위한 것이다.
- 회고 요청이 유예를 넘긴 세션에 도착하면 그 자리에서 `abandoned` 처리하고 409를 돌려준다.

## 2. 회고

- `ended` 직후 같은 화면에서 회고 폼을 띄운다. 화면 전환 없음.
- 필수: `mood`(1~4), `intent_match`(`yes|partly|no`, intent가 있을 때만).
- 선택: `tags`(다중, 사용자 정의 가능), `note`(300자).
- 제출 → 세션 `completed` → 보상 계산 → `coin_ledger` 기록. 이 셋은 한 트랜잭션이다.
- 회고는 세션당 하나. 수정은 당일 경계 전까지 허용하되 보상은 재계산하지 않는다.

## 3. 보상

### 3.1 코인

```
base   = floor(focused_minutes × rate_per_minute)
coins  = min(base × streak_multiplier(streak_days), remaining_daily_cap)
```

- `rate_per_minute`, `daily_cap`, `streak_multipliers`는 `reward_config`의 현재 유효 행에서 읽는다.
- `remaining_daily_cap = daily_cap − (해당 local_date에 이미 지급된 session_reward 합)`.
- `coin_ledger`에 `(kind=session_reward, ref_id=session_id)` 유니크 제약으로 멱등성을 보장한다.
- 잔액 = `Σ coin_ledger.delta`. 별도 잔액 컬럼을 두지 않는다(M2에서 성능 문제가 보이면 그때 캐시).

### 3.2 연속 일수

- `streak_days` = 오늘을 포함해 "completed 세션이 1개 이상인 날"이 연속된 수.
- 하루 빠지면 0으로 돌아간다. 회복 아이템 같은 완화 장치는 M5 이후에 논의한다.

### 3.3 마을 XP

- 마을 XP = 그 마을 소유자(들)의 누적 `focused_minutes` 합. 코인과 독립.
- 레벨 구간은 `village_levels` 테이블. 레벨은 상점 해금 조건으로만 쓴다.

## 4. 마을

- 격자 맵. 초기 크기 16×16. 레벨업으로 확장.
- 아이템 카탈로그 `items`: 코드, 카테고리(building, tree, prop, ground), 가격, 크기(w×h 타일), 해금 레벨.
- 구매: 잔액 확인 → `coin_ledger(kind=purchase, delta<0)` → `inventory` 증가. 한 트랜잭션.
- 배치: `inventory`에서 꺼내 `placements`에 기록. 겹침·경계 검증은 서버. 철거하면 인벤토리로 돌아간다(환불 없음).
- 레이어: `ground` 아이템은 ground 레이어, 나머지는 object 레이어. 겹침은 같은 레이어 안에서만 검사한다. 잔디 위에 나무는 되고 나무 위에 나무는 안 된다.
- 레벨은 `village_levels`에서 계산하고 저장하지 않는다. 레벨업 시 `villages.width/height`만 새 크기로 키운다.
- 공개 URL `/v/{slug}`는 로그인 없이 읽기 가능. 편집은 소유자만.
- 소유자는 `owner_type ∈ {user, guild}`. M1~M4는 user만 존재하지만 스키마는 처음부터 이 형태다.

## 5. 알림

| 종류 | 채널 | 트리거 |
|---|---|---|
| 카운트다운 도달 | 탭 열림: Notification API 즉시. 탭 닫힘: Web Push | 세션 start 시 `scheduled_notifications`에 due_at 예약 |
| 회고 미완료 | Web Push | `ended` 후 30분 경과, 아직 `completed` 아님 |
| 일일 리마인더 | Web Push | 사용자 설정 시각. 기본 off |
| 주간 요약 | 이메일 | 매주 월요일 08:00 사용자 TZ |

- 서버 푸시 디스패치: 외부 크론이 1분마다 `POST /internal/dispatch` (헤더 `X-Cron-Secret`). 서버는 `due_at <= now AND sent_at IS NULL`을 처리하고 결과를 기록한다.
- 세션이 stop되면 관련 예약은 취소(`cancelled_at`)한다.
- iOS Safari는 홈 화면 추가(PWA) 상태에서만 푸시가 온다. 푸시 권한 요청 전에 이 안내를 보여준다.

## 6. API 스케치 (M1 범위)

```
POST   /auth/google/start            → Google OAuth 리다이렉트
GET    /auth/google/callback         → 세션 쿠키 발급
POST   /auth/logout
GET    /me                           → 프로필, 타임존, 잔액, streak

POST   /sessions                     {mode, target_seconds?, intent?}
GET    /sessions/current
POST   /sessions/{id}/heartbeat
POST   /sessions/{id}/pause          {reason: "user"|"idle"}
POST   /sessions/{id}/resume
POST   /sessions/{id}/stop
POST   /sessions/{id}/retro          {mood, intent_match?, tags?, note?}
GET    /sessions?date=YYYY-MM-DD     → 하루 목록

POST   /internal/dispatch            (크론 전용)
GET    /health
```

모든 응답 시각은 UTC ISO 8601. 클라이언트가 로컬로 변환한다.
