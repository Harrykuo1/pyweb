import { describe, expect, it } from 'vitest'
import {
  calendarCells,
  defaultFilters,
  filterError,
  intensity,
  localToday,
  longestStreak,
  parseFilters,
  shiftDate,
} from './activityUtils'

describe('activity dates and filters', () => {
  it('uses the selected timezone rather than the browser date', () => {
    const now = new Date('2026-10-01T17:00:00Z')
    expect(localToday('Asia/Taipei', now)).toBe('2026-10-02')
    expect(localToday('UTC', now)).toBe('2026-10-01')
    expect(shiftDate('2024-03-01', -1)).toBe('2024-02-29')
    expect(shiftDate('2026-01-01', -1)).toBe('2025-12-31')
  })
  it('keeps Discord IDs as strings and accepts repeated URL parameters', () => {
    const result = parseFilters({
      user_ids: ['960893399014211614', '101'],
      weekdays: ['1', '5'],
      hour_start: '18',
      hour_end: '24',
    })
    expect(result.user_ids[0]).toBe('960893399014211614')
    expect(result.weekdays).toEqual([1, 5])
    expect(result.hour_start).toBe(18)
    expect(filterError(result)).toBe('')
  })
  it.each([
    { start_date: 'bad' },
    { start_date: '2026-02-30', end_date: '2026-03-01' },
    { start_date: '2026-10-02', end_date: '2026-10-01' },
    { start_date: '2025-01-01', end_date: '2026-12-31' },
    { timezone: 'not/a-zone' },
    { hour_start: 5, hour_end: 5 },
    { hour_start: -1 },
    { hour_end: 25 },
    { weekdays: [9] },
    { user_ids: ['1 OR 1=1'] },
    { channel_ids: ['abc'] },
  ])('rejects invalid conditions %j', (override) => {
    expect(filterError({ ...defaultFilters(), ...override })).not.toBe('')
  })
  it('pads a Monday-first calendar without inventing activity', () => {
    const days = [
      { date: '2026-10-01', messages: 3 },
      { date: '2026-10-02', messages: 0 },
    ]
    const cells = calendarCells(days)
    expect(cells.length).toBe(7)
    expect(cells.slice(0, 3)).toEqual([null, null, null])
    expect(cells.filter(Boolean)).toEqual(days)
    expect(calendarCells([])).toEqual([])
  })
  it('calculates streaks separately for each metric and handles zero', () => {
    const daily = [
      { messages: 2, voice_minutes: 0 },
      { messages: 5, voice_minutes: 1 },
      { messages: 0, voice_minutes: 1 },
    ]
    expect(longestStreak(daily, 'messages')).toBe(2)
    expect(longestStreak(daily, 'voice_minutes')).toBe(2)
    expect(longestStreak([], 'messages')).toBe(0)
    expect(intensity(0, 0)).toBe(0)
    expect(intensity(1, 100)).toBe(1)
    expect(intensity(100, 100)).toBe(4)
  })
})
