import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { membersApi } from './members'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('membersApi.list', () => {
  it('GETs /members with default order=asc', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await membersApi.list()
    expect(get).toHaveBeenCalledWith('/members', { params: { order: 'asc' } })
  })

  it('passes through order=desc', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await membersApi.list({ order: 'desc' })
    expect(get).toHaveBeenCalledWith('/members', { params: { order: 'desc' } })
  })

  it('returns the response data array', async () => {
    const fake = [{ id: 1, real_name: 'A' }]
    vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await membersApi.list()
    expect(result).toEqual(fake)
  })
})

describe('membersApi.get', () => {
  it('GETs /members/:id', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: { id: 5 } })
    const result = await membersApi.get(5)
    expect(get).toHaveBeenCalledWith('/members/5')
    expect(result).toEqual({ id: 5 })
  })
})

describe('membersApi.create', () => {
  it('POSTs payload to /members', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const payload = { graduation_year: 2024, real_name: 'A', current_position: 'B' }
    const result = await membersApi.create(payload)
    expect(post).toHaveBeenCalledWith('/members', payload)
    expect(result).toEqual({ id: 1 })
  })
})

describe('membersApi.update', () => {
  it('PUTs partial payload to /members/:id', async () => {
    const put = vi.spyOn(client, 'put').mockResolvedValue({
      data: { id: 5, real_name: 'New' },
    })
    const result = await membersApi.update(5, { real_name: 'New' })
    expect(put).toHaveBeenCalledWith('/members/5', { real_name: 'New' })
    expect(result.real_name).toBe('New')
  })
})

describe('membersApi.remove', () => {
  it('DELETEs /members/:id', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({ data: null })
    await membersApi.remove(7)
    expect(del).toHaveBeenCalledWith('/members/7')
  })
})
