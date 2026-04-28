import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Jobs from './Jobs.vue'
import { jobsApi } from '../api/jobs'
import { useAuthStore } from '../stores/auth'

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
    job_month: 5,
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
    job_month: 3,
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
  vi.useRealTimers()
})

async function mountPage(items = sample, total = items.length, role = 'viewer') {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
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
      year: undefined,
      company: [],
      kind: undefined,
      q: undefined,
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
    expect(wrapper.text()).toContain('尚無符合條件的紀錄')
  })
})

describe('Jobs.vue — URL-driven state on first paint', () => {
  it('reads sort/order from route.query and uses them for the first fetch', async () => {
    routeQuery.value = { sort: 'company', order: 'asc' }
    const { listSpy, wrapper } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'company', order: 'asc' }),
    )
    const activePill = wrapper.find('[data-test="sort-company"]')
    expect(activePill.classes()).toContain('is-active')
  })

  it('falls back to defaults when query carries an unknown sort key', async () => {
    routeQuery.value = { sort: 'garbage', order: 'sideways' }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'created_at', order: 'desc' }),
    )
  })

  it('reads year, company, kind and q from route.query', async () => {
    routeQuery.value = {
      year: '2024',
      company: 'Acme',
      kind: 'internship',
      q: 'system',
    }
    const { listSpy, wrapper } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        year: 2024,
        company: ['Acme'],
        kind: 'internship',
        q: 'system',
      }),
    )
    expect(
      wrapper.find('[data-test="filter-kind-internship"]').classes(),
    ).toContain('is-active')
  })

  it('reads multiple company values from a repeated query param', async () => {
    routeQuery.value = { company: ['Acme', 'Globex'] }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ company: ['Acme', 'Globex'] }),
    )
  })

  it('drops year out of range or non-numeric on first paint', async () => {
    routeQuery.value = { year: '1999' }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ year: undefined }),
    )
  })
})

describe('Jobs.vue — toggleSort', () => {
  it('clicking a different pill switches the sort key and asks the API again', async () => {
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()

    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()

    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'company', order: 'asc' }),
    )
    expect(wrapper.find('[data-test="sort-company"]').classes()).toContain(
      'is-active',
    )
  })

  it('clicking the active pill flips order from asc to desc', async () => {
    const { wrapper, listSpy } = await mountPage()
    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()
    listSpy.mockClear()
    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'company', order: 'desc' }),
    )
  })
})

describe('Jobs.vue — kind filter chips', () => {
  it('clicking 實習 calls the API with kind=internship', async () => {
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()
    await wrapper.find('[data-test="filter-kind-internship"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'internship' }),
    )
    expect(
      wrapper.find('[data-test="filter-kind-internship"]').classes(),
    ).toContain('is-active')
  })

  it('clicking 正職 then 全部 clears the kind filter', async () => {
    const { wrapper, listSpy } = await mountPage()
    await wrapper.find('[data-test="filter-kind-fulltime"]').trigger('click')
    await flushPromises()
    listSpy.mockClear()
    await wrapper.find('[data-test="filter-kind-all"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ kind: undefined }),
    )
  })
})

describe('Jobs.vue — search debounce', () => {
  it('does not fire a request until the debounce window elapses', async () => {
    vi.useFakeTimers()
    const { wrapper, listSpy } = await mountPage()
    listSpy.mockClear()

    const input = wrapper.find('.filter-search input')
    await input.setValue('a')
    await input.setValue('ab')
    await input.setValue('abc')
    // Three keystrokes — none should have fired yet.
    expect(listSpy).not.toHaveBeenCalled()

    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(listSpy).toHaveBeenCalledTimes(1)
    expect(listSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'abc' }),
    )
  })
})

