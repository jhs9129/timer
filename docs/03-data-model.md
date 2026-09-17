# 03. 데이터 모델

모든 `*_at`은 `timestamptz`(UTC). PK는 `uuid`(현재 v4, 애플리케이션 생성. Python 3.11 표준 라이브러리에 v7이 없어 보류). `local_date`는 사용자 타임존 + 04:00 경계로 서버가 계산한 `date`. 상태를 가진 테이블은 `updated_at`을 두고 서비스가 갱신한다.

실제 스키마의 원본은 `apps/api/app/models/`와 `apps/api/alembic/versions/`다. 이 문서는 의도를 설명하고, 둘이 어긋나면 코드가 맞다.

## 사용자

### users
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| google_sub | text unique | Google OIDC subject |
| email | text unique | |
| display_name | text | |
| timezone | text | IANA. 기본 브라우저 감지값 |
| created_at | timestamptz | |

### consents
| 컬럼 | 타입 | 비고 |
|---|---|---|
| user_id | uuid FK | |
| kind | text | `analytics_basic`, `email_weekly`, 향후 `desktop_activity` 등 |
| granted_at | timestamptz | |
| revoked_at | timestamptz null | |

PK `(user_id, kind, granted_at)`.

## 세션

### focus_sessions
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| mode | text | `stopwatch` / `countdown` |
| target_seconds | int null | countdown일 때 |
| intent | text null | ≤120자 |
| status | text | `running` `paused` `ended` `completed` `abandoned` |
| pause_reason | text null | `user` `idle` `timeout` |
| local_date | date | 시작 시점 계산 |
| started_at | timestamptz | |
| ended_at | timestamptz null | stop 시각 |
| focused_seconds | int | stop 시 확정. 그 전엔 세그먼트 합으로 계산 |
| created_at | timestamptz | |

부분 유니크 인덱스: `(user_id) WHERE status IN ('running','paused')` → 동시 활성 세션 1개.

### session_segments
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| session_id | uuid FK | |
| started_at | timestamptz | start/resume 시각 |
| last_seen_at | timestamptz | 마지막 heartbeat |
| ended_at | timestamptz null | 닫힌 시각. timeout이면 = last_seen_at |
| end_reason | text null | `pause` `idle` `timeout` `stop` |

열린 세그먼트는 세션당 최대 1개(부분 유니크 `(session_id) WHERE ended_at IS NULL`).

## 회고

### retrospectives
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| session_id | uuid FK unique | |
| mood | smallint | 1~4 |
| intent_match | text null | `yes` `partly` `no` |
| note | text null | ≤300자 |
| submitted_at | timestamptz | |
| updated_at | timestamptz | |

### tags / retro_tags
- `tags(id, owner_user_id null, name, created_at)`. `owner_user_id`가 null이면 전역 기본 태그.
- `retro_tags(retro_id, tag_id)` PK 복합.

## 보상

### reward_config
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| effective_from | timestamptz | 가장 최근 행이 현재 값 |
| rate_per_minute | numeric | |
| daily_cap | int | 코인 |
| streak_multipliers | jsonb | 예 `{"3":1.1,"7":1.25,"30":1.5}` |
| created_at | timestamptz | |

### coin_ledger
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| delta | int | 양수 적립, 음수 사용 |
| kind | text | `session_reward` `purchase` `adjustment` |
| ref_type | text | `focus_session` `inventory` 등 |
| ref_id | uuid | |
| local_date | date | 일일 상한 계산용 |
| created_at | timestamptz | |

유니크 `(kind, ref_id)` → 멱등.

## 마을

### villages
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| owner_type | text | `user` / `guild` |
| owner_id | uuid | users.id 또는 guilds.id. FK는 걸지 않고 애플리케이션이 검증 |
| slug | text unique | 공개 URL |
| name | text | |
| width, height | smallint | 초기 16×16 |
| xp | bigint | 누적 focused_minutes |
| created_at | timestamptz | |

유니크 `(owner_type, owner_id)`. M1에서 사용자 생성 시 마을도 함께 만든다.

### village_levels
`(level smallint PK, xp_required bigint, width smallint, height smallint)`.

### items
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| code | text unique | `tree_oak_01` |
| name | text | |
| category | text | `building` `tree` `prop` `ground` |
| price | int | |
| width, height | smallint | 타일 |
| unlock_level | smallint | |
| active | bool | 판매 중 여부 |

### inventory
`(id, village_id FK, item_id FK, qty int)`, 유니크 `(village_id, item_id)`.

### placements
`(id, village_id FK, item_id FK, x, y smallint, rotation smallint, placed_at)`. 겹침 검증은 서버 로직.

## 알림

### push_subscriptions
`(id, user_id FK, endpoint text unique, p256dh text, auth text, user_agent text, created_at, revoked_at null)`.

### scheduled_notifications
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| kind | text | `countdown_reached` `retro_pending` `daily_reminder` `weekly_summary` |
| due_at | timestamptz | |
| payload | jsonb | |
| ref_type, ref_id | text, uuid null | 세션 등 |
| sent_at | timestamptz null | |
| cancelled_at | timestamptz null | |
| attempts | smallint | |
| last_error | text null | |

인덱스 `(due_at) WHERE sent_at IS NULL AND cancelled_at IS NULL`.

## 이벤트

### events
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| event_type | text | 아래 목록 |
| actor_id | uuid null | 사용자. 시스템이면 null |
| subject_type | text | `focus_session` `retrospective` `coin_ledger` … |
| subject_id | uuid | |
| payload | jsonb | 변경 전후 요약. PII 최소화 |
| occurred_at | timestamptz | 도메인 시각 |
| ingested_at | timestamptz default now() | |

인덱스 `(occurred_at)`, `(event_type, occurred_at)`, `(actor_id, occurred_at)`. 파티셔닝은 M4에서 월 단위로 검토.

### 이벤트 목록 (초기)

| event_type | 시점 | payload 예 |
|---|---|---|
| `session.started` | start | mode, target_seconds, has_intent |
| `session.paused` | pause | reason, focused_seconds_so_far |
| `session.resumed` | resume | paused_seconds |
| `session.stopped` | stop | focused_seconds, segment_count |
| `session.abandoned` | 배치 | last_status, focused_seconds |
| `retro.submitted` | 회고 | mood, intent_match, tag_count, has_note |
| `reward.granted` | 보상 | coins, base, multiplier, cap_hit |
| `item.purchased` | 구매 | item_code, price |
| `placement.changed` | 배치/이동/철거 | action, item_code, x, y |
| `notification.sent` | 디스패치 | kind, channel, ok |
| `reward_config.changed` | 설정 변경 | before, after |
| `consent.changed` | 동의 변경 | kind, granted |

heartbeat는 이벤트로 남기지 않는다(양이 많고 세그먼트가 이미 같은 정보를 담는다).

## 향후 (M4 이후)
- `guilds`, `guild_members`
- `external_weather_daily`, `external_holidays` (M4, 외부 데이터 결합)
- 이벤트 월별 파티션, Parquet 내보내기 워터마크 테이블
