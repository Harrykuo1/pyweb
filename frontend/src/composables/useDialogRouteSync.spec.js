import { describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { useDialogRouteSync } from './useDialogRouteSync'

function makeRoute(query = {}) {
  return reactive({ query: { ...query } })
}

describe('useDialogRouteSync', () => {
  it('fetches and opens on mount when the query key holds a valid id', async () => {
    const route = makeRoute({ detail: '7' })
    const router = { replace: vi.fn() }
    const fetchItem = vi.fn().mockResolvedValue({ id: 7, name: 'x' })

    const sync = useDialogRouteSync({ route, router, fetchItem })
    await flushPromises()

    expect(fetchItem).toHaveBeenCalledWith(7)
    expect(sync.open.value).toBe(true)
    expect(sync.item.value).toEqual({ id: 7, name: 'x' })
  })

  it('ignores a non-numeric value and never fetches', async () => {
    const route = makeRoute({ detail: 'abc' })
    const fetchItem = vi.fn()
    const sync = useDialogRouteSync({ route, router: { replace: vi.fn() }, fetchItem })
    await nextTick()

    expect(fetchItem).not.toHaveBeenCalled()
    expect(sync.open.value).toBe(false)
  })

  it('swallows a rejected fetch and leaves the dialog closed', async () => {
    const route = makeRoute({ detail: '999' })
    const fetchItem = vi.fn().mockRejectedValue({ response: { status: 404 } })
    const sync = useDialogRouteSync({ route, router: { replace: vi.fn() }, fetchItem })
    await flushPromises()

    expect(sync.open.value).toBe(false)
  })

  it('drops the key but preserves other params when the dialog closes', async () => {
    const route = makeRoute({ detail: '7', sort: 'company', order: 'asc' })
    const router = { replace: vi.fn() }
    const fetchItem = vi.fn().mockResolvedValue({ id: 7 })
    const sync = useDialogRouteSync({ route, router, fetchItem })
    await flushPromises()
    expect(sync.open.value).toBe(true)

    sync.open.value = false
    await nextTick()

    expect(router.replace).toHaveBeenCalledWith({
      query: { sort: 'company', order: 'asc' },
    })
  })

  it('skips a redundant fetch when the same id re-emits while already open', async () => {
    const route = makeRoute({ detail: '7' })
    const fetchItem = vi.fn().mockResolvedValue({ id: 7 })
    useDialogRouteSync({ route, router: { replace: vi.fn() }, fetchItem })
    await nextTick()
    expect(fetchItem).toHaveBeenCalledTimes(1)

    // A URL rewrite re-emits the same value; no second fetch.
    route.query = { ...route.query, sort: 'company' }
    await nextTick()
    expect(fetchItem).toHaveBeenCalledTimes(1)
  })

  it('does not touch the URL on close when the key was never present', async () => {
    const route = makeRoute({})
    const router = { replace: vi.fn() }
    const sync = useDialogRouteSync({ route, router, fetchItem: vi.fn() })
    await nextTick()

    sync.show({ id: 3 })
    await nextTick()
    sync.open.value = false
    await nextTick()

    expect(router.replace).not.toHaveBeenCalled()
  })
})
