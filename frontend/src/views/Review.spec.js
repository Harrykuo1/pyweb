import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Review from './Review.vue'
import { jobsApi } from '../api/jobs'
import { eventsApi } from '../api/events'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
  }
})

const JOBS = [
  {
    id: 1,
    company: 'Acme',
    kind: 'internship',
    display_name: 'Ada',
    job_year: 2024,
    experience_md: 'x',
  },
]
const EVENTS = [
  { id: 5, title: 'Party', event_date: '2026-01-01', author_display_name: 'Bo' },
]

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountReview(jobs = JOBS, events = EVENTS) {
  vi.spyOn(jobsApi, 'list').mockResolvedValue({ items: jobs, total: jobs.length })
  vi.spyOn(eventsApi, 'list').mockResolvedValue({
    items: events,
    total: events.length,
  })
  const wrapper = mount(Review)
  await flushPromises()
  return wrapper
}

describe('Review.vue', () => {
  it('renders pending job and event rows and the total count', async () => {
    const wrapper = await mountReview()
    expect(wrapper.findAll('[data-test="pending-job-row"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="pending-event-row"]')).toHaveLength(1)
    expect(wrapper.find('[data-test="pending-count"]').text()).toContain('2')
  })

  it('masks an anonymous job as 匿名 in the queue', async () => {
    const wrapper = await mountReview([
      { ...JOBS[0], is_anonymous: true, display_name: 'Ada' },
    ])
    // The real name must not show in the (streamable) review queue.
    expect(wrapper.find('[data-test="pending-job-row"]').text()).not.toContain(
      'Ada',
    )
    expect(wrapper.find('[data-test="pending-job-row"]').text()).toContain(
      '匿名',
    )
  })

  it('shows the empty state when nothing is pending', async () => {
    const wrapper = await mountReview([], [])
    expect(wrapper.find('[data-test="review-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pending-job-row"]').exists()).toBe(false)
  })

  it('accept approves the job via the api and drops its row', async () => {
    const wrapper = await mountReview()
    const accept = vi.spyOn(jobsApi, 'accept').mockResolvedValue({})

    await wrapper.find('[data-test="accept-job-1"]').trigger('click')
    await flushPromises()

    expect(accept).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-test="pending-job-row"]').exists()).toBe(false)
  })
})
