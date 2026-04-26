import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { authApi } from '../api/auth'
import { useAuthStore } from './auth'

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useAuthStore', () => {
  it('starts unauthenticated', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.isAdmin).toBe(false)
  })

  it('login() stores the returned user and flips isAuthenticated', async () => {
    const fakeUser = { id: 1, username: 'admin', role: 'admin' }
    vi.spyOn(authApi, 'login').mockResolvedValue(fakeUser)

    const store = useAuthStore()
    await store.login('pw')

    expect(store.user).toEqual(fakeUser)
    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(true)
  })

  it('isAdmin is false for viewer role', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      id: 2,
      username: 'viewer',
      role: 'viewer',
    })

    const store = useAuthStore()
    await store.login('pw')

    expect(store.isAuthenticated).toBe(true)
    expect(store.isAdmin).toBe(false)
  })

  it('login() leaves user null and rethrows on failure', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const store = useAuthStore()
    await expect(store.login('wrong')).rejects.toThrow()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('logout() calls api and clears user', async () => {
    const logout = vi.spyOn(authApi, 'logout').mockResolvedValue()
    const store = useAuthStore()
    store.user = { id: 1, username: 'admin', role: 'admin' }

    await store.logout()

    expect(logout).toHaveBeenCalled()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('fetchMe() populates user when session is valid', async () => {
    const fakeUser = { id: 3, username: 'someone', role: 'viewer' }
    vi.spyOn(authApi, 'getMe').mockResolvedValue(fakeUser)

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.user).toEqual(fakeUser)
  })

  it('fetchMe() swallows 401 and leaves user null', async () => {
    vi.spyOn(authApi, 'getMe').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const store = useAuthStore()
    await expect(store.fetchMe()).resolves.toBeUndefined()
    expect(store.user).toBeNull()
  })

  it('fetchMe() rethrows non-401 errors', async () => {
    vi.spyOn(authApi, 'getMe').mockRejectedValue(
      Object.assign(new Error('500'), { response: { status: 500 } }),
    )

    const store = useAuthStore()
    await expect(store.fetchMe()).rejects.toThrow()
  })
})
