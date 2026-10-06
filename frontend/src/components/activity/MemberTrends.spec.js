import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import MemberTrends from './MemberTrends.vue'
import { activityApi } from '../../api/activity'
vi.mock('../../api/activity', () => ({
  activityApi: { memberTrends: vi.fn() },
}))
enableAutoUnmount(afterEach)
const filters = {
  end_date: '2026-10-05',
  start_date: '2026-01-01',
  timezone: 'Asia/Taipei',
  hour_start: 18,
  hour_end: 24,
  weekdays: [0],
  channel_ids: ['201'],
  user_ids: [],
}
const users = [
  { user_id: '101', name: 'Alice' },
  { user_id: '102', name: 'Bob' },
]
function payload() {
  return {
    current_start: '2026-09-29',
    current_end: '2026-10-05',
    previous_start: '2026-09-22',
    previous_end: '2026-09-28',
    window_days: 7,
    eligible_current_days: 1,
    eligible_previous_days: 1,
    excluded_today: true,
    series: users.map((u, i) => ({
      ...u,
      current_messages: 4,
      previous_messages: 2,
      current_messages_rate: 4,
      previous_messages_rate: 2,
      current_voice_minutes: 1,
      previous_voice_minutes: 0,
      current_voice_minutes_rate: 1,
      previous_voice_minutes_rate: 0,
      messages_change_percent: i ? -50 : 100,
      voice_minutes_change_percent: null,
      daily: Array.from({ length: 14 }, (_, j) => ({
        date: `2026-09-${j + 1}`,
        messages: j % 3,
        messages_avg7: 1,
        voice_minutes: j,
        voice_minutes_avg7: 2,
      })),
    })),
  }
}
const stubs = {
  ElSelect: {
    props: ['modelValue', 'multipleLimit'],
    emits: ['update:modelValue'],
    template: '<div class="select"><slot/></div>',
  },
  ElOption: true,
}
async function render() {
  const w = mount(MemberTrends, {
    props: { filters, members: users, users },
    global: { stubs },
  })
  await flushPromises()
  return w
}
beforeEach(() => {
  vi.clearAllMocks()
  activityApi.memberTrends.mockResolvedValue(payload())
})
describe('member frequency comparison', () => {
  it('draws each member, rates and directions with the scoped query', async () => {
    const w = await render()
    expect(activityApi.memberTrends.mock.lastCall[0]).toEqual({
      end_date: filters.end_date,
      window_days: 7,
      timezone: filters.timezone,
      hour_start: 18,
      hour_end: 24,
      weekdays: [0],
      channel_ids: ['201'],
      user_ids: ['101', '102'],
    })
    expect(w.findAll('polyline')).toHaveLength(2)
    expect(w.text()).toContain('↑ 100%')
    expect(w.text()).toContain('↓ 50%')
    expect(w.text()).toContain('今天尚未結束，已排除')
    expect(w.findComponent(stubs.ElSelect).props('multipleLimit')).toBe(6)
    await w.find('svg g[tabindex]').trigger('focus')
    expect(w.find('.readout').text()).toContain('Alice 1')
  })
  it('switches raw / averaged curves and metric without fetching', async () => {
    const w = await render()
    const original = w.find('polyline').attributes('points')
    await w.findAll('.modes button')[1].trigger('click')
    expect(w.find('polyline').attributes('points')).not.toBe(original)
    await w.setProps({ metric: 'voice_minutes' })
    expect(w.text()).toContain('前期無紀錄')
    expect(w.text()).toContain('並非實際發言時長')
    expect(w.text()).not.toContain('Infinity')
    expect(activityApi.memberTrends).toHaveBeenCalledTimes(1)
  })
  it('requests a different comparison window and passes changed parent filters', async () => {
    const w = await render()
    await w.findAll('.periods button')[2].trigger('click')
    await flushPromises()
    expect(activityApi.memberTrends.mock.lastCall[0].window_days).toBe(30)
    await w.setProps({ filters: { ...filters, channel_ids: ['203'] } })
    await flushPromises()
    expect(activityApi.memberTrends.mock.lastCall[0].channel_ids).toEqual([
      '203',
    ])
  })
  it('clears the selection without an invalid request', async () => {
    const w = await render()
    w.findComponent(stubs.ElSelect).vm.$emit('update:modelValue', [])
    await flushPromises()
    expect(w.text()).toContain('選擇成員，開始比較')
    expect(w.findAll('polyline')).toHaveLength(0)
    expect(activityApi.memberTrends).toHaveBeenCalledTimes(1)
  })
  it('ignores stale responses and aborts on unmount', async () => {
    let resolve
    activityApi.memberTrends.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r
        }),
    )
    const w = await render()
    const signal = activityApi.memberTrends.mock.calls[0][1]
    await w.findAll('.periods button')[1].trigger('click')
    await flushPromises()
    expect(signal.aborted).toBe(true)
    resolve({ ...payload(), series: [] })
    await flushPromises()
    expect(w.findAll('polyline')).toHaveLength(2)
    const current = activityApi.memberTrends.mock.lastCall[1]
    w.unmount()
    expect(current.aborted).toBe(true)
  })
  it('handles failure and retries', async () => {
    activityApi.memberTrends.mockRejectedValueOnce(new Error('offline'))
    const w = await render()
    expect(w.find('[role="alert"]').text()).toContain('載入失敗')
    await w.find('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(w.findAll('polyline')).toHaveLength(2)
  })
})
