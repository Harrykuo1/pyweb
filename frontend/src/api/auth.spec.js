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

describe('authApi.listAdminContacts', () => {
  it('GETs /auth/admin-contacts and returns the list', async () => {
    const contacts = [{ display_name: 'Harry', discord_username: 'as6325400' }]
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: contacts })

    const result = await authApi.listAdminContacts()

    expect(get).toHaveBeenCalledWith('/auth/admin-contacts')
    expect(result).toEqual(contacts)
  })
})

describe('authApi.listUsers', () => {
  it('GETs /auth/users and returns the array', async () => {
    const fakeUsers = [
      { id: 1, username: 'admin', role: 'admin' },
      { id: 2, username: 'viewer', role: 'viewer' },
    ]
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: fakeUsers })

    const result = await authApi.listUsers()

    expect(get).toHaveBeenCalledWith('/auth/users')
    expect(result).toEqual(fakeUsers)
  })
})

describe('authApi.updateUsername', () => {
  it('PATCHes /auth/users/{role}/username and returns the updated user', async () => {
    const updated = { id: 2, username: 'watcher', role: 'viewer' }
    const patch = vi.spyOn(client, 'patch').mockResolvedValue({ data: updated })

    const result = await authApi.updateUsername('viewer', 'watcher')

    expect(patch).toHaveBeenCalledWith('/auth/users/viewer/username', {
      username: 'watcher',
    })
    expect(result).toEqual(updated)
  })
})

describe('authApi.updatePassword', () => {
  it('PATCHes /auth/users/{role}/password with both fields', async () => {
    const patch = vi.spyOn(client, 'patch').mockResolvedValue({ data: null })

    await authApi.updatePassword('admin', 'old', 'new')

    expect(patch).toHaveBeenCalledWith('/auth/users/admin/password', {
      current_password: 'old',
      new_password: 'new',
    })
  })
})

describe('axios client', () => {
  it('uses /api baseURL and sends credentials', () => {
    expect(client.defaults.baseURL).toBe('/api')
    expect(client.defaults.withCredentials).toBe(true)
  })
})
