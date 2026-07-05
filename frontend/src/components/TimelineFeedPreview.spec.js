import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import TimelineFeedPreview from './TimelineFeedPreview.vue'
import { timelineApi } from '../api/timeline'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

const ONE_HOUR_AGO = '2026-05-05T11:00:00Z'

beforeEach(() => {
  pushMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function mountPreview(items, props = {}) {
  vi.spyOn(timelineApi, 'list').mockResolvedValue({ items })
  const wrapper = mount(TimelineFeedPreview, { props })
  await flushPromises()
  return wrapper
}

describe('TimelineFeedPreview.vue', () => {
  it('shows skeleton rows while loading', async () => {
    let resolve
    vi.spyOn(timelineApi, 'list').mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    const wrapper = mount(TimelineFeedPreview)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="hero-feed-loading"]').exists()).toBe(true)
    resolve({ items: [] })
    await flushPromises()
    expect(wrapper.find('[data-test="hero-feed-loading"]').exists()).toBe(false)
  })

  it('renders the empty state when no items return', async () => {
    const wrapper = await mountPreview([])
    expect(wrapper.find('[data-test="hero-feed-empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚無動態')
  })

  it('caps requested limit by passing it to the API', async () => {
    const spy = vi.spyOn(timelineApi, 'list').mockResolvedValue({ items: [] })
    mount(TimelineFeedPreview, { props: { limit: 4 } })
    await flushPromises()
    expect(spy).toHaveBeenCalledWith({ limit: 4 })
  })

  it('renders a member_joined row with the name and verb', async () => {
    const wrapper = await mountPreview([
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
    const row = wrapper.find('[data-test="hero-feed-row-member_joined"]')
    expect(row.exists()).toBe(true)
    expect(row.text()).toContain('Alice')
    expect(row.text()).toContain('加入了社群')
  })

  it('renders a job_created row showing the company', async () => {
    const wrapper = await mountPreview([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 9,
        company: 'Acme',
        kind: 'internship',
        category: null,
        real_name: 'Bob',
        job_year: 2026,
        job_month: 5,
      },
    ])
    const row = wrapper.find('[data-test="hero-feed-row-job_created"]')
    expect(row.exists()).toBe(true)
    expect(row.text()).toContain('Bob')
    expect(row.text()).toContain('Acme')
  })

  it('falls back to 匿名成員 for jobs without a real_name', async () => {
    const wrapper = await mountPreview([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 9,
        company: 'Globex',
        kind: 'fulltime',
        category: null,
        real_name: null,
        job_year: 2026,
        job_month: 5,
      },
    ])
    expect(wrapper.text()).toContain('匿名成員')
  })

  it('deep-links member rows via membersApi.focusRoute', async () => {
    const wrapper = await mountPreview([
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
      .find('[data-test="hero-feed-row-member_joined"]')
      .trigger('click')
    expect(pushMock).toHaveBeenCalledWith({
      path: '/members',
      query: { focus: '12' },
    })
  })

  it('deep-links job rows via jobsApi.detailRoute', async () => {
    const wrapper = await mountPreview([
      {
        type: 'job_created',
        timestamp: ONE_HOUR_AGO,
        job_id: 9,
        company: 'Acme',
        kind: 'internship',
        category: null,
        real_name: 'Bob',
        job_year: 2026,
        job_month: 5,
      },
    ])
    await wrapper
      .find('[data-test="hero-feed-row-job_created"]')
      .trigger('click')
    expect(pushMock).toHaveBeenCalledWith({
      path: '/jobs',
      query: { detail: '9' },
    })
  })

  it('查看全部 link scrolls to the configured anchor', async () => {
    document.body.innerHTML = '<div id="timeline-feed-section"></div>'
    const target = document.getElementById('timeline-feed-section')
    target.scrollIntoView = vi.fn()
    const wrapper = await mountPreview([])
    await wrapper.find('[data-test="hero-feed-link"]').trigger('click')
    expect(target.scrollIntoView).toHaveBeenCalled()
  })

  it('renders an <img> inside the avatar when a member has a photo', async () => {
    const wrapper = await mountPreview([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 7,
        real_name: 'Alice',
        institution: 'NTU',
        position: null,
        has_photo: true,
        photo_updated_at: '2026-05-04T00:00:00Z',
      },
    ])
    const row = wrapper.find('[data-test="hero-feed-row-member_joined"]')
    const img = row.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('/api/members/7/photo')
    expect(img.attributes('src')).toContain('v=')
  })

  it('falls back to a letter circle when the member has no photo', async () => {
    const wrapper = await mountPreview([
      {
        type: 'member_joined',
        timestamp: ONE_HOUR_AGO,
        member_id: 8,
        real_name: 'Bob',
        institution: 'NTU',
        position: null,
        has_photo: false,
        photo_updated_at: null,
      },
    ])
    const row = wrapper.find('[data-test="hero-feed-row-member_joined"]')
    expect(row.find('img').exists()).toBe(false)
    expect(row.text()).toContain('B')
  })

  it('tints job_created avatars by kind so internship vs fulltime is visible', async () => {
    const wrapper = await mountPreview([
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
        timestamp: ONE_HOUR_AGO,
        job_id: 2,
        company: 'Globex',
        kind: 'fulltime',
        category: null,
        real_name: 'Dave',
        job_year: 2026,
        job_month: 5,
      },
    ])
    const rows = wrapper.findAll('[data-test="hero-feed-row-job_created"]')
    expect(rows.length).toBe(2)
    const firstAvatar = rows[0].find('.hero-feed-avatar')
    const secondAvatar = rows[1].find('.hero-feed-avatar')
    expect(firstAvatar.classes()).toContain('hero-feed-avatar--kind-internship')
    expect(secondAvatar.classes()).toContain('hero-feed-avatar--kind-fulltime')
  })
})
