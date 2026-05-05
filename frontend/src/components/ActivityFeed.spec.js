import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ActivityFeed from './ActivityFeed.vue'
import { activityApi } from '../api/activity'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

const NOW_ISO = '2026-05-05T12:00:00Z'
const ONE_HOUR_AGO = '2026-05-05T11:00:00Z'
const TWO_HOURS_AGO = '2026-05-05T10:00:00Z'

beforeEach(() => {
  pushMock.mockClear()
  // Pin "now" so the relative-time formatter is stable across runs.
  vi.useFakeTimers()
  vi.setSystemTime(new Date(NOW_ISO))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

async function mountFeed(items) {
  const listSpy = vi
    .spyOn(activityApi, 'list')
    .mockResolvedValue({ items })
  const wrapper = mount(ActivityFeed)
  await flushPromises()
  return { wrapper, listSpy }
}

describe('ActivityFeed.vue', () => {
  it('shows skeleton rows while loading', async () => {
    let resolve
    vi.spyOn(activityApi, 'list').mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const wrapper = mount(ActivityFeed)
    // onMounted's load() flips `loading` to true on a microtask, and the
    // ElCollapseTransition wrapper means the body re-renders one extra
    // tick later — wait for both before asserting.
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="activity-loading"]').exists()).toBe(true)

    resolve({ items: [] })
    await flushPromises()
    expect(wrapper.find('[data-test="activity-loading"]').exists()).toBe(false)
  })

  it('shows the empty state when no items return', async () => {
    const { wrapper } = await mountFeed([])
    expect(wrapper.find('[data-test="activity-empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('目前還沒有動態')
  })

  it('shows an error state when the API rejects', async () => {
    vi.spyOn(activityApi, 'list').mockRejectedValue(new Error('boom'))
    const wrapper = mount(ActivityFeed)
    await flushPromises()
    expect(wrapper.find('[data-test="activity-error"]').exists()).toBe(true)
  })

  it('renders a member_joined row with name, institution, position', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 1,
        real_name: 'Alice',
        institution: 'NTU CSIE',
        position: 'SWE Intern',
        has_photo: false,
        photo_updated_at: null,
      },
    ])
    const row = wrapper.find('[data-test="activity-row-member_joined"]')
    expect(row.exists()).toBe(true)
    expect(row.text()).toContain('Alice')
    expect(row.text()).toContain('加入了社群')
    expect(row.text()).toContain('NTU CSIE')
    expect(row.text()).toContain('SWE Intern')
  })

  it('renders a job_created row with the kind chip', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 2,
        company: 'Acme',
        kind: 'internship',
        category: 'Backend',
        real_name: 'Bob',
        job_year: 2026,
        job_month: 5,
      },
    ])
    const row = wrapper.find('[data-test="activity-row-job_created"]')
    expect(row.exists()).toBe(true)
    expect(row.text()).toContain('Bob')
    expect(row.text()).toContain('新增了一筆求職紀錄')
    expect(row.text()).toContain('實習')
    expect(row.text()).toContain('Acme')
    expect(row.text()).toContain('Backend')
  })

  it('renders an anonymous job_created row as 匿名成員', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 3,
        company: 'Globex',
        kind: 'fulltime',
        category: null,
        real_name: null,
        job_year: 2026,
        job_month: 5,
      },
    ])
    const row = wrapper.find('[data-test="activity-row-job_created"]')
    expect(row.text()).toContain('匿名成員')
    expect(row.text()).toContain('正職')
  })

  it('navigates to /members on member_joined click', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 1,
        real_name: 'Alice',
        institution: 'NTU',
        position: null,
        has_photo: false,
        photo_updated_at: null,
      },
    ])
    await wrapper
      .find('[data-test="activity-row-member_joined"]')
      .trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('navigates to /jobs on job_created click', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'job_created',
        timestamp: TWO_HOURS_AGO,
        job_id: 9,
        company: 'Acme',
        kind: 'internship',
        category: null,
        real_name: 'Carol',
        job_year: 2026,
        job_month: 5,
      },
    ])
    await wrapper.find('[data-test="activity-row-job_created"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/jobs')
  })

  it('activates a row via Enter key for keyboard accessibility', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 1,
        real_name: 'Alice',
        institution: 'NTU',
        position: null,
        has_photo: false,
        photo_updated_at: null,
      },
    ])
    await wrapper
      .find('[data-test="activity-row-member_joined"]')
      .trigger('keydown', { key: 'Enter' })
    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('passes the limit prop through to the API', async () => {
    const listSpy = vi
      .spyOn(activityApi, 'list')
      .mockResolvedValue({ items: [] })
    mount(ActivityFeed, { props: { limit: 5 } })
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith({ limit: 5 })
  })
})

describe('ActivityFeed.vue — collapse / expand', () => {
  it('defaults to expanded on every mount and labels the toggle 收合', async () => {
    const { wrapper } = await mountFeed([])
    const toggle = wrapper.find('[data-test="activity-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.text()).toContain('收合')
  })

  it('flips aria-expanded and the label on click', async () => {
    const { wrapper } = await mountFeed([])
    const toggle = wrapper.find('[data-test="activity-toggle"]')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.text()).toContain('展開')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.text()).toContain('收合')
  })

  it('does not refetch when collapsing then re-expanding within a session', async () => {
    const { wrapper, listSpy } = await mountFeed([])
    expect(listSpy).toHaveBeenCalledTimes(1)
    const toggle = wrapper.find('[data-test="activity-toggle"]')
    await toggle.trigger('click') // collapse
    await toggle.trigger('click') // expand
    await flushPromises()
    expect(listSpy).toHaveBeenCalledTimes(1)
  })
})
