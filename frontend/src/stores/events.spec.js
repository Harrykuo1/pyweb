import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useEventsStore } from './events'
import { eventsApi } from '../api/events'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

describe('useEventsStore', () => {
  it('fetch() forwards params and stores items + total', async () => {
    const list = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: [{ id: 1 }], total: 4 })
    const store = useEventsStore()

    await store.fetch({ order: 'asc' })

    expect(list).toHaveBeenCalledWith({ order: 'asc' })
    expect(store.items).toEqual([{ id: 1 }])
    expect(store.total).toBe(4)
    expect(store.loading).toBe(false)
  })

  it('a cache miss shows loading, a cache hit does not and still revalidates', async () => {
    const list = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: [], total: 0 })
    const store = useEventsStore()
    const params = { order: 'desc' }

    let resolveCold
    list.mockReturnValueOnce(
      new Promise((r) => {
        resolveCold = () => r({ items: [], total: 0 })
      }),
    )
    const cold = store.fetch(params)
    expect(store.loading).toBe(true)
    resolveCold()
    await cold

    list.mockClear()
    const warm = store.fetch(params)
    expect(store.loading).toBe(false)
    expect(store.revalidating).toBe(true)
    await warm
    expect(list).toHaveBeenCalledTimes(1)
  })

  it('invalidate() drops the cache so the next identical fetch is cold', async () => {
    vi.spyOn(eventsApi, 'list').mockResolvedValue({ items: [], total: 0 })
    const store = useEventsStore()
    const params = { order: 'desc' }
    await store.fetch(params)

    store.invalidate()

    const next = store.fetch(params)
    expect(store.loading).toBe(true)
    await next
  })
})
