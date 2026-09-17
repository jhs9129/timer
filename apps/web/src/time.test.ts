import { describe, expect, it } from 'vitest'

import { formatDuration, liveFocusedSeconds } from './time'

describe('formatDuration', () => {
  it('formats minutes and seconds', () => {
    expect(formatDuration(0)).toBe('00:00')
    expect(formatDuration(65)).toBe('01:05')
    expect(formatDuration(3600)).toBe('1:00:00')
    expect(formatDuration(-5)).toBe('00:00')
  })
})

describe('liveFocusedSeconds', () => {
  it('returns server seconds when nothing is running', () => {
    expect(liveFocusedSeconds(120, null, Date.now())).toBe(120)
  })
  it('adds the open segment elapsed locally', () => {
    const since = new Date('2026-09-17T01:00:00Z').toISOString()
    const now = Date.parse('2026-09-17T01:00:30Z')
    expect(liveFocusedSeconds(120, since, now)).toBe(150)
  })
})
