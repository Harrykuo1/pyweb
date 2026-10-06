import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, enableAutoUnmount } from '@vue/test-utils'
import { reactive } from 'vue'
import Activity from './Activity.vue'
import { activityApi } from '../api/activity'
import { defaultFilters } from '../components/activity/activityUtils'

vi.mock('../api/activity', () => ({
  activityApi: { options: vi.fn(), analytics: vi.fn() },
}))
const routing = vi.hoisted(() => ({
  route: null,
  replace: vi.fn(),
  push: vi.fn(),
}))
vi.mock('vue-router', () => ({
  useRoute: () => routing.route,
  useRouter: () => ({ replace: routing.replace, push: routing.push }),
}))
enableAutoUnmount(afterEach)
const metrics = {
  messages: 10,
  voice_minutes: 120,
  active_members: 2,
  active_days: 1,
  replies: 2,
  attachments: 3,
  text_characters: 50,
}
function payload(filters = defaultFilters()) {
  return {
    filters: { ...filters },
    summary: { ...metrics },
    daily: [{ date: filters.start_date, ...metrics }],
    hourly: Array.from({ length: 24 }, (_, hour) => ({ ...metrics, hour })),
    rhythm: Array.from({ length: 168 }, (_, i) => ({
      ...metrics,
      weekday: Math.floor(i / 24),
      hour: i % 24,
    })),
    members: [
      { ...metrics, user_id: '101', name: 'Alice', member_id: 1 },
      {
        ...metrics,
        messages: 2,
        voice_minutes: 240,
        user_id: '102',
        name: 'Discord · 102',
        member_id: null,
      },
    ],
    channels: [{ ...metrics, channel_id: '201' }],
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  routing.route = reactive({ query: {} })
  routing.replace.mockImplementation(async ({ query }) => {
    routing.route.query = query
  })
  activityApi.options.mockResolvedValue({
    configured: true,
    users: [{ user_id: '101', name: 'Alice' }],
    channels: ['201'],
  })
  activityApi.analytics.mockImplementation(async (filters) => payload(filters))
})
const stubs = {
  MemberTrends: true,
  ChannelNames: true,
  ElSelect: { props: ['modelValue'], template: '<div><slot/></div>' },
  ElOption: { template: '<span/>' },
}
async function render() {
  const wrapper = mount(Activity, { global: { stubs } })
  await flushPromises()
  return wrapper
}

