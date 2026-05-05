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

// Latest IntersectionObserver instance + callback created during a test.
// jsdom doesn't ship the API, so we install a tiny manual stand-in that
// captures the constructor args; tests then fire `intersect()` to
// simulate the user scrolling the sentinel into view.
let observerInstances = []

class MockIntersectionObserver {
  constructor(callback, options) {
    this.callback = callback
    this.options = options
    this.observed = []
    observerInstances.push(this)
  }
  observe(el) {
    this.observed.push(el)
  }
  unobserve(el) {
    this.observed = this.observed.filter((x) => x !== el)
  }
  disconnect() {
    this.observed = []
  }
}

function fireIntersect(isIntersecting = true) {
  // Always poke the most recently created observer — ActivityFeed
  // disconnects and recreates one on every loadMore round-trip, so the
  // freshest instance is the only one still hooked to a live sentinel.
  const obs = observerInstances[observerInstances.length - 1]
  if (!obs) throw new Error('No IntersectionObserver was constructed')
  obs.callback([{ isIntersecting }])
}

beforeEach(() => {
  pushMock.mockClear()
  observerInstances = []
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  // Pin "now" so the relative-time formatter is stable across runs.
  vi.useFakeTimers()
  vi.setSystemTime(new Date(NOW_ISO))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

async function mountFeed(items, { hasMore = false, props = {} } = {}) {
  const listSpy = vi
    .spyOn(activityApi, 'list')
    .mockResolvedValue({ items, has_more: hasMore })
  const wrapper = mount(ActivityFeed, { props })
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

    resolve({ items: [], has_more: false })
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

  it('tints the job avatar by kind so internship vs fulltime is visible', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 1,
        company: 'Acme',
        kind: 'internship',
        category: null,
        real_name: 'Carol',
        job_year: 2026,
        job_month: 5,
      },
      {
        type: 'job_created',
        timestamp: TWO_HOURS_AGO,
        job_id: 2,
        company: 'Globex',
        kind: 'fulltime',
        category: null,
        real_name: 'Dave',
        job_year: 2026,
        job_month: 5,
      },
    ])
    const rows = wrapper.findAll('[data-test="activity-row-job_created"]')
    expect(rows.length).toBe(2)
    expect(rows[0].find('.row-avatar--job').classes()).toContain(
      'row-avatar--kind-internship',
    )
    expect(rows[1].find('.row-avatar--job').classes()).toContain(
      'row-avatar--kind-fulltime',
    )
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

  it('deep-links to /members?focus=<id> on member_joined click', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 12,
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
    expect(pushMock).toHaveBeenCalledWith({
      path: '/members',
      query: { focus: '12' },
    })
  })

  it('deep-links to /jobs?detail=<id> on job_created click', async () => {
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
    expect(pushMock).toHaveBeenCalledWith({
      path: '/jobs',
      query: { detail: '9' },
    })
  })

  it('activates a row via Enter key for keyboard accessibility', async () => {
    const { wrapper } = await mountFeed([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 12,
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
    expect(pushMock).toHaveBeenCalledWith({
      path: '/members',
      query: { focus: '12' },
    })
  })

  it('passes the pageSize prop through to the API as `limit`', async () => {
    const listSpy = vi
      .spyOn(activityApi, 'list')
      .mockResolvedValue({ items: [], has_more: false })
    mount(ActivityFeed, { props: { pageSize: 5 } })
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

describe('ActivityFeed.vue — lazy load (cursor pagination)', () => {
  function memberItem(id, timestamp, real_name = `Member${id}`) {
    return {
      type: 'member_joined',
      timestamp,
      member_id: id,
      real_name,
      institution: 'NTU',
      position: null,
      has_photo: false,
      photo_updated_at: null,
    }
  }

  it('does not render the sentinel when has_more is false', async () => {
    const { wrapper } = await mountFeed([memberItem(1, ONE_HOUR_AGO)], {
      hasMore: false,
    })
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(false)
  })

  it('renders the sentinel when has_more is true', async () => {
    const { wrapper } = await mountFeed([memberItem(1, ONE_HOUR_AGO)], {
      hasMore: true,
    })
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(true)
  })

  it('fetches the next batch with `before = lastItem.timestamp` when sentinel intersects', async () => {
    // First call: 1 item, has_more=true. Second call: cursor walk.
    const listSpy = vi.spyOn(activityApi, 'list')
    listSpy.mockResolvedValueOnce({
      items: [memberItem(1, ONE_HOUR_AGO)],
      has_more: true,
    })
    listSpy.mockResolvedValueOnce({
      items: [memberItem(2, TWO_HOURS_AGO)],
      has_more: false,
    })
    const wrapper = mount(ActivityFeed, { props: { pageSize: 1 } })
    await flushPromises()

    fireIntersect(true)
    await flushPromises()

    expect(listSpy).toHaveBeenNthCalledWith(1, { limit: 1 })
    expect(listSpy).toHaveBeenNthCalledWith(2, {
      limit: 1,
      before: ONE_HOUR_AGO,
    })
    // Both rows now in the DOM; sentinel is gone (has_more=false).
    expect(
      wrapper.findAll('[data-test="activity-row-member_joined"]').length,
    ).toBe(2)
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(false)
  })

  it('appends successive pages and keeps the sentinel until has_more flips false', async () => {
    const listSpy = vi.spyOn(activityApi, 'list')
    listSpy.mockResolvedValueOnce({
      items: [memberItem(1, '2026-05-05T11:00:00Z')],
      has_more: true,
    })
    listSpy.mockResolvedValueOnce({
      items: [memberItem(2, '2026-05-05T10:00:00Z')],
      has_more: true,
    })
    listSpy.mockResolvedValueOnce({
      items: [memberItem(3, '2026-05-05T09:00:00Z')],
      has_more: false,
    })
    const wrapper = mount(ActivityFeed, { props: { pageSize: 1 } })
    await flushPromises()

    fireIntersect(true)
    await flushPromises()
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(true)

    fireIntersect(true)
    await flushPromises()
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(false)
    expect(
      wrapper.findAll('[data-test="activity-row-member_joined"]').length,
    ).toBe(3)
    expect(listSpy).toHaveBeenCalledTimes(3)
  })

  it('ignores non-intersecting observer events', async () => {
    const listSpy = vi
      .spyOn(activityApi, 'list')
      .mockResolvedValue({
        items: [memberItem(1, ONE_HOUR_AGO)],
        has_more: true,
      })
    mount(ActivityFeed, { props: { pageSize: 1 } })
    await flushPromises()

    fireIntersect(false)
    await flushPromises()

    // Only the initial fetch — the false event is a no-op.
    expect(listSpy).toHaveBeenCalledTimes(1)
  })

  it('hides the sentinel after a failed lazy-load fetch (silent failure)', async () => {
    const listSpy = vi.spyOn(activityApi, 'list')
    listSpy.mockResolvedValueOnce({
      items: [memberItem(1, ONE_HOUR_AGO)],
      has_more: true,
    })
    listSpy.mockRejectedValueOnce(new Error('network down'))
    const wrapper = mount(ActivityFeed, { props: { pageSize: 1 } })
    await flushPromises()
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(true)

    fireIntersect(true)
    await flushPromises()

    // The first row is still there; the sentinel disappears so the
    // observer doesn't get re-armed and refire on every scroll.
    expect(
      wrapper.findAll('[data-test="activity-row-member_joined"]').length,
    ).toBe(1)
    expect(wrapper.find('[data-test="activity-sentinel"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="activity-error"]').exists()).toBe(false)
  })
})
