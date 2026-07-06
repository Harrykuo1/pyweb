import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useReviewQueue } from './useReviewQueue'
import { jobsApi } from '../api/jobs'
import { eventsApi } from '../api/events'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(
    vi.fn(() => ({ close: vi.fn() })),
    { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  ),
  ElMessageBox: { prompt: vi.fn() },
}))

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

function mountQueue() {
  let api
  const Host = {
    setup() {
      api = useReviewQueue()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.spyOn(jobsApi, 'list').mockResolvedValue({ items: JOBS, total: 1 })
  vi.spyOn(eventsApi, 'list').mockResolvedValue({ items: EVENTS, total: 1 })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useReviewQueue', () => {
  it('loads pending jobs and events on mount with status=pending', async () => {
    const { get } = mountQueue()
    await flushPromises()
    const a = get()
    expect(jobsApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'pending' }),
    )
    expect(eventsApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'pending' }),
    )
    expect(a.jobs.value).toHaveLength(1)
    expect(a.events.value).toHaveLength(1)
    expect(a.pendingCount.value).toBe(2)
  })

  it('accept calls the api, drops the row and toasts success', async () => {
    const { get } = mountQueue()
    await flushPromises()
    const a = get()
    const spy = vi.spyOn(jobsApi, 'accept').mockResolvedValue({})

    await a.accept('job', JOBS[0])

    expect(spy).toHaveBeenCalledWith(1)
    expect(a.jobs.value).toHaveLength(0)
    expect(a.pendingCount.value).toBe(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已通過')
  })

  it('reject prompts for a reason, calls reject (trimmed) and drops the row', async () => {
    const { get } = mountQueue()
    await flushPromises()
    const a = get()
    ElMessageBox.prompt.mockResolvedValue({ value: '  內容不足  ' })
    const spy = vi.spyOn(eventsApi, 'reject').mockResolvedValue({})

    await a.reject('event', EVENTS[0])

    expect(spy).toHaveBeenCalledWith(5, '內容不足')
    expect(a.events.value).toHaveLength(0)
    expect(ElMessage.success).toHaveBeenCalledWith('已退回')
  })

  it('reject does nothing when the reason prompt is cancelled', async () => {
    const { get } = mountQueue()
    await flushPromises()
    const a = get()
    ElMessageBox.prompt.mockRejectedValue('cancel')
    const spy = vi.spyOn(jobsApi, 'reject').mockResolvedValue({})

    await a.reject('job', JOBS[0])

    expect(spy).not.toHaveBeenCalled()
    expect(a.jobs.value).toHaveLength(1)
  })
})
