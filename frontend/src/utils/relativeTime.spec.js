import { describe, expect, it } from 'vitest'

import { relativeTime } from './relativeTime'

const NOW = new Date('2026-05-05T12:00:00Z')

function ago(seconds) {
  return new Date(NOW.getTime() - seconds * 1000)
}

describe('relativeTime', () => {
  it('returns "剛剛" for under 5 seconds in either direction', () => {
    expect(relativeTime(ago(0), NOW)).toBe('剛剛')
    expect(relativeTime(ago(3), NOW)).toBe('剛剛')
    expect(relativeTime(ago(-3), NOW)).toBe('剛剛')
  })

  it('formats seconds, minutes, hours, days, months, years', () => {
    // We can't assert exact strings across every Intl version — just
    // that the right unit shows up. zh-TW with numeric:auto produces
    // "X 分鐘前" / "X 小時前" / "X 天前" etc.
    expect(relativeTime(ago(30), NOW)).toMatch(/秒/)
    expect(relativeTime(ago(5 * 60), NOW)).toMatch(/分鐘/)
    expect(relativeTime(ago(2 * 60 * 60), NOW)).toMatch(/小時/)
    expect(relativeTime(ago(3 * 86400), NOW)).toMatch(/天/)
    expect(relativeTime(ago(45 * 86400), NOW)).toMatch(/月/)
    expect(relativeTime(ago(2 * 365 * 86400), NOW)).toMatch(/年/)
  })

  it('accepts an ISO string', () => {
    expect(relativeTime('2026-05-05T11:00:00Z', NOW)).toMatch(/小時/)
  })

  it('returns empty string for unparseable input', () => {
    expect(relativeTime('not-a-date', NOW)).toBe('')
  })
})
