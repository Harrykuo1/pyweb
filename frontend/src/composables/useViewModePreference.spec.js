import { afterEach, describe, expect, it } from 'vitest'

import { useViewModePreference } from './useViewModePreference'

const KEY = 'test.viewMode'

afterEach(() => {
  localStorage.clear()
})

describe('useViewModePreference', () => {
  it('defaults to the fallback when nothing is stored', () => {
    const { viewMode } = useViewModePreference(KEY)
    expect(viewMode.value).toBe('grid')
  })

  it('reads a previously stored allowed value', () => {
    localStorage.setItem(KEY, 'list')
    const { viewMode } = useViewModePreference(KEY)
    expect(viewMode.value).toBe('list')
  })

  it('ignores a stored value not in the allowed set', () => {
    localStorage.setItem(KEY, 'bogus')
    const { viewMode } = useViewModePreference(KEY)
    expect(viewMode.value).toBe('grid')
  })

  it('setViewMode updates the ref and persists', () => {
    const { viewMode, setViewMode } = useViewModePreference(KEY)
    setViewMode('list')
    expect(viewMode.value).toBe('list')
    expect(localStorage.getItem(KEY)).toBe('list')
  })
})
