import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import Home from './Home.vue'
import { activityApi } from '../api/activity'
import { membersApi } from '../api/members'
import { statsApi } from '../api/stats'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

const SAMPLE_STATS = {
  total_members: 12,
  total_jobs: 30,
  total_companies: 18,
  year_min: 2020,
  year_max: 2026,
}

function makeMembers(n) {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    graduation_year: 2025,
    real_name: `Member${i + 1}`,
    institution: 'NTU',
    position: null,
    resume_md: null,
    joined_at: `2025-01-${String(i + 1).padStart(2, '0')}T00:00:00+00:00`,
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
    photo_updated_at: null,
    resume_pdf_updated_at: null,
  }))
}

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.mockClear()
  // Force prefers-reduced-motion so useCounter mirrors its source
  // synchronously — happy-dom doesn't pump rAF inside flushPromises,
  // and we don't want these tests to depend on real timing.
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  )
  // ActivityFeed installs an IntersectionObserver on mount; jsdom
  // doesn't provide one, so stub a no-op class. Home tests don't drive
  // lazy-load behavior — that's covered in ActivityFeed.spec — they
  // just need the constructor to exist.
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  vi.spyOn(activityApi, 'list').mockResolvedValue({
    items: [],
    has_more: false,
  })
  vi.spyOn(statsApi, 'get').mockResolvedValue(SAMPLE_STATS)
  vi.spyOn(membersApi, 'list').mockResolvedValue(makeMembers(SAMPLE_STATS.total_members))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Home.vue — bootstrap', () => {
  it('mounts without throwing when the user is not yet populated', () => {
    const wrapper = mount(Home)
    expect(wrapper.exists()).toBe(true)
  })
})

describe('Home.vue — spotlight stat + member pile', () => {
  it('renders the community member count in the spotlight', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    await flushPromises()
    const spotlight = wrapper.find('[data-test="spotlight-number"]')
    expect(spotlight.exists()).toBe(true)
    expect(spotlight.text()).toContain('12')
    expect(spotlight.text()).toContain('位')
  })

  it('renders a stacked avatar pile when at least the minimum members exist', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    const pile = wrapper.find('[data-test="member-pile"]')
    expect(pile.exists()).toBe(true)
    // Cap at 6 in the pile, regardless of how many were returned.
    expect(pile.findAll('.pile-avatar').length).toBe(6)
  })

  it('shows a +N overflow pip when there are more members than fit in the pile', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    // 12 total - 6 in pile = +6 overflow.
    expect(wrapper.find('[data-test="member-pile"]').text()).toContain('+6')
  })

  it('hides the pile and shows an empty-state subtitle when DB is empty', async () => {
    statsApi.get.mockResolvedValue({
      total_members: 0,
      total_jobs: 0,
      total_companies: 0,
      year_min: null,
      year_max: null,
    })
    membersApi.list.mockResolvedValue([])
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    expect(wrapper.find('[data-test="member-pile"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="hero-sub"]').text()).toContain(
      '社群剛剛起步',
    )
  })

  it('hides the pile when below the minimum threshold but still shows the count', async () => {
    statsApi.get.mockResolvedValue({
      total_members: 2,
      total_jobs: 0,
      total_companies: 0,
      year_min: null,
      year_max: null,
    })
    membersApi.list.mockResolvedValue(makeMembers(2))
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    expect(wrapper.find('[data-test="member-pile"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="spotlight-number"]').text()).toContain('2')
    expect(wrapper.find('[data-test="hero-sub"]').text()).toContain('學長姊')
  })

  it('clicking the spotlight CTA navigates to /members', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    await wrapper.find('[data-test="spotlight-cta"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('clicking a pile avatar deep-links to that specific member', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    // Sample fixture has 12 members; the first one (id=1) sits at the
    // front of the pile.
    const avatar = wrapper.find('[data-test="pile-avatar-1"]')
    expect(avatar.exists()).toBe(true)
    await avatar.trigger('click')
    expect(pushMock).toHaveBeenCalledWith({
      path: '/members',
      query: { focus: '1' },
    })
  })

  it('renders the jobs mini-stat with the live count', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    const tile = wrapper.find('[data-test="mini-stat-jobs"]')
    expect(tile.exists()).toBe(true)
    expect(tile.text()).toContain('30')
    expect(tile.text()).toContain('求職紀錄')
  })

  it('clicking the jobs mini-stat navigates to /jobs', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    await wrapper.find('[data-test="mini-stat-jobs"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/jobs')
  })

  it('renders the activities mini-stat as a 規劃中 placeholder', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    const tile = wrapper.find('[data-test="mini-stat-activities"]')
    expect(tile.exists()).toBe(true)
    expect(tile.text()).toContain('規劃中')
    expect(tile.text()).toContain('活動紀錄')
    // Placeholder is a div, not a button — no router push on click.
    expect(tile.element.tagName.toLowerCase()).toBe('div')
    expect(tile.attributes('aria-disabled')).toBe('true')
  })

  it('still renders cleanly when the stats API rejects', async () => {
    statsApi.get.mockRejectedValue(new Error('boom'))
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    expect(wrapper.find('[data-test="spotlight-cta"]').exists()).toBe(true)
  })
})

describe('Home.vue — feature grid', () => {
  it('renders the three feature cards', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    expect(wrapper.text()).toContain('成員介紹')
    expect(wrapper.text()).toContain('求職紀錄')
    expect(wrapper.text()).toContain('活動紀錄')
  })

  it('clicking the members card navigates to /members', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await wrapper.find('[data-test="card-members"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/members')
  })

  it('clicking the jobs card navigates to /jobs', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await wrapper.find('[data-test="card-jobs"]').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/jobs')
  })
})

describe('Home.vue — activity preview integration', () => {
  it('mounts the in-hero activity preview alongside the spotlight', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    const wrapper = mount(Home)
    await flushPromises()
    expect(wrapper.find('[data-test="hero-feed"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="spotlight-card"]').exists()).toBe(true)
  })

  it('boots the standalone feed with the configured pageSize as the first batch', async () => {
    // The full feed below the hero now lazy-loads via cursor pagination;
    // its first request is just `limit=<pageSize>` (no `before` cursor).
    // Subsequent batches are driven by the IntersectionObserver inside
    // ActivityFeed itself and aren't asserted from here.
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'alice', role: 'admin' }
    mount(Home)
    await flushPromises()
    expect(activityApi.list).toHaveBeenCalledWith({ limit: 20 })
  })
})
