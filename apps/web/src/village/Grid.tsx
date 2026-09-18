import type { Placement } from '../api'

export const CELL = 28

/** Placeholder look until the design pass: one flat color per category. */
const COLORS: Record<Placement['category'], string> = {
  ground: '#cfe8b8',
  tree: '#4f8a3a',
  prop: '#c9a15b',
  building: '#b0654a',
}

interface Props {
  width: number
  height: number
  placements: Placement[]
  onCell?: (x: number, y: number) => void
  onPlacement?: (placement: Placement) => void
  selected?: string | null
}

export function Grid({ width, height, placements, onCell, onPlacement, selected }: Props) {
  const ground = placements.filter((p) => p.layer === 'ground')
  const objects = placements.filter((p) => p.layer === 'object')
  return (
    <div
      role="grid"
      aria-label="village grid"
      style={{
        position: 'relative',
        width: width * CELL,
        height: height * CELL,
        backgroundColor: '#e6dfcf',
        backgroundImage:
          'linear-gradient(#d8cfba 1px, transparent 1px), linear-gradient(90deg, #d8cfba 1px, transparent 1px)',
        backgroundSize: `${CELL}px ${CELL}px`,
        cursor: onCell && selected ? 'copy' : 'default',
      }}
      onClick={(e) => {
        if (!onCell) return
        const rect = e.currentTarget.getBoundingClientRect()
        const x = Math.floor((e.clientX - rect.left) / CELL)
        const y = Math.floor((e.clientY - rect.top) / CELL)
        if (x >= 0 && y >= 0 && x < width && y < height) onCell(x, y)
      }}
    >
      {[...ground, ...objects].map((p) => (
        <button
          key={p.id}
          type="button"
          aria-label={`${p.item_code} at ${p.x},${p.y}`}
          title={p.item_code}
          onClick={(e) => {
            if (!onPlacement) return
            e.stopPropagation()
            onPlacement(p)
          }}
          style={{
            position: 'absolute',
            left: p.x * CELL,
            top: p.y * CELL,
            width: p.width * CELL,
            height: p.height * CELL,
            background: COLORS[p.category],
            border: p.layer === 'object' ? '1px solid rgba(0,0,0,.35)' : 'none',
            fontSize: 9,
            overflow: 'hidden',
            padding: 0,
            cursor: onPlacement ? 'pointer' : 'default',
          }}
        >
          {p.layer === 'object' ? p.item_code : ''}
        </button>
      ))}
    </div>
  )
}