describe('community activity dashboard', () => {
  it('renders real API totals, charts, members, units and source limitations', async () => {
    const wrapper = await render()
    expect(wrapper.findAll('.metric-card')).toHaveLength(4)
    expect(wrapper.findAll('.metric-number')[1].text()).toBe('2小時')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('每日貢獻熱圖')
    expect(wrapper.text()).toContain('並非實際發言時長')
    expect(wrapper.findAll('.hour-bar')).toHaveLength(24)
    expect(wrapper.findAll('.rhythm-row button')).toHaveLength(168)
    expect(wrapper.find('[data-test="contribution-grid"]').exists()).toBe(true)
    expect(wrapper.find('.error-panel').exists()).toBe(false)
  })
  it('uses synced names while retaining channel IDs for filters and fallback', async () => {
    activityApi.options.mockResolvedValue({
      configured: true,
      users: [],
      channels: ['201'],
      channel_names: { 201: '聊天大廳' },
    })
    const wrapper = await render()
    expect(wrapper.find('.channel-row').text()).toContain('聊天大廳')
    expect(wrapper.find('.channel-row').attributes('title')).toContain('201')
    await wrapper.find('.channel-row').trigger('click')
    await flushPromises()
    expect(activityApi.analytics.mock.lastCall[0].channel_ids).toEqual(['201'])
  })
  it('switches metric and reorders members without making another request', async () => {
    const wrapper = await render()
    await wrapper.findAll('.metric-switch button')[1].trigger('click')
    expect(wrapper.classes()).toContain('metric-voice')
    expect(wrapper.find('.person-details strong').text()).toBe('Discord · 102')
    expect(activityApi.analytics).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.contribution').classes()).toContain('is-voice')
  })
  it('applies evening preset, persists it in the URL and fetches the same filters', async () => {
    const wrapper = await render()
    await wrapper.findAll('.presets button').at(-1).trigger('click')
    await flushPromises()
    expect(routing.replace).toHaveBeenCalled()
    expect(activityApi.analytics.mock.lastCall[0]).toMatchObject({
      hour_start: 18,
      hour_end: 24,
    })
    const f = activityApi.analytics.mock.lastCall[0]
    expect((Date.parse(f.end_date) - Date.parse(f.start_date)) / 86400000).toBe(
      4,
    )
  })
  it('drills into days, members, channels and weekday/hour cells', async () => {
    const wrapper = await render()
    await wrapper.find('.day-cell:not(.blank)').trigger('click')
    await flushPromises()
    let f = activityApi.analytics.mock.lastCall[0]
    expect(f.start_date).toBe(f.end_date)
    await wrapper.find('.person-button').trigger('click')
    await flushPromises()
    expect(activityApi.analytics.mock.lastCall[0].user_ids).toEqual(['101'])
    await wrapper.find('.channel-row').trigger('click')
    await flushPromises()
    expect(activityApi.analytics.mock.lastCall[0].channel_ids).toEqual(['201'])
    await wrapper.findAll('.rhythm-row button')[24 + 18].trigger('click')
    await flushPromises()
    expect(activityApi.analytics.mock.lastCall[0]).toMatchObject({
      weekdays: [1],
      hour_start: 18,
      hour_end: 19,
    })
  })
  it('restores URL filters and rejects invalid dates before issuing a request', async () => {
    routing.route.query = {
      start_date: '2026-10-01',
      end_date: '2026-10-05',
      weekdays: ['3'],
      user_ids: ['101'],
      hour_start: '18',
    }
    const wrapper = await render()
    expect(activityApi.analytics.mock.calls[0][0]).toMatchObject({
      start_date: '2026-10-01',
      weekdays: [3],
      user_ids: ['101'],
      hour_start: 18,
    })
    await wrapper.find('[aria-label="結束日期"]').setValue('2026-09-01')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('1 至 366 天')
    expect(activityApi.analytics).toHaveBeenCalledTimes(1)
  })
  it('shows empty data honestly and allows retrying an API error', async () => {
    activityApi.analytics.mockRejectedValueOnce(new Error('offline'))
    const wrapper = await render()
    expect(wrapper.find('[role="alert"]').text()).toContain('暫時無法')
    activityApi.analytics.mockImplementationOnce(async (f) => ({
      ...payload(f),
      summary: {
        ...metrics,
        messages: 0,
        voice_minutes: 0,
        active_members: 0,
        active_days: 0,
      },
      members: [],
      channels: [],
    }))
    await wrapper.find('.error-panel button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="empty-activity"]').exists()).toBe(true)
    expect(wrapper.find('.error-panel').exists()).toBe(false)
  })
  it('cancels older queries and prevents their responses overwriting newer data', async () => {
    let finishOld
    activityApi.analytics.mockImplementationOnce(
      (f) =>
        new Promise((resolve) => {
          finishOld = () =>
            resolve({
              ...payload(f),
              members: [{ ...metrics, user_id: '1', name: 'stale-user' }],
            })
        }),
    )
    const wrapper = mount(Activity, { global: { stubs } })
    await flushPromises()
    const oldSignal = activityApi.analytics.mock.calls[0][1]
    routing.route.query = { start_date: '2026-10-01', end_date: '2026-10-05' }
    await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    finishOld()
    await flushPromises()
    expect(wrapper.text()).not.toContain('stale-user')
    expect(wrapper.text()).toContain('Alice')
    const lastSignal = activityApi.analytics.mock.lastCall[1]
    wrapper.unmount()
    expect(lastSignal.aborted).toBe(true)
  })
  it('reports failed option loading without hiding the dashboard', async () => {
    activityApi.options.mockRejectedValueOnce(new Error('offline'))
    const wrapper = await render()
    expect(wrapper.find('.options-error').exists()).toBe(true)
    expect(wrapper.findAll('.metric-card')).toHaveLength(4)
    await wrapper.find('.options-error button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.options-error').exists()).toBe(false)
  })
})
