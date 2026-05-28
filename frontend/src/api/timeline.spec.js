import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { timelineApi } from './timeline'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('timelineApi.list', () => {
  it('GETs /timeline with no params by default', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [] } })
    await timelineApi.list()
    expect(get).toHaveBeenCalledWith('/timeline', { params: {} })
  })

  it('passes through limit when provided', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [] } })
    await timelineApi.list({ limit: 5 })
    expect(get).toHaveBeenCalledWith('/timeline', { params: { limit: 5 } })
  })

  it('passes through `before` cursor when provided', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], has_more: false } })
    const cursor = '2026-05-01T00:00:00Z'
    await timelineApi.list({ limit: 20, before: cursor })
    expect(get).toHaveBeenCalledWith('/timeline', {
      params: { limit: 20, before: cursor },
    })
  })

  it('omits `before` from params when not supplied', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], has_more: false } })
    await timelineApi.list({ limit: 20 })
    expect(get).toHaveBeenCalledWith('/timeline', { params: { limit: 20 } })
  })

  it('returns the {items} envelope unchanged', async () => {
    const fake = {
      items: [{ type: 'member_joined', member_id: 1, real_name: 'Alice' }],
    }
    vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await timelineApi.list()
    expect(result).toEqual(fake)
  })
})