describe('Jobs.vue — URL sync on filter/sort changes', () => {
  it('writes non-default sort to the URL via router.replace', async () => {
    const { wrapper } = await mountPage()
    replaceMock.mockClear()

    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()

    expect(replaceMock).toHaveBeenLastCalledWith({
      query: { sort: 'company', order: 'asc' },
    })
  })

  it('writes the kind filter into the URL', async () => {
    const { wrapper } = await mountPage()
    replaceMock.mockClear()
    await wrapper.find('[data-test="filter-kind-fulltime"]').trigger('click')
    await flushPromises()
    expect(replaceMock).toHaveBeenLastCalledWith({
      query: { kind: 'fulltime' },
    })
  })

  it('writes a debounced search term into the URL', async () => {
    vi.useFakeTimers()
    const { wrapper } = await mountPage()
    replaceMock.mockClear()
    const input = wrapper.find('.filter-search input')
    await input.setValue('hello')
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(replaceMock).toHaveBeenLastCalledWith({ query: { q: 'hello' } })
  })

  it('strips defaults from the URL so a clean URL stays clean', async () => {
    routeQuery.value = { sort: 'company', order: 'asc' }
    const { wrapper } = await mountPage()
    replaceMock.mockClear()

    await wrapper.find('[data-test="sort-created_at"]').trigger('click')
    await flushPromises()
    expect(replaceMock).toHaveBeenLastCalledWith({ query: { order: 'asc' } })

    replaceMock.mockClear()
    await wrapper.find('[data-test="sort-created_at"]').trigger('click')
    await flushPromises()
    expect(replaceMock).toHaveBeenLastCalledWith({ query: {} })
  })
})

describe('Jobs.vue — company multi-select', () => {
  it('wires the remote-method to jobsApi.listCompanies and merges results into options', async () => {
    const { wrapper } = await mountPage()
    const select = wrapper.find('[data-test="filter-company"]')
      .findComponent({ name: 'ElSelect' })
    expect(select.exists()).toBe(true)
    expect(select.props('multiple')).toBe(true)
    expect(select.props('remote')).toBe(true)

    const listSpy = vi
      .spyOn(jobsApi, 'listCompanies')
      .mockResolvedValue(['Acme', 'AcmeInc'])

    const remoteMethod = select.props('remoteMethod')
    expect(typeof remoteMethod).toBe('function')

    await remoteMethod('ac')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith('ac')

    // Options should now include both fetched suggestions.
    const optionLabels = select.findAllComponents({ name: 'ElOption' })
      .map((o) => o.props('label'))
    expect(optionLabels).toEqual(expect.arrayContaining(['Acme', 'AcmeInc']))
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

describe('Jobs.vue — admin delete flow', () => {
  it('hides delete button for viewers', async () => {
    const { wrapper } = await mountPage(sample, sample.length, 'viewer')
    expect(wrapper.find('[data-test="delete-job-button"]').exists())
      .toBe(false)
  })

  it('shows delete button for admin and triggers the password dialog', async () => {
    const { wrapper } = await mountPage(sample, sample.length, 'admin')
    expect(wrapper.find('[data-test="delete-job-button"]').exists())
      .toBe(true)
  })

  it('calls jobsApi.remove with the entered password and refetches on success', async () => {
    const remove = vi.spyOn(jobsApi, 'remove').mockResolvedValue()
    const { wrapper, listSpy } = await mountPage(sample, sample.length, 'admin')

    // Click the delete affordance on the first card.
    await wrapper.find('[data-test="delete-job-button"]').trigger('click')
    await flushPromises()

    // Drive the confirm directly via the DeleteWithPasswordDialog's emit.
    const dialog = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })
    expect(dialog.exists()).toBe(true)
    listSpy.mockClear()
    dialog.vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(sample[0].id, 'admin-pw')
    expect(listSpy).toHaveBeenCalledTimes(1)
  })

  it('surfaces a 401 password-error message instead of refetching', async () => {
    const remove = vi.spyOn(jobsApi, 'remove').mockRejectedValue({
      response: { status: 401 },
    })
    const { wrapper, listSpy } = await mountPage(sample, sample.length, 'admin')

    await wrapper.find('[data-test="delete-job-button"]').trigger('click')
    await flushPromises()
    const dialog = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })

    listSpy.mockClear()
    dialog.vm.$emit('confirm', 'wrong')
    await flushPromises()

    expect(remove).toHaveBeenCalled()
    expect(dialog.props('errorMessage')).toBe('密碼錯誤')
    expect(listSpy).not.toHaveBeenCalled()
  })
})
