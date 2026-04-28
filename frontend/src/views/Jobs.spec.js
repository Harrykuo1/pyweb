import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Jobs from './Jobs.vue'
import { jobsApi } from '../api/jobs'

const replaceMock = vi.fn()
const routeQuery = { value: {} }

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get query() {
      return routeQuery.value
    },
  }),
  useRouter: () => ({ replace: replaceMock }),
}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(vi.fn(() => ({ close: vi.fn() })), {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    }),
  }
})

const sample = [
  {
    id: 1,
    job_year: 2024,
    company: 'Acme',
    kind: 'internship',
    real_name: 'Alice',
    timeline_md: null,
    experience_md: '## interview',
    created_at: '2024-05-01T00:00:00+00:00',
  },
  {
    id: 2,
    job_year: 2025,
    company: 'Globex',
    kind: 'fulltime',
    real_name: null,
    timeline_md: null,
    experience_md: 'x',
    created_at: '2025-03-15T00:00:00+00:00',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  routeQuery.value = {}
  replaceMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function mountPage(items = sample, total = items.length) {
  const listSpy = vi
    .spyOn(jobsApi, 'list')
    .mockResolvedValue({ items, total })
  const wrapper = mount(Jobs)
  await flushPromises()
  return { wrapper, listSpy }
}

describe('Jobs.vue — initial load', () => {
  it('calls api.list with default sort=created_at desc on mount', async () => {
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith({
      sort: 'created_at',
      order: 'desc',
    })
  })

  it('renders one card per item with company, kind tag, and date', async () => {
    const { wrapper } = await mountPage()
    const cards = wrapper.findAll('[data-test="record-card"]')
    expect(cards).toHaveLength(2)
    expect(wrapper.text()).toContain('Acme')
    expect(wrapper.text()).toContain('Globex')
    expect(wrapper.find('[data-test="kind-internship"]').text()).toContain('實習')
    expect(wrapper.find('[data-test="kind-fulltime"]').text()).toContain('正職')
  })

  it('shows the real name when present and 匿名 when null', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.find('[data-test="real-name"]').text()).toContain('Alice')
    expect(wrapper.find('[data-test="anonymous"]').text()).toContain('匿名')
  })

  it('shows the count chip with the response total', async () => {
    const { wrapper } = await mountPage(sample, 17)
    expect(wrapper.text()).toContain('17 筆')
  })
})

describe('Jobs.vue — empty state', () => {
  it('renders the empty placeholder when no items come back', async () => {
    const { wrapper } = await mountPage([], 0)
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚無求職紀錄')
  })
})

describe('Jobs.vue — URL-driven sort/order on first paint', () => {
  it('reads sort and order from route.query and uses them for the first fetch', async () => {
    routeQuery.value = { sort: 'company', order: 'asc' }
    const { listSpy, wrapper } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith({ sort: 'company', order: 'asc' })
    // Active pill is the URL-driven one, not the default created_at.
    const activePill = wrapper.find('[data-test="sort-company"]')
    expect(activePill.classes()).toContain('is-active')
  })

  it('falls back to defaults when query carries an unknown sort key', async () => {
    routeQuery.value = { sort: 'garbage', order: 'sideways' }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith({
      sort: 'created_at',
      order: 'desc',
    })
  })
})

describe('Jobs.vue — toggleSort', () => {
  it('clicking a different pill switches the sort key and asks the API again', async () => {
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()

    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()

    expect(listSpy).toHaveBeenCalledWith({ sort: 'company', order: 'asc' })
    expect(wrapper.find('[data-test="sort-company"]').classes()).toContain(
      'is-active',
    )
  })

  it('clicking the active pill flips order from asc to desc', async () => {
    const { wrapper, listSpy } = await mountPage()
    // First click: switch to company (asc)
    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()
    listSpy.mockClear()
    // Second click on the same pill: flip to desc
    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith({ sort: 'company', order: 'desc' })
  })

  it('clicking the kind pill cycles internship sort axis', async () => {
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()
    await wrapper.find('[data-test="sort-kind"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith({ sort: 'kind', order: 'asc' })
  })
})

describe('Jobs.vue — URL sync on sort changes', () => {
  it('writes non-default sort/order to the URL via router.replace', async () => {
    const { wrapper } = await mountPage()
    replaceMock.mockClear()

    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()

    expect(replaceMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith({
      query: { sort: 'company', order: 'asc' },
    })
  })

  it('strips defaults from the URL so a clean URL stays clean', async () => {
    routeQuery.value = { sort: 'company', order: 'asc' }
    const { wrapper } = await mountPage()
    replaceMock.mockClear()

    // Click company twice: first flips to desc, second back to asc — neither
    // matches the (created_at, desc) default. Then click the default pill:
    // should clear both query keys.
    await wrapper.find('[data-test="sort-created_at"]').trigger('click')
    await flushPromises()
    // sort=created_at + order=asc still has order!=default; one key gone.
    expect(replaceMock).toHaveBeenLastCalledWith({ query: { order: 'asc' } })

    // Click again: order flips to desc — now both default. Both stripped.
    replaceMock.mockClear()
    await wrapper.find('[data-test="sort-created_at"]').trigger('click')
    await flushPromises()
    expect(replaceMock).toHaveBeenLastCalledWith({ query: {} })
  })
})

describe('Jobs.vue — refresh button', () => {
  it('refetches when the refresh button is clicked', async () => {
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()
    await wrapper.find('[data-test="refresh-button"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledTimes(1)
  })
})
