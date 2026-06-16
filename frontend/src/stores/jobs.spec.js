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
})
