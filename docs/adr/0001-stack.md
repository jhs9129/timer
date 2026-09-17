# ADR 0001. 기술 스택: FastAPI + React

상태: accepted (2026-09-17)

## 맥락

서비스는 세션 타이머, 회고, 보상, 마을 편집, 알림을 제공한다. 운영자는 데이터 엔지니어 한 명이고 Python에 익숙하다. 이후 이벤트 데이터를 파이프라인 프로젝트로 확장할 계획이 있다. 비용은 0원이어야 한다.

## 결정

- 백엔드: Python 3.11, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2. 패키지 관리는 uv.
- 프론트: React 19, Vite, TypeScript. 상태 fetch는 TanStack Query(M1 도입). PWA로 푸시 수신.
- DB: Postgres 16.
- 모노레포 `apps/api`, `apps/web`, `data/`(M4), `docs/`, `infra/`.

## 대안

- Next.js + Supabase 풀스택: 무료 배포 선택지가 가장 넓지만 TypeScript 단일 스택이 되어 Python 파이프라인과 언어가 갈린다. 운영자의 강점(Python)을 살리지 못한다.
- Cloudflare Workers + D1: 상업 사용도 무료지만 SQLite라 Postgres 기능(부분 인덱스, jsonb, 파티션)을 못 쓴다.

## 결과

- 백엔드와 데이터 파이프라인이 같은 언어. 도메인 모델을 dbt 소스 정의로 옮기기 쉽다.
- Python 무료 호스팅 선택지가 좁아 배포 결정(ADR 0005)이 까다로워졌다.
- 프론트와 백엔드 타입을 공유하지 않는다. OpenAPI 스키마에서 클라이언트 타입을 생성해 메운다(M1).
