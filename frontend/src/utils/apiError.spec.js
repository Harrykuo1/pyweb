import { describe, expect, it } from 'vitest'

import { extractError } from './apiError'

describe('extractError', () => {
  it('returns the backend detail string when present', () => {
    const err = { response: { data: { detail: '名稱已被使用' } } }
    expect(extractError(err, 'fallback')).toBe('名稱已被使用')
  })

  it('falls back when detail is missing or not a string', () => {
    expect(extractError({ response: { data: {} } }, 'fb')).toBe('fb')
    expect(extractError({ response: { data: { detail: 42 } } }, 'fb')).toBe('fb')
    expect(extractError(undefined, 'fb')).toBe('fb')
    expect(extractError(new Error('x'), 'fb')).toBe('fb')
  })
})
