import { describe, expect, it } from 'vitest'

import {
  CURRENT_YEAR,
  MIN_JOB_YEAR,
  YEAR_OPTIONS,
  safeKind,
  safeOrder,
  safeSort,
  safeStringList,
  safeYear,
} from './jobFilters'

describe('jobFilters validators', () => {
  it('safeSort falls back to created_at for unknown keys', () => {
    expect(safeSort('company')).toBe('company')
    expect(safeSort('garbage')).toBe('created_at')
    expect(safeSort(undefined)).toBe('created_at')
  })

  it('safeOrder falls back to desc for anything but asc/desc', () => {
    expect(safeOrder('asc')).toBe('asc')
    expect(safeOrder('sideways')).toBe('desc')
  })

  it('safeKind only accepts the known kind values', () => {
    expect(safeKind('internship')).toBe('internship')
    expect(safeKind('fulltime')).toBe('fulltime')
    expect(safeKind('')).toBe('')
    expect(safeKind('bogus')).toBe('')
  })

  it('safeYear accepts in-range numbers and rejects the rest', () => {
    expect(safeYear(String(CURRENT_YEAR))).toBe(CURRENT_YEAR)
    expect(safeYear(MIN_JOB_YEAR)).toBe(MIN_JOB_YEAR)
    expect(safeYear('1999')).toBe(null)
    expect(safeYear(CURRENT_YEAR + 1)).toBe(null)
    expect(safeYear('abc')).toBe(null)
    expect(safeYear('')).toBe(null)
  })

  it('safeStringList normalizes, dedupes, trims and caps at the limit', () => {
    expect(safeStringList('Acme', 10)).toEqual(['Acme'])
    expect(safeStringList(['Acme', ' Acme ', 'Globex'], 10)).toEqual([
      'Acme',
      'Globex',
    ])
    expect(safeStringList(['a', 'b', 'c'], 2)).toEqual(['a', 'b'])
    expect(safeStringList([null, 1, ' '], 10)).toEqual([])
    expect(safeStringList(undefined, 10)).toEqual([])
  })

  it('YEAR_OPTIONS runs from the current year down to the floor', () => {
    expect(YEAR_OPTIONS[0]).toBe(CURRENT_YEAR)
    expect(YEAR_OPTIONS[YEAR_OPTIONS.length - 1]).toBe(MIN_JOB_YEAR)
  })
})
