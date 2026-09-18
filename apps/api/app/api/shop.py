from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas import InventoryOut, ItemOut, PurchaseIn, PurchaseOut
from app.services import shop, villages
from app.services.rewards import balance

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/items")
async def list_items(db: DbSession) -> list[ItemOut]:
    return [ItemOut.from_model(item) for item in await shop.list_items(db)]


@router.post("/purchase")
async def purchase(body: PurchaseIn, db: DbSession, user: CurrentUser) -> PurchaseOut:
    village = await villages.village_for_user(db, user.id)
    await shop.purchase(db, user=user, village=village, item_code=body.item_code)
    inventory = await villages.inventory_of(db, village.id)
    return PurchaseOut(
        inventory=[InventoryOut(item_code=i.item.code, qty=i.qty) for i in inventory if i.qty > 0],
        balance=await balance(db, user.id),
    )
