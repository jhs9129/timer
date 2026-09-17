# My Little Village

몰두(집중)를 돕는 서비스. 타이머로 몰두 세션을 기록하고, 끝나면 회고를 남기고, 그 시간이 코인이 되어 자기 마을을 꾸민다.

- 무엇을 왜 만드는지: [`docs/01-vision.md`](docs/01-vision.md)
- 어떻게 동작하는지: [`docs/02-process.md`](docs/02-process.md)
- 데이터: [`docs/03-data-model.md`](docs/03-data-model.md)
- 배포(0원): [`docs/04-deployment.md`](docs/04-deployment.md)
- AI와 일하는 방식: [`docs/05-harness.md`](docs/05-harness.md), [`CLAUDE.md`](CLAUDE.md)

## 시작하기

```
make setup      # uv sync, npm ci
make db-up      # Postgres 16 (docker)
make dev-api    # http://localhost:8000/health
make dev-web    # http://localhost:5173
make check      # 커밋 전 필수
```

요구: Python 3.11, uv, Node 22, Docker.

개발 환경에서는 Google OAuth 설정 없이 로그인 화면의 "개발용 로그인"(이메일만)으로 들어갈 수 있다. 운영에서는 `APP_ENV=production`이라 이 경로가 404다.
