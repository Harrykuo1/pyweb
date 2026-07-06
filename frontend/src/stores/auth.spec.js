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

  it('needsProfile is true only for a member without a profile', () => {
    const store = useAuthStore()
    store.user = { id: 3, role: 'member', has_profile: false }
    expect(store.needsProfile).toBe(true)

    store.user = { id: 3, role: 'member', has_profile: true }
    expect(store.needsProfile).toBe(false)

    store.user = { id: 1, role: 'admin', has_profile: false }
    expect(store.needsProfile).toBe(false)
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

  it('clearLocal() resets user and viewAsViewer without calling the api', async () => {
    const logout = vi.spyOn(authApi, 'logout').mockResolvedValue()
    const store = useAuthStore()
    store.user = { id: 1, username: 'admin', role: 'admin' }
    store.setViewAsViewer(true)

    store.clearLocal()

    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.viewAsViewer).toBe(false)
    expect(logout).not.toHaveBeenCalled()
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

  // ---------- viewAsViewer (admin preview mode) ----------

  it('admin can toggle viewAsViewer; isAdmin becomes false in that mode', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      id: 1,
      username: 'admin',
      role: 'admin',
    })

    const store = useAuthStore()
    await store.login('pw')

    expect(store.isActuallyAdmin).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(store.isViewingAsViewer).toBe(false)

    store.setViewAsViewer(true)
    expect(store.isActuallyAdmin).toBe(true)
    expect(store.isAdmin).toBe(false)
    expect(store.isViewingAsViewer).toBe(true)

    store.setViewAsViewer(false)
    expect(store.isAdmin).toBe(true)
    expect(store.isViewingAsViewer).toBe(false)
  })

  it('non-admin call to setViewAsViewer is ignored', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      id: 2,
      username: 'viewer',
      role: 'viewer',
    })

    const store = useAuthStore()
    await store.login('pw')

    store.setViewAsViewer(true)
    expect(store.viewAsViewer).toBe(false)
    expect(store.isAdmin).toBe(false)
    expect(store.isViewingAsViewer).toBe(false)
  })

  it('login resets a stale viewAsViewer flag', async () => {
    vi.spyOn(authApi, 'login')
      .mockResolvedValueOnce({ id: 1, username: 'admin', role: 'admin' })
      .mockResolvedValueOnce({ id: 1, username: 'admin', role: 'admin' })

    const store = useAuthStore()
    await store.login('pw')
    store.setViewAsViewer(true)
    expect(store.viewAsViewer).toBe(true)

    await store.login('pw')
    expect(store.viewAsViewer).toBe(false)
  })

  it('logout clears viewAsViewer too', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      id: 1,
      username: 'admin',
      role: 'admin',
    })
    vi.spyOn(authApi, 'logout').mockResolvedValue()

    const store = useAuthStore()
    await store.login('pw')
    store.setViewAsViewer(true)
    await store.logout()

    expect(store.viewAsViewer).toBe(false)
  })

  // ---------- updateUsername / updatePassword ----------

  it('updateUsername calls api and refreshes own user when self renamed', async () => {
    const store = useAuthStore()
    store.user = { id: 1, username: 'admin', role: 'admin' }

    vi.spyOn(authApi, 'updateUsername').mockResolvedValue({
      id: 1,
      username: 'boss',
      role: 'admin',
    })

    const result = await store.updateUsername('admin', 'boss')

    expect(authApi.updateUsername).toHaveBeenCalledWith('admin', 'boss')
    expect(result.username).toBe('boss')
    expect(store.user.username).toBe('boss')
  })

  it('updateUsername does not change current user when renaming the other account', async () => {
    const store = useAuthStore()
    store.user = { id: 1, username: 'admin', role: 'admin' }

    vi.spyOn(authApi, 'updateUsername').mockResolvedValue({
      id: 2,
      username: 'watcher',
      role: 'viewer',
    })

    await store.updateUsername('viewer', 'watcher')

    expect(store.user.username).toBe('admin')
  })

  it('updatePassword forwards to api and resolves', async () => {
    const spy = vi.spyOn(authApi, 'updatePassword').mockResolvedValue()

    const store = useAuthStore()
    await store.updatePassword('viewer', 'old', 'new')

    expect(spy).toHaveBeenCalledWith('viewer', 'old', 'new')
  })

  it('updatePassword rethrows api errors', async () => {
    vi.spyOn(authApi, 'updatePassword').mockRejectedValue(
      Object.assign(new Error('409'), { response: { status: 409 } }),
    )

    const store = useAuthStore()
    await expect(store.updatePassword('viewer', 'a', 'b')).rejects.toThrow()
  })
})
