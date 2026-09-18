import type { Item } from '../api'

interface Props {
  items: Item[]
  balance: number
  level: number
  onBuy: (code: string) => Promise<void>
}

export function Shop({ items, balance, level, onBuy }: Props) {
  return (
    <section aria-label="shop">
      <h2>상점 · 코인 {balance}</h2>
      <ul>
        {items.map((item) => {
          const locked = item.unlock_level > level
          const poor = item.price > balance
          return (
            <li key={item.code}>
              {item.name} ({item.code}) · {item.width}×{item.height} · {item.price}코인
              {locked ? ` · Lv.${item.unlock_level} 해금` : ''}
              <button type="button" disabled={locked || poor} onClick={() => void onBuy(item.code)}>
                구매
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
