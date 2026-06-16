import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useJobsStore } from './jobs'
import { jobsApi } from '../api/jobs'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

describe('useJobsStore', () => {
  it('starts empty and not loading', () => {
    const store = useJobsStore()
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
  })

  it('fetch() forwards params to the API and stores items + total', async () => {
    const list = vi
      .spyOn(jobsApi, 'list')
      .mockResolvedValue({ items: [{ id: 1 }], total: 5 })
    const store = useJobsStore()

    const params = { sort: 'company', order: 'asc' }
    await store.fetch(params)

    expect(list).toHaveBeenCalledWith(params)
    expect(store.items).toEqual([{ id: 1 }])
    expect(store.total).toBe(5)
    expect(store.loading).toBe(false)
  })

  it('toggles loading true during the call and false after', async () => {
    let resolve
    vi.spyOn(jobsApi, 'list').mockReturnValue(
      new Promise((r) => {
        resolve = () => r({ items: [], total: 0 })
      }),
    )
    const store = useJobsStore()

    const pending = store.fetch({})
    expect(store.loading).toBe(true)

    resolve()
    await pending
    expect(store.loading).toBe(false)
  })

  it('resets loading even when the API rejects', async () => {
    vi.spyOn(jobsApi, 'list').mockRejectedValue(new Error('boom'))
    const store = useJobsStore()

    await expect(store.fetch({})).rejects.toThrow('boom')
    expect(store.loading).toBe(false)
  })

  describe('stale-while-revalidate cache', () => {
    it('a cache miss shows the skeleton (loading), a cache hit does not', async () => {
      const list = vi
        .spyOn(jobsApi, 'list')
        .mockResolvedValue({ items: [{ id: 1 }], total: 1 })
      const store = useJobsStore()
      const params = { sort: 'created_at', order: 'desc' }

      // Cold: skeleton flips on during the in-flight request.
      let resolveCold
      list.mockReturnValueOnce(
        new Promise((r) => {
          resolveCold = () => r({ items: [{ id: 1 }], total: 1 })
        }),
      )
      const cold = store.fetch(params)
      expect(store.loading).toBe(true)
      resolveCold()
      await cold
      expect(store.loading).toBe(false)

      // Warm: same params paint cached rows without ever flipping loading,
      // and still refetch in the background.
      list.mockClear()
      const warm = store.fetch(params)
      expect(store.loading).toBe(false)
      expect(store.revalidating).toBe(true)
      expect(store.items).toEqual([{ id: 1 }])
      await warm
      expect(list).toHaveBeenCalledTimes(1)
      expect(store.revalidating).toBe(false)
    })

    it('caches each distinct params set separately', async () => {
      const list = vi
        .spyOn(jobsApi, 'list')
        .mockResolvedValue({ items: [], total: 0 })
      const store = useJobsStore()

      await store.fetch({ kind: 'internship' })
      await store.fetch({ kind: 'fulltime' })
      list.mockClear()

      // Both are now warm — neither re-cold-fetches (loading stays false).
      await store.fetch({ kind: 'internship' })
      expect(store.loading).toBe(false)
      await store.fetch({ kind: 'fulltime' })
      expect(store.loading).toBe(false)
      expect(list).toHaveBeenCalledTimes(2) // background revalidations only
    })

    it('invalidate() drops the cache so the next identical fetch is cold', async () => {
      vi.spyOn(jobsApi, 'list').mockResolvedValue({ items: [], total: 0 })
      const store = useJobsStore()
      const params = { kind: 'internship' }

      await store.fetch(params) // warms the cache

      store.invalidate()

      // Cache gone → this fetch is a cold miss → skeleton shows again.
      const next = store.fetch(params)
      expect(store.loading).toBe(true)
      await next
    })
  })
})
