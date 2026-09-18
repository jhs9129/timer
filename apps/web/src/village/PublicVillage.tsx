import { useEffect, useState } from 'react'

import { ApiError, villageApi, type PublicVillage as PublicVillageT } from '../api'
import { Grid } from './Grid'

export function PublicVillage({ slug }: { slug: string }) {
  const [state, setState] = useState<
    { kind: 'loading' } | { kind: 'ok'; village: PublicVillageT } | { kind: 'missing' } | { kind: 'error' }
  >({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    villageApi
      .public(slug)
      .then((village) => {
        if (!cancelled) setState({ kind: 'ok', village })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState(err instanceof ApiError && err.status === 404 ? { kind: 'missing' } : { kind: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  if (state.kind === 'loading') return <main>불러오는 중</main>
  if (state.kind === 'missing') return <main>그런 마을은 없어요.</main>
  if (state.kind === 'error') return <main>마을을 불러오지 못했어요.</main>

  const { village } = state
  return (
    <main>
      <a href="/">My Little Village</a>
      <h1>{village.name}</h1>
      <p>
        Lv.{village.level} · XP {village.xp}
      </p>
      <Grid width={village.width} height={village.height} placements={village.placements} />
    </main>
  )
}
