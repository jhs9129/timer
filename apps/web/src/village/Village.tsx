import { useCallback, useEffect, useState } from 'react'

import { villageApi, type Item, type Placement, type Village as VillageT } from '../api'
import { Grid } from './Grid'
import { Shop } from './Shop'

export function Village() {
  const [village, setVillage] = useState<VillageT | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const [v, list] = await Promise.all([villageApi.mine(), villageApi.items()])
      setVillage(v)
      setItems(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const run = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!village) return <main>{error ? <p role="alert">{error}</p> : '마을을 불러오는 중'}</main>

  const selectedInv = village.inventory.find((i) => i.item_code === selected)
  const publicUrl = `${window.location.origin}/v/${village.slug}`

  return (
    <main>
      <header>
        <a href="/">← 집중으로</a>
        <h1>{village.name}</h1>
        <p>
          Lv.{village.level} · XP {village.xp}
          {village.next_level_xp !== null ? ` / ${village.next_level_xp}` : ''} · {village.width}×
          {village.height} · 코인 {village.balance}
        </p>
        <p>
          공개 주소: <a href={publicUrl}>{publicUrl}</a>
        </p>
      </header>

      {error && <p role="alert">{error}</p>}

      <section aria-label="inventory">
        <h2>인벤토리</h2>
        {village.inventory.length === 0 && <p>비어 있어요. 상점에서 구매하세요.</p>}
        <ul>
          {village.inventory.map((entry) => (
            <li key={entry.item_code}>
              <button
                type="button"
                aria-pressed={selected === entry.item_code}
                onClick={() => setSelected(selected === entry.item_code ? null : entry.item_code)}
              >
                {entry.item_code} × {entry.qty}
              </button>
            </li>
          ))}
        </ul>
        <p>
          {selectedInv
            ? `${selectedInv.item_code} 선택됨. 격자를 클릭해 배치하세요. 배치된 것을 클릭하면 철거합니다.`
            : '인벤토리에서 아이템을 고른 뒤 격자를 클릭하세요.'}
        </p>
      </section>

      <Grid
        width={village.width}
        height={village.height}
        placements={village.placements}
        selected={selected}
        onCell={(x, y) => {
          if (!selected) return
          void run(() => villageApi.place(selected, x, y))
        }}
        onPlacement={(p: Placement) => {
          if (window.confirm(`${p.item_code}을(를) 철거할까요? 인벤토리로 돌아갑니다.`)) {
            void run(() => villageApi.remove(p.id))
          }
        }}
      />

      <Shop
        items={items}
        balance={village.balance}
        level={village.level}
        onBuy={(code) => run(() => villageApi.purchase(code))}
      />
    </main>
  )
}
