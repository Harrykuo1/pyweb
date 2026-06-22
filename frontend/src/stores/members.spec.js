import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMembersStore } from './members'
import { membersApi } from '../api/members'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

describe('useMembersStore', () => {
  it('fetch() loads the full list', async () => {
    const list = vi
      .spyOn(membersApi, 'list')
      .mockResolvedValue([{ id: 1 }, { id: 2 }])
    const store = useMembersStore()

    await store.fetch()

    expect(list).toHaveBeenCalled()
    expect(store.members).toEqual([{ id: 1 }, { id: 2 }])
    expect(store.loading).toBe(false)
  })

  it('a cold fetch shows loading; a warm one revalidates without it', async () => {
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue([])
    const store = useMembersStore()

    let resolveCold
    list.mockReturnValueOnce(
      new Promise((r) => {
        resolveCold = () => r([])
      }),
    )
    const cold = store.fetch()
    expect(store.loading).toBe(true)
    resolveCold()
    await cold

    list.mockClear()
    const warm = store.fetch()
    expect(store.loading).toBe(false)
    expect(store.revalidating).toBe(true)
    await warm
    expect(list).toHaveBeenCalledTimes(1)
    expect(store.revalidating).toBe(false)
  })

  it('invalidate() makes the next fetch cold again', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue([])
    const store = useMembersStore()
    await store.fetch()

    store.invalidate()

    const next = store.fetch()
    expect(store.loading).toBe(true)
    await next
  })
})
