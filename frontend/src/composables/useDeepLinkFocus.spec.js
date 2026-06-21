import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive } from 'vue'

import { useDeepLinkFocus } from './useDeepLinkFocus'

function setup(query = {}) {
  const route = reactive({ query: { ...query } })
  const router = { replace: vi.fn() }
  const scope = effectScope()
  let api
  scope.run(() => {
    api = useDeepLinkFocus({
      route,
      router,
      anchorClass: (id) => `row-${id}`,
      watchSource: () => 0,
    })
  })
  return { route, router, ...api, dispose: () => scope.stop() }
}

function addAnchor(id) {
  const el = document.createElement('div')
  el.className = `row-${id}`
  el.scrollIntoView = vi.fn()
  document.body.appendChild(el)
  return el
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('useDeepLinkFocus', () => {
  it('does nothing when there is no focus id', () => {
    const { router, consume } = setup({})
    consume()
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('strips the key from the URL and flashes the anchor', async () => {
    const el = addAnchor(7)
    const { router, consume } = setup({ focus: '7', tag: 'x' })

    consume()
    // Key removed, other params preserved.
    expect(router.replace).toHaveBeenCalledWith({ query: { tag: 'x' } })

    await nextTick()
    expect(el.scrollIntoView).toHaveBeenCalled()
    expect(el.classList.contains('is-flash')).toBe(true)
  })

  it('ignores a non-numeric focus value', () => {
    const { router, consume } = setup({ focus: 'abc' })
    consume()
    expect(router.replace).not.toHaveBeenCalled()
  })

  it('no-ops the flash when the anchor is not in the DOM', async () => {
    const { consume } = setup({ focus: '99' })
    consume()
    await nextTick()
    // Nothing to assert beyond "did not throw" — the missing anchor path.
    expect(document.querySelector('.row-99')).toBe(null)
  })
})
