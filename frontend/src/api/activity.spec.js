import { afterEach, describe, expect, it, vi } from 'vitest'
import client from './client'
import { activityApi } from './activity'
afterEach(() => vi.restoreAllMocks())
describe('activity API', () => {
  it('serializes arrays as repeated query keys and preserves snowflakes', async () => {
    const spy = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { summary: {} } })
    const signal = new AbortController().signal
    await activityApi.analytics(
      {
        start_date: '2026-10-01',
        hour_start: 0,
        user_ids: ['960893399014211614', '101'],
        weekdays: [0, 6],
        channel_ids: [],
      },
      signal,
    )
    const [url, config] = spy.mock.calls[0]
    expect(url).toBe('/activity/analytics')
    expect(config.params.getAll('user_ids')).toEqual([
      '960893399014211614',
      '101',
    ])
    expect(config.params.getAll('weekdays')).toEqual(['0', '6'])
    expect(config.params.get('hour_start')).toBe('0')
    expect(config.params.has('channel_ids')).toBe(false)
    expect(config.signal).toBe(signal)
  })
  it('loads filter options and propagates errors', async () => {
    const spy = vi
      .spyOn(client, 'get')
      .mockResolvedValueOnce({ data: { users: [] } })
      .mockRejectedValueOnce(new Error('offline'))
    expect(await activityApi.options()).toEqual({ users: [] })
    expect(spy.mock.calls[0][0]).toBe('/activity/options')
    await expect(activityApi.options()).rejects.toThrow('offline')
  })
})
