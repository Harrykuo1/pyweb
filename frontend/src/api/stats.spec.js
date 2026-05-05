import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { statsApi } from './stats'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('statsApi.get', () => {
  it('GETs /stats and returns the response data', async () => {
    const fake = {
      total_members: 12,
      total_jobs: 30,
      total_companies: 18,
      year_min: 2020,
      year_max: 2026,
    }
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await statsApi.get()
    expect(get).toHaveBeenCalledWith('/stats')
    expect(result).toEqual(fake)
  })
})
