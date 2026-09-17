# 01. Google 로그인과 프로필

상태: implemented
관련 ADR: 0001, 0004
관련 문서: `docs/02-process.md` §6

## 목적

몰두 기록은 사람에게 귀속되어야 한다. 비밀번호를 직접 관리하지 않기 위해 Google OIDC만 지원한다. 가입과 동시에 사용자의 마을을 만들어 마을 모드가 항상 존재하게 한다.

## 범위

포함:
- Google OAuth 인가 코드 흐름(서버 사이드), 서명된 세션 쿠키
- 첫 로그인 시 사용자·마을 생성, `user.created` 이벤트
- `/me` 조회와 타임존·표시 이름 수정
- 개발 환경 전용 `dev-login` (APP_ENV=development일 때만 활성)

제외:
- 동의 항목 저장(`consents`)은 알림 스펙(M3)에서 UI와 함께 넣는다
- 계정 삭제

## 흐름

1. `GET /auth/google/start` → `state`를 서명 쿠키에 담고 Google 인가 URL로 302.
2. `GET /auth/google/callback?code&state` → state 검증 → 코드 교환 → userinfo 조회 → `google_sub`로 upsert → 새 사용자면 마을 생성 → 세션 쿠키 발급 → `FRONTEND_URL`로 302.
3. 이후 요청은 쿠키의 서명된 user id로 인증한다. 만료 30일.

## API

```
GET  /auth/google/start                → 302 Google
GET  /auth/google/callback?code&state  → 302 FRONTEND_URL ; state 불일치 400
POST /auth/dev-login {email, display_name?}  → 200 MeOut ; 개발 환경 외 404
POST /auth/logout                      → 204, 쿠키 삭제
GET  /me                               → 200 MeOut ; 미인증 401
PATCH /me {timezone?, display_name?}   → 200 MeOut ; 잘못된 IANA 타임존 422
```

`MeOut = {id, email, display_name, timezone, balance, streak_days, village: {slug, name, xp}}`

## 스키마 변경

`users`, `villages`, `village_levels`, `events`. `docs/03-data-model.md` 참고.

## 이벤트

- `user.created` {email_domain, timezone}
- `village.created` {owner_type, slug}

## 수용 기준

- [x] AC1. 미인증 상태로 `/me`를 호출하면 401을 반환한다.
- [x] AC2. Google 콜백이 유효한 코드로 도착하면 사용자와 마을이 생성되고 세션 쿠키가 설정된다.
- [x] AC3. 같은 `google_sub`로 다시 로그인하면 사용자가 중복 생성되지 않는다.
- [x] AC4. state가 쿠키와 다르면 400을 반환하고 사용자를 만들지 않는다.
- [x] AC5. 개발 환경에서 `dev-login`은 사용자를 만들고 쿠키를 설정한다. 운영 환경에서는 404다.
- [x] AC6. `PATCH /me`에 잘못된 타임존을 보내면 422다.
- [x] AC7. 사용자 생성 시 `user.created`, `village.created` 이벤트가 기록된다.

## 메모

- userinfo 엔드포인트를 쓰므로 id_token 서명 검증을 하지 않는다. 토큰을 Google과 직접 TLS로 교환했기 때문에 안전하다.
- 운영에서 프론트와 API가 다른 사이트(Cloudflare Pages 도메인 vs Koyeb 도메인)면 `COOKIE_SAMESITE=none`, `COOKIE_SECURE=true`가 필요하다. 같은 상위 도메인을 쓰면 `lax`로 충분하다.
