"""village items inventory placements

Revision ID: 8372ab940a8e
Revises: 6e7b77997983
Create Date: 2026-09-18 02:12:00.413351

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8372ab940a8e"
down_revision: str | None = "6e7b77997983"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("width", sa.SmallInteger(), nullable=False),
        sa.Column("height", sa.SmallInteger(), nullable=False),
        sa.Column("unlock_level", sa.SmallInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "inventory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("village_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
        ),
        sa.ForeignKeyConstraint(
            ["village_id"],
            ["villages.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("village_id", "item_id", name="uq_inventory_village_item"),
    )
    op.create_index(op.f("ix_inventory_village_id"), "inventory", ["village_id"], unique=False)
    op.create_table(
        "placements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("village_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("x", sa.SmallInteger(), nullable=False),
        sa.Column("y", sa.SmallInteger(), nullable=False),
        sa.Column("rotation", sa.SmallInteger(), nullable=False),
        sa.Column("layer", sa.String(length=8), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
        ),
        sa.ForeignKeyConstraint(
            ["village_id"],
            ["villages.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_placements_village_id"), "placements", ["village_id"], unique=False)

    # Seed catalog. Prices assume 1 coin/min and a 300 coin daily cap (reward_config).
    items = [
        # code, name, category, price, w, h, unlock_level
        ("ground_grass", "잔디", "ground", 5, 1, 1, 1),
        ("ground_path", "돌길", "ground", 8, 1, 1, 1),
        ("ground_flowers", "꽃밭", "ground", 15, 1, 1, 1),
        ("tree_oak", "참나무", "tree", 60, 1, 1, 1),
        ("tree_pine", "소나무", "tree", 60, 1, 1, 1),
        ("tree_big_oak", "큰 참나무", "tree", 150, 2, 2, 2),
        ("prop_lamp", "가로등", "prop", 40, 1, 1, 1),
        ("prop_bench", "벤치", "prop", 50, 1, 1, 1),
        ("prop_fence", "울타리", "prop", 20, 1, 1, 1),
        ("prop_well", "우물", "prop", 200, 2, 2, 2),
        ("bldg_cottage", "오두막", "building", 500, 2, 2, 2),
        ("bldg_cafe", "카페", "building", 900, 3, 2, 3),
    ]
    rows = ",\n".join(
        f"(gen_random_uuid(), '{code}', '{name}', '{cat}', {price}, {w}, {h}, {lvl}, true, {i})"
        for i, (code, name, cat, price, w, h, lvl) in enumerate(items)
    )
    op.execute(
        sa.text(
            "INSERT INTO items (id, code, name, category, price, width, height, unlock_level, "
            f"active, sort_order) VALUES\n{rows}"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_placements_village_id"), table_name="placements")
    op.drop_table("placements")
    op.drop_index(op.f("ix_inventory_village_id"), table_name="inventory")
    op.drop_table("inventory")
    op.drop_table("items")
