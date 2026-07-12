import { describe, expect, it, vi } from 'vitest'

import { handleAuthResponseError } from './client'

function makeContext({ routeName = 'members', fullPath = '/members' } = {}) {
  const auth = { clearLocal: vi.fn() }
  const router = {
    currentRoute: { value: { name: routeName, fullPath } },
    push: vi.fn(),
  }
  const message = { warning: vi.fn() }
  return { auth, router, message }
}

describe('handleAuthResponseError', () => {
  it('passes through non-401 errors untouched', async () => {
    const ctx = makeContext()
    const err = { response: { status: 500 }, config: { url: '/members' } }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)
    expect(ctx.auth.clearLocal).not.toHaveBeenCalled()
    expect(ctx.router.push).not.toHaveBeenCalled()
    expect(ctx.message.warning).not.toHaveBeenCalled()
  })

  it('on 401 from a non-login endpoint clears auth, toasts, and redirects to /login with the current path', async () => {
    const ctx = makeContext({
      routeName: 'members',
      fullPath: '/members?q=alice',
    })
    const err = { response: { status: 401 }, config: { url: '/members/1' } }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)

    expect(ctx.auth.clearLocal).toHaveBeenCalledOnce()
    expect(ctx.message.warning).toHaveBeenCalledWith(
      '您的登入已失效，請重新登入',
    )
    expect(ctx.router.push).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/members?q=alice' },
    })
  })

  it('on a suspended 401 redirects to /login with error=account_suspended and no generic toast', async () => {
    const ctx = makeContext({ routeName: 'members', fullPath: '/members' })
    const err = {
      response: { status: 401, data: { detail: 'Account suspended' } },
      config: { url: '/members/1' },
    }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)

    expect(ctx.auth.clearLocal).toHaveBeenCalledOnce()
    expect(ctx.message.warning).not.toHaveBeenCalled()
    expect(ctx.router.push).toHaveBeenCalledWith({
      path: '/login',
      query: { error: 'account_suspended' },
    })
  })

  it('on 401 from /auth/login does NOT clear auth or redirect, so the form can show "wrong password"', async () => {
    const ctx = makeContext({ routeName: 'login', fullPath: '/login' })
    const err = { response: { status: 401 }, config: { url: '/auth/login' } }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)

    expect(ctx.auth.clearLocal).not.toHaveBeenCalled()
    expect(ctx.router.push).not.toHaveBeenCalled()
    expect(ctx.message.warning).not.toHaveBeenCalled()
  })

  it('on 401 from /auth/me passes through untouched so the router guard can handle bootstrap', async () => {
    // Boot path: router beforeEach awaits fetchMe, which fires /auth/me.
    // If the interceptor also pushes /login, two navigations race during
    // a single guard run and the app gets stuck.
    const ctx = makeContext({ routeName: undefined, fullPath: '/' })
    const err = { response: { status: 401 }, config: { url: '/auth/me' } }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)

    expect(ctx.auth.clearLocal).not.toHaveBeenCalled()
    expect(ctx.router.push).not.toHaveBeenCalled()
    expect(ctx.message.warning).not.toHaveBeenCalled()
  })

  it('on 401 while already on /login does not push or toast (no redirect loop)', async () => {
    const ctx = makeContext({ routeName: 'login', fullPath: '/login' })
    // A non-exempt endpoint — e.g. some background fetch from a login-
    // page widget that happens to 401.
    const err = { response: { status: 401 }, config: { url: '/members' } }

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)

    // clearLocal still runs — local state should match the server state
    // even when we don't bounce the user.
    expect(ctx.auth.clearLocal).toHaveBeenCalledOnce()
    expect(ctx.router.push).not.toHaveBeenCalled()
    expect(ctx.message.warning).not.toHaveBeenCalled()
  })

  it('passes through errors with no response object (e.g. network errors)', async () => {
    const ctx = makeContext()
    const err = new Error('Network down')

    await expect(handleAuthResponseError(err, ctx)).rejects.toBe(err)
    expect(ctx.auth.clearLocal).not.toHaveBeenCalled()
    expect(ctx.router.push).not.toHaveBeenCalled()
  })
})
