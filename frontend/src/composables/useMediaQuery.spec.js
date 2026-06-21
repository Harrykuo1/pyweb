import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { useMediaQuery } from './useMediaQuery'

// A controllable matchMedia stub so we can flip the match and fire change.
function installMatchMedia(initialMatches) {
  const listeners = new Set()
  const mql = {
    matches: initialMatches,
    addEventListener: (_e, cb) => listeners.add(cb),
    removeEventListener: (_e, cb) => listeners.delete(cb),
  }
  window.matchMedia = vi.fn(() => mql)
  return {
    mql,
    fire(matches) {
      mql.matches = matches
      listeners.forEach((cb) => cb({ matches }))
    },
    listenerCount: () => listeners.size,
  }
}

function mountQuery() {
  let result
  const Host = {
    setup() {
      result = useMediaQuery('(max-width: 640px)')
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, matches: () => result.value }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useMediaQuery', () => {
  it('seeds from the current match and reacts to change events', async () => {
    const mm = installMatchMedia(true)
    const { matches } = mountQuery()
    expect(matches()).toBe(true)

    mm.fire(false)
    expect(matches()).toBe(false)
  })

  it('removes its listener on unmount', () => {
    const mm = installMatchMedia(false)
    const { wrapper } = mountQuery()
    expect(mm.listenerCount()).toBe(1)
    wrapper.unmount()
    expect(mm.listenerCount()).toBe(0)
  })
})
