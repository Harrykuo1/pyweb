import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import { createAuthGuard } from './index'

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

const homeRoute = { path: '/', fullPath: '/', meta: { requiresAuth: true } }
const loginRoute = { path: '/login', fullPath: '/login', meta: { requiresAuth: false } }
const membersRoute = { path: '/members', fullPath: '/members', meta: { requiresAuth: true } }

describe('auth guard', () => {
  it('redirects unauthenticated users from protected routes to /login with redirect query', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'fetchMe').mockResolvedValue()

    const guard = createAuthGuard()
    const result = await guard(membersRoute)

    expect(result).toEqual({
      path: '/login',
      query: { redirect: '/members' },
    })
  })

  it('allows authenticated users to access protected routes', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const guard = createAuthGuard()
    const result = await guard(homeRoute)

    expect(result).toBe(true)
  })

  it('bootstraps the session via fetchMe on the first navigation when user is null', async () => {
    const auth = useAuthStore()
    const fetchMe = vi.spyOn(auth, 'fetchMe').mockImplementation(async () => {
      auth.user = { id: 1, username: 'a', role: 'admin' }
    })

    const guard = createAuthGuard()
    const result = await guard(homeRoute)

    expect(fetchMe).toHaveBeenCalled()
    expect(result).toBe(true)
  })

  it('redirects authenticated users away from /login to /', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const guard = createAuthGuard()
    const result = await guard(loginRoute)

    expect(result).toEqual({ path: '/' })
  })

  it('lets unauthenticated users reach /login normally', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'fetchMe').mockResolvedValue()

    const guard = createAuthGuard()
    const result = await guard(loginRoute)

    expect(result).toBe(true)
  })

  it('does not call fetchMe again once user is populated', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const fetchMe = vi.spyOn(auth, 'fetchMe')

    const guard = createAuthGuard()
    await guard(homeRoute)
    await guard(homeRoute)

    expect(fetchMe).not.toHaveBeenCalled()
  })
})
