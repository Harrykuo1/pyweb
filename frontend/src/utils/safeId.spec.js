import { describe, expect, it } from 'vitest'

import { safeId } from './safeId'

describe('safeId', () => {
  it('accepts positive integers (string or number)', () => {
    expect(safeId('7')).toBe(7)
    expect(safeId(7)).toBe(7)
  })

  it('takes the first element of an array', () => {
    expect(safeId(['7', '8'])).toBe(7)
  })

  it('rejects non-positive, non-integer, empty and missing values', () => {
    expect(safeId('0')).toBe(null)
    expect(safeId('-3')).toBe(null)
    expect(safeId('1.5')).toBe(null)
    expect(safeId('abc')).toBe(null)
    expect(safeId('')).toBe(null)
    expect(safeId(undefined)).toBe(null)
    expect(safeId(null)).toBe(null)
  })
})
