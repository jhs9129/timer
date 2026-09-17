# ADR 0005. 무비용 배포: Koyeb + Supabase Postgres + Cloudflare Pages + cron-job.org

상태: accepted (2026-09-17)

## 맥락

수익화 전까지 월 요금 0원. 카드 등록은 허용하되 요금이 0을 넘을 수 없는 구성을 선호한다. 백엔드는 Python(ADR 0001). 카운트다운 종료 푸시를 탭이 닫힌 상태에서도 보내야 하므로 시각 기반 실행 수단이 필요하다. 인스턴스가 하나뿐이면 별도 워커를 둘 수 없다.

검증한 사실(2026-09):
- Render Free: 15분 슬립, 콜드스타트 30~60초.
- Koyeb Free: 1인스턴스, 1시간 슬립, 콜드스타트 1~5초, 카드 대부분 요구.
- Cloud Run: 월 200만 요청 무료, 카드 필수, 소프트캡. Cloud Tasks로 예약 호출 가능.
- Neon Free: 월 100 CU시간. 1분 크론이 깨우면 초과.
- Supabase Free: 500MB, 7일 비활성 시 일시정지, 컴퓨트 시간 상한 없음.
- cron-job.org: 분 단위 무료, 타임아웃 30초.

## 결정

- API: Koyeb 무료 인스턴스 1개. Dockerfile 빌드.
- DB: Supabase 무료 Postgres. Supabase Auth/PostgREST는 쓰지 않는다.
- 프론트: Cloudflare Pages.
- 스케줄: cron-job.org가 1분마다 `/internal/dispatch` 호출. 알림 발송, heartbeat timeout 판정, 당일 경계 abandon 처리를 이 엔드포인트가 30초 안에 배치로 수행한다.
- 이메일: Resend 무료 구간. 푸시: VAPID.

## 대안

- Cloud Run + Cloud Tasks: 푸시 시각이 정확하고 한도가 넉넉하다. 소프트캡이라 기각. 트래픽이 Koyeb 1인스턴스를 넘으면 1순위 이전 후보다. 컨테이너 하나로 빌드하므로 이전 비용은 낮다.
- Render: 콜드스타트가 크론 타임아웃과 푸시 지연을 유발. 기각.
- Neon: 크론 패턴과 CU시간 한도가 충돌. 기각.

## 결과

- 서버 푸시는 최대 60초 지연 + 콜드스타트. 탭이 열려 있으면 클라이언트가 즉시 알림을 띄우므로 체감은 탭이 닫힌 경우로 한정된다.
- 모든 배치 작업이 `/internal/dispatch` 하나에 몰린다. 작업별 상한(건수)을 두고 나머지는 다음 분으로 넘긴다.
- 인메모리 상태 금지. 스케줄은 전부 DB.
- 새 외부 서비스는 `docs/04-deployment.md`에 무료 구간과 카드 요구를 기록하고 ADR로 결정한 뒤에만 추가한다.
