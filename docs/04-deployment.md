# 04. 배포 (무비용)

원칙: 수익화 전까지 월 요금 0원. 카드 등록은 허용하되, **요금이 0을 넘을 수 없는(하드캡) 구성**을 우선한다.

## 확정 조합

| 역할 | 서비스 | 무료 구간 | 카드 | 제약 |
|---|---|---|---|---|
| 프론트 | Cloudflare Pages | 무제한 정적 요청 | 불필요 | 없음 |
| API | Koyeb Free Instance | 조직당 1개, 512MB, 0.1 vCPU | 대부분 요구(사기 방지) | 1시간 무트래픽 시 슬립, 콜드스타트 1~5초. 1개 초과 불가 → 하드캡 |
| DB | Supabase Free (Postgres만 사용) | 500MB, 프로젝트 2개 | 불필요 | 7일 비활성 시 일시정지. 크론이 매분 치므로 실제로는 잠들지 않음 |
| 크론 | cron-job.org | 분 단위, 잡 수 무제한, 타임아웃 30초 | 불필요 | API 생성 100회/일 |
| 이메일 | Resend | 월 3천 건 | 불필요 | 도메인 인증 필요(무료) |
| 푸시 | Web Push (VAPID) | 무료 | 불필요 | 키는 자체 생성 |
| 스토리지 (M4) | Cloudflare R2 | 10GB | 요구 | 이그레스 무료 |

## 검토했지만 제외한 것 (2026-09 기준)

- **Render Free**: 15분 슬립, 콜드스타트 30~60초. 푸시 디스패치 지연이 1분을 넘을 수 있어 제외.
- **Neon Free**: 프로젝트당 월 100 CU시간. 1분 크론이 DB를 계속 깨우면 720시간 × 0.25CU = 180 CU시간으로 한도 초과. 제외.
- **Google Cloud Run + Cloud Tasks**: 무료 한도가 넉넉하고 예약 시각 호출이 정확하지만, 설정 실수 시 과금되는 소프트캡. 트래픽이 Koyeb 한 인스턴스를 넘을 때 이전 후보 1순위. API는 Dockerfile 하나로 빌드하므로 이전 비용은 낮다.

## 아키텍처 제약이 배포에서 오는 것

- 서버는 언제든 재시작될 수 있다. 인메모리 상태를 두지 않는다. 스케줄은 전부 DB 테이블(`scheduled_notifications`).
- 크론 요청은 30초 안에 끝나야 한다. `/internal/dispatch`는 한 번에 최대 N건(기본 200) 처리하고 나머지는 다음 분에 넘긴다.
- 무료 인스턴스는 1개다. 백그라운드 워커를 따로 띄울 수 없으므로 배치 작업(abandon 처리, heartbeat timeout 판정)도 같은 `/internal/dispatch` 안에서 수행한다.
- 512MB 메모리. 커넥션 풀은 작게(기본 5). Supabase는 pooler(6543, transaction 모드) 사용.

## 환경 변수

| 이름 | 용도 |
|---|---|
| `APP_ENV` | `development` / `production` |
| `DATABASE_URL` | `postgresql+asyncpg://…` |
| `CORS_ORIGINS` | 콤마 구분 |
| `SESSION_SECRET` | 쿠키 서명 (M1) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth (M1) |
| `CRON_SECRET` | `/internal/*` 보호 |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Web Push. `make vapid-keys`로 생성. 비어 있으면 푸시는 로그만 남긴다 |
| `RESEND_API_KEY`, `EMAIL_FROM` | 주간 요약 이메일. 비어 있으면 로그만 남긴다 |

시크릿은 저장소에 넣지 않는다. `.env.example`만 커밋한다.

## 배포 절차 (M1에서 실제 수행)

1. Supabase 프로젝트 생성 → `DATABASE_URL` 확보(pooler 주소).
2. Koyeb에 GitHub 연동, `apps/api/Dockerfile` 빌드, 환경 변수 등록, 헬스체크 `/health`.
3. Cloudflare Pages에 `apps/web` 연결. 빌드 `npm run build`, 출력 `dist`, `VITE_API_URL` 설정.
4. cron-job.org에 `POST https://<api>/internal/dispatch` 1분 주기, 헤더 `X-Cron-Secret` 등록. 이 한 호출이 timeout·abandon 배치와 알림 발송을 모두 수행한다.
5. Google Cloud Console에서 OAuth 클라이언트 생성(무료). 리다이렉트 URI 등록.
6. `make vapid-keys`로 VAPID 키 쌍을 만들어 Koyeb 환경 변수에 넣는다. 공개 키는 프론트가 `/push/vapid-public-key`로 받아간다.
7. Resend에서 발신 도메인을 인증하고 `RESEND_API_KEY`, `EMAIL_FROM`을 넣는다. 도메인 인증 전에는 계정 소유자 주소로만 발송된다.
8. 프론트와 API가 다른 사이트(예: `*.pages.dev`와 `*.koyeb.app`)면 `COOKIE_SAMESITE=none`, `COOKIE_SECURE=true`가 필요하다. 같은 상위 도메인을 쓰면 `lax`로 충분하다.

## 비용 감시

- Koyeb: 무료 인스턴스만 존재하는지 월 1회 확인.
- Supabase: DB 크기 500MB 도달 전에 `events` 파티션 내보내기(M4)로 정리.
- 새 서비스 추가는 이 문서에 행을 추가하고 ADR을 쓴 뒤에만.
