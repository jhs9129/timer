# ADR 0004. 마을 소유자는 `owner_type + owner_id`로 추상화한다

상태: accepted (2026-09-17)

## 맥락

M1~M4에서 마을은 사용자 한 명의 것이다. M5에서 여러 사용자가 함께 꾸미는 길드 마을을 계획하고 있다. 그때 `villages.user_id`를 `guild_id`로 바꾸거나 두 컬럼을 병존시키면 인벤토리, 배치, 잔액 로직을 전부 손봐야 한다.

## 결정

- `villages(owner_type text, owner_id uuid)`. `owner_type ∈ {user, guild}`. 유니크 `(owner_type, owner_id)`.
- `inventory`와 `placements`는 `village_id`에만 묶인다. 사용자에 직접 묶지 않는다.
- 코인 잔액은 사용자(`coin_ledger.user_id`)의 것이다. 길드 마을에서 구매할 때 누구의 코인을 쓰는지는 M5에서 결정한다. 이 ADR은 그 결정을 막지 않는다.
- DB FK는 걸지 않는다(다형 참조). 애플리케이션이 소유자 존재를 검증한다.

## 대안

- `villages.user_id` + 나중에 마이그레이션: 지금은 단순하지만 M5에서 3개 테이블과 모든 마을 API를 건드린다.
- 별도 `owners` 테이블(사용자와 길드가 각각 owner 행을 가짐): FK를 걸 수 있어 정합성은 낫지만 조인이 하나 늘고, 현재 단계에서 얻는 것이 없다. M5에서 필요해지면 이 방식으로 전환하는 ADR을 쓴다.

## 결과

- 마을 API는 처음부터 "요청자가 이 마을을 편집할 권한이 있는가"를 소유자 타입에 따라 판단하는 함수를 거친다.
- 사용자 삭제 시 마을 정리는 애플리케이션 책임이다(FK cascade 없음).
