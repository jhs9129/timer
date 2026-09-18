# My Little Village

몰두(집중)를 돕는 서비스. 사용자는 타이머로 몰두 세션을 기록하고, 세션 종료 후 회고를 남기며, 그 대가로 얻은 코인으로 자기 마을을 꾸민다.
**핵심 목적은 몰두다. 보상과 마을은 몰두를 지속시키는 수단이다.** 기능을 판단할 때 항상 이 순서를 지킨다.

## 문서 먼저 읽기

| 문서 | 내용 |
|---|---|
| `docs/01-vision.md` | 목적, 비목적, 설계 원칙 |
| `docs/02-process.md` | 세션 상태 머신, 회고, 보상, 마을, 알림 흐름 |
| `docs/03-data-model.md` | 테이블·이벤트 정의 |
| `docs/04-deployment.md` | 무비용 배포 조합과 제약 |
| `docs/05-harness.md` | AI와 함께 일하는 방식, 스펙 템플릿, 검증 루프 |
| `docs/adr/` | 결정 기록. 뒤집으려면 새 ADR을 쓴다 |
| `docs/specs/` | 기능별 스펙. 구현 전에 먼저 작성 |

## 구조와 스택

```
apps/api    FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, Python 3.11, uv
apps/web    React 19, Vite, TypeScript, Vitest
infra/      docker-compose (local Postgres 16)
docs/       위 표 참고
data/       (M4) dbt-duckdb 파이프라인. 아직 없음
```

## 명령

```
make setup      # uv sync + npm ci
make db-up      # 로컬 Postgres 기동
make dev-api    # uvicorn --reload (http://localhost:8000)
make dev-web    # vite (http://localhost:5173)
make check      # ruff + mypy + pytest + eslint + tsc + vitest. 커밋 전 필수
make test       # 테스트만
make migrate    # alembic upgrade head
make vapid-keys # Web Push 키 쌍 출력 (한 번만, 시크릿으로 보관)
```

알림 발송 어댑터는 `app.state.senders`에 있다. 키가 없으면 로그만 남기는 어댑터가 들어가고, 테스트는 `RecordingSender`로 바꾼다. 서비스 코드는 pywebpush나 httpx를 직접 부르지 않는다.

API 테스트는 실제 Postgres를 요구한다. 로컬은 `make db-up` 후 `village_test` DB를 테스트가 스스로 만들고 마이그레이션한다. CI는 Postgres 서비스 컨테이너를 띄운다. DB 없이 "통과"하는 테스트는 없다.

시간은 `app/services/clock.py`의 `now()` 하나로만 읽는다. 테스트는 `fake_clock` 픽스처로 이 함수를 바꿔 시간을 제어한다. `datetime.now()`를 직접 호출하지 않는다.

## 절대 규칙

1. **시간은 서버가 계산한다.** 클라이언트가 보낸 경과 시간, 시작 시각, 종료 시각을 집계에 쓰지 않는다. heartbeat 수신 시각으로 세그먼트를 만든다.
2. **상태 변경은 이벤트를 동반한다.** 도메인 테이블을 쓰는 트랜잭션 안에서 `events`에 한 행을 넣는다. 이벤트 없는 상태 변경은 리뷰에서 거부한다.
3. **보상 상수는 코드에 박지 않는다.** RATE, DAILY_CAP, streak 배수는 `reward_config`에서 읽는다.
4. **유료 서비스를 추가하지 않는다.** 새 외부 서비스는 무료 구간 한도와 카드 요구 여부를 `docs/04-deployment.md`에 먼저 기록하고 ADR로 결정한다.
5. **테스트를 스킵·비활성화해서 녹색을 만들지 않는다.** 실패 원인을 고친다. 조건부 스킵 게이트를 추가하지 않는다.
6. **타임스탬프는 전부 UTC `timestamptz`.** 사용자 로컬 날짜(`local_date`)는 프로필 타임존과 04:00 경계로 서버가 계산해 저장한다.
7. **마이그레이션은 Alembic으로만.** autogenerate 결과를 사람이 읽고 다듬은 뒤 커밋한다. 모델과 마이그레이션이 어긋난 채 커밋하지 않는다.
8. **마을 소유자는 `owner_type + owner_id`.** `user_id`를 마을이나 인벤토리에 직접 걸지 않는다.

## 작업 순서

1. `docs/specs/`에 스펙 작성(템플릿 `docs/specs/_template.md`). 수용 기준을 테스트 문장으로 쓴다.
2. 테스트를 먼저 쓴다. 상태 전이는 전부 API 레벨 테스트로 검증한다.
3. 구현한다. 스펙 밖의 일은 하지 않는다. 발견한 문제는 스펙에 메모로 남긴다.
4. `make check`가 깨끗해야 커밋한다.
5. 결정이 바뀌면 ADR을 추가한다. 기존 ADR은 수정하지 않고 `Superseded by`로 연결한다.

## 커밋

- 제목은 영어 명령형 72자 이내, 본문은 "왜"를 쓴다.
- 문서만 바꿨으면 `docs:`, 스캐폴드·설정은 `chore:`, 기능은 `feat:`, 수정은 `fix:`.
