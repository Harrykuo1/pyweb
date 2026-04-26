import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { authApi } from './auth'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('authApi.login', () => {
  it('POSTs the password to /auth/login and returns the user', async () => {
    const fakeUser = { id: 1, username: 'admin', role: 'admin' }
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: fakeUser })

    const result = await authApi.login('pw')

    expect(post).toHaveBeenCalledWith('/auth/login', { password: 'pw' })
    expect(result).toEqual(fakeUser)
  })

  it('rethrows when the server returns an error', async () => {
    vi.spyOn(client, 'post').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    await expect(authApi.login('wrong')).rejects.toThrow()
  })
})

describe('authApi.logout', () => {
  it('POSTs to /auth/logout', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: null })

    await authApi.logout()

    expect(post).toHaveBeenCalledWith('/auth/logout')
  })
})

describe('authApi.getMe', () => {
  it('GETs /auth/me and returns the user payload', async () => {
    const fakeUser = { id: 2, username: 'viewer', role: 'viewer' }
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: fakeUser })

    const result = await authApi.getMe()

    expect(get).toHaveBeenCalledWith('/auth/me')
    expect(result).toEqual(fakeUser)
  })
})

describe('axios client', () => {
  it('uses /api baseURL and sends credentials', () => {
    expect(client.defaults.baseURL).toBe('/api')
    expect(client.defaults.withCredentials).toBe(true)
  })
})
