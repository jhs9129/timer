# 05. 마을: 카탈로그, 구매, 격자 배치, 레벨

상태: implemented
관련 ADR: 0004
관련 문서: `docs/02-process.md` §4

## 목적

몰두로 얻은 코인을 "내 것"으로 바꾸는 곳. 마을이 하찮으면 몰두를 지속시키는 힘이 없다. 이 스펙은 로직만 다룬다. 에셋과 화면은 M5 디자인 패스에서 교체한다.

## 범위

포함:
- 아이템 카탈로그(시드 12개), 구매, 인벤토리
- 격자 배치·이동·철거, 레이어 기반 겹침 검사, 회전
- 레벨(누적 XP → `village_levels`), 레벨업 시 격자 확장
- 공개 조회 `/v/{slug}`

제외:
- 길드 마을(M5). 편집 권한 판단은 `assert_can_edit` 한 곳에 모아 두어 M5에서 확장한다
- 판매·환불, 아이템 업그레이드
- 에셋, 애니메이션

## 흐름

- 레벨 = `village_levels`에서 `xp_required <= xp`인 최대 level. 크기는 그 레벨의 `width×height`.
- `add_xp`(회고 시 호출)가 임계값을 넘기면 `villages.width/height`를 새 레벨 크기로 키우고 `village.level_up` 이벤트. 기존 배치는 그대로.
- 구매: `active` 아이템, `unlock_level <= level`, 잔액 ≥ price. `coin_ledger(kind=purchase, delta=−price)` + `inventory.qty += 1`. 한 트랜잭션.
- 레이어: `ground` 카테고리는 ground 레이어, 나머지(tree, prop, building)는 object 레이어. 겹침은 같은 레이어 안에서만 검사한다. 잔디 위에 나무는 되고, 나무 위에 나무는 안 된다.
- 회전 `0..3`. 1과 3은 footprint의 w/h를 교환한다.
- 배치: 인벤토리 qty>0, 경계 안, 겹침 없음 → qty−1. 철거 → qty+1(환불 없음). 이동은 자기 자신을 제외하고 겹침 검사.

## API

```
GET    /villages/me                                  → VillageOut
PATCH  /villages/me {name}                           → VillageOut
GET    /v/{slug}                                     → PublicVillageOut ; 404 ; 인증 불필요
GET    /shop/items                                   → [ItemOut]
POST   /shop/purchase {item_code}                    → PurchaseOut ; 없는 코드 404 ; 미해금 409 ; 잔액 부족 409
POST   /villages/me/placements {item_code,x,y,rotation?} → 201 PlacementOut ; 재고 없음 409 ; 경계 밖 422 ; 겹침 409
PATCH  /villages/me/placements/{id} {x,y,rotation?}  → PlacementOut ; 겹침 409 ; 남의 것 404
DELETE /villages/me/placements/{id}                  → 204
```

## 스키마 변경

`items`, `inventory`, `placements`(컬럼 `layer` 추가). `items.sort_order`. `docs/03-data-model.md` 갱신.

## 이벤트

- `item.purchased` {item_code, price, qty_after}
- `placement.changed` {action: place|move|remove, item_code, x, y, rotation}
- `village.level_up` {from_level, to_level, width, height}

## 수용 기준

- [x] AC1. 잔액이 가격보다 적으면 구매는 409이고 원장·인벤토리가 바뀌지 않는다.
- [x] AC2. 구매에 성공하면 원장에 −price 행이 생기고 인벤토리 qty가 1 는다. `item.purchased`가 기록된다.
- [x] AC3. 해금 레벨보다 마을 레벨이 낮으면 구매는 409다.
- [x] AC4. 없는 아이템 코드는 404다.
- [x] AC5. 인벤토리에 없는 아이템을 배치하면 409다.
- [x] AC6. 경계를 벗어난 좌표는 422다.
- [x] AC7. 같은 레이어에서 겹치면 409다. ground 위에 tree는 허용된다.
- [x] AC8. 2×2 아이템을 rotation 1로 놓으면 footprint가 교환된다(3×2 아이템으로 검증).
- [x] AC9. 철거하면 인벤토리로 돌아오고 `placement.changed(remove)`가 기록된다.
- [x] AC10. 이동은 자기 자신과의 겹침을 무시하고, 다른 배치와 겹치면 409다.
- [x] AC11. 다른 사용자의 placement id로 이동·철거하면 404다.
- [x] AC12. XP가 600에 이르면 level 2, 1800에 이르면 level 3이고 마을이 20×20으로 커지며 `village.level_up`이 기록된다. 기존 배치는 유지된다.
- [x] AC13. 미인증으로 `GET /v/{slug}`를 부르면 200이고 인벤토리·잔액 필드가 없다. 없는 slug는 404다.

## 메모

- 코인은 테스트에서도 실제 세션(`focus_and_stop` + `retro`)으로만 만든다. 원장 직접 삽입은 잔액 경로 검증을 우회하므로 하지 않는다.
- 레벨업 테스트는 서비스 `add_xp`를 직접 불러 XP를 올린다. 1800분짜리 세션을 API로 돌리면 heartbeat 1800건이라 느리다.
