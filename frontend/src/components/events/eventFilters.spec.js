import { describe, expect, it } from 'vitest'

import {
  CURRENT_YEAR,
  MIN_YEAR,
  YEAR_OPTIONS,
  safeOrder,
  safeStringList,
  safeYear,
} from './eventFilters'

describe('eventFilters validators', () => {
  it('safeOrder only accepts asc, else desc', () => {
    expect(safeOrder('asc')).toBe('asc')
    expect(safeOrder('desc')).toBe('desc')
    expect(safeOrder('nonsense')).toBe('desc')
    expect(safeOrder(undefined)).toBe('desc')
  })

  it('safeYear accepts in-range numbers and rejects the rest', () => {
    expect(safeYear(String(CURRENT_YEAR))).toBe(CURRENT_YEAR)
    expect(safeYear(MIN_YEAR)).toBe(MIN_YEAR)
    expect(safeYear('1999')).toBe(null)
    expect(safeYear(CURRENT_YEAR + 1)).toBe(null)
    expect(safeYear('abc')).toBe(null)
    expect(safeYear('')).toBe(null)
  })

  it('safeStringList normalizes, dedupes, trims and caps at the limit', () => {
    expect(safeStringList('出遊', 20)).toEqual(['出遊'])
    expect(safeStringList(['a', ' a ', 'b'], 20)).toEqual(['a', 'b'])
    expect(safeStringList(['a', 'b', 'c'], 2)).toEqual(['a', 'b'])
    expect(safeStringList([null, 1, '  '], 20)).toEqual([])
    expect(safeStringList(undefined, 20)).toEqual([])
  })

  it('YEAR_OPTIONS runs from the current year down to the floor', () => {
    expect(YEAR_OPTIONS[0]).toBe(CURRENT_YEAR)
    expect(YEAR_OPTIONS[YEAR_OPTIONS.length - 1]).toBe(MIN_YEAR)
  })
})
