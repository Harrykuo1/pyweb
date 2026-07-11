import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Jobs from './Jobs.vue'
import { jobsApi } from '../api/jobs'
import { useAuthStore } from '../stores/auth'
import { useJobsStore } from '../stores/jobs'

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
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      },
    ),
  }
})

const sample = [
  {
    id: 1,
    job_year: 2024,
    job_month: 5,
    company: 'Acme',
    kind: 'internship',
    display_name: 'Alice',
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
    display_name: null,
    timeline_md: null,
    experience_md: 'x',
    created_at: '2025-03-15T00:00:00+00:00',
  },
]

// The same rows as the backend would return them to someone allowed to edit
// (admin, or the owning member): can_edit drives the edit/delete affordances.
const ownedSample = sample.map((j) => ({ ...j, can_edit: true }))

let pendingTeardowns = []

beforeEach(() => {
  setActivePinia(createPinia())
  routeQuery.value = {}
  replaceMock.mockClear()
})

afterEach(() => {
  // Unmount every Jobs instance a test mounted so their watchers, debounces
  // and URL-sync timers don't accumulate and interfere with later tests.
  for (const w of pendingTeardowns) w.unmount()
  pendingTeardowns = []
  vi.restoreAllMocks()
  vi.useRealTimers()
})

async function mountPage(
  items = sample,
  total = items.length,
  role = 'viewer',
  preview = false,
) {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
  if (preview) auth.previewAsMember = true
  const listSpy = vi.spyOn(jobsApi, 'list').mockResolvedValue({ items, total })
  const wrapper = mount(Jobs)
  pendingTeardowns.push(wrapper)
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
      category: [],
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
    expect(wrapper.find('[data-test="kind-internship"]').text()).toContain(
      '實習',
    )
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

  it('renders the category chip with an inner text span (marquee target)', async () => {
    // The hover-marquee animates an inner .category-chip-text span
    // independently of the chip outer; assert the structure is intact
    // so the marquee handler can find its target. Animation itself is
    // not testable in jsdom (no layout), so this is structural only.
    const withCategory = [{ ...sample[0], category: 'Design Verification' }]
    const { wrapper } = await mountPage(withCategory)
    const chip = wrapper.find('[data-test="card-category"]')
    expect(chip.exists()).toBe(true)
    const inner = chip.find('.category-chip-text')
    expect(inner.exists()).toBe(true)
    expect(inner.text()).toBe('Design Verification')
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
  it('restricts to accepted posts when an admin previews as a member', async () => {
    const { listSpy } = await mountPage(sample, sample.length, 'admin', true)
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'accepted' }),
    )
  })

  it('does not restrict status for a real admin (not previewing)', async () => {
    const { listSpy } = await mountPage(sample, sample.length, 'admin', false)
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ status: undefined }),
    )
  })

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

  it('reads category from route.query as an array', async () => {
    routeQuery.value = { category: ['Backend', 'DevOps'] }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ category: ['Backend', 'DevOps'] }),
    )
  })

  it('reads a single category value as a one-item array', async () => {
    routeQuery.value = { category: 'Backend' }
    const { listSpy } = await mountPage()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ category: ['Backend'] }),
    )
  })
})

describe('Jobs.vue — category filter', () => {
  it('renders the filter-category multi-select with placeholder', async () => {
    const { wrapper } = await mountPage()
    const select = wrapper.find('[data-test="filter-category"]')
    expect(select.exists()).toBe(true)
    expect(wrapper.text()).toContain('職類（可多選）')
  })

  it('calls jobsApi.listCategories on remote keystrokes', async () => {
    const listCategoriesSpy = vi
      .spyOn(jobsApi, 'listCategories')
      .mockResolvedValue(['Backend', 'DevOps'])
    const { wrapper } = await mountPage()

    const select = wrapper.findComponent('[data-test="filter-category"]')
    // Trigger the remote-method by invoking the prop directly — the
    // el-select internal input wiring would otherwise need a real focus
    // sequence under happy-dom.
    await select.vm.remoteMethod('de')
    await flushPromises()

    expect(listCategoriesSpy).toHaveBeenCalledWith('de')
  })

  it('renders a category chip on cards that have a category', async () => {
    const items = [
      { ...sample[0], id: 11, category: 'Backend' },
      { ...sample[1], id: 12, category: null },
    ]
    const { wrapper } = await mountPage(items)
    const chips = wrapper.findAll('[data-test="card-category"]')
    expect(chips).toHaveLength(1)
    expect(chips[0].text()).toBe('Backend')
  })

  it('search input placeholder is the new 姓名、心得內文 copy', async () => {
    const { wrapper } = await mountPage()
    const input = wrapper.find('.filter-search input')
    expect(input.attributes('placeholder')).toBe('搜尋姓名、心得內文')
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
    const select = wrapper
      .find('[data-test="filter-company"]')
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
    const optionLabels = select
      .findAllComponents({ name: 'ElOption' })
      .map((o) => o.props('label'))
    expect(optionLabels).toEqual(expect.arrayContaining(['Acme', 'AcmeInc']))
  })
})

describe('Jobs.vue — ?detail=<id> deep-link', () => {
  it('fetches the targeted job and opens the detail dialog on mount', async () => {
    routeQuery.value = { detail: '7' }
    const getSpy = vi.spyOn(jobsApi, 'get').mockResolvedValue({
      id: 7,
      job_year: 2025,
      job_month: 5,
      company: 'Linked',
      kind: 'internship',
      display_name: 'Eve',
      timeline_md: null,
      experience_md: 'deep-linked',
      created_at: '2025-05-01T00:00:00+00:00',
    })
    const { wrapper } = await mountPage()
    await flushPromises()

    expect(getSpy).toHaveBeenCalledWith(7)
    const dialog = wrapper.findComponent({ name: 'JobDetailDialog' })
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('modelValue')).toBe(true)
    expect(dialog.props('job')).toMatchObject({ id: 7, company: 'Linked' })
  })

  it('ignores a non-numeric ?detail value and never fetches', async () => {
    routeQuery.value = { detail: 'abc' }
    const getSpy = vi.spyOn(jobsApi, 'get')
    await mountPage()
    expect(getSpy).not.toHaveBeenCalled()
  })

  it('swallows a 404 silently when the deep-linked record was deleted', async () => {
    routeQuery.value = { detail: '999' }
    vi.spyOn(jobsApi, 'get').mockRejectedValue({ response: { status: 404 } })
    const { wrapper } = await mountPage()
    await flushPromises()
    const dialog = wrapper.findComponent({ name: 'JobDetailDialog' })
    expect(dialog.props('modelValue')).toBe(false)
  })

  it('clears ?detail from the URL when the dialog is closed', async () => {
    routeQuery.value = { detail: '7', sort: 'company', order: 'asc' }
    vi.spyOn(jobsApi, 'get').mockResolvedValue({
      id: 7,
      job_year: 2025,
      job_month: 5,
      company: 'Linked',
      kind: 'internship',
      display_name: null,
      timeline_md: null,
      experience_md: 'x',
      created_at: '2025-05-01T00:00:00+00:00',
    })
    const { wrapper } = await mountPage()
    await flushPromises()
    replaceMock.mockClear()

    const dialog = wrapper.findComponent({ name: 'JobDetailDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await flushPromises()

    // detail key dropped, other filter keys retained.
    expect(replaceMock).toHaveBeenCalled()
    const lastCall = replaceMock.mock.calls.at(-1)[0]
    expect(lastCall.query).not.toHaveProperty('detail')
    expect(lastCall.query).toMatchObject({ sort: 'company', order: 'asc' })
  })

  it('preserves ?detail across filter edits', async () => {
    routeQuery.value = { detail: '7' }
    vi.spyOn(jobsApi, 'get').mockResolvedValue({
      id: 7,
      job_year: 2025,
      job_month: 5,
      company: 'Linked',
      kind: 'internship',
      display_name: null,
      timeline_md: null,
      experience_md: 'x',
      created_at: '2025-05-01T00:00:00+00:00',
    })
    const { wrapper } = await mountPage()
    await flushPromises()
    replaceMock.mockClear()

    await wrapper.find('[data-test="sort-company"]').trigger('click')
    await flushPromises()

    // Filter sync re-writes the URL but must keep the deep-link key.
    expect(replaceMock).toHaveBeenLastCalledWith({
      query: expect.objectContaining({
        sort: 'company',
        order: 'asc',
        detail: '7',
      }),
    })
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

describe('Jobs.vue — post affordances', () => {
  it('hides the add button for viewers but shows it for members and admins', async () => {
    const viewer = await mountPage(sample, sample.length, 'viewer')
    expect(viewer.wrapper.find('[data-test="add-job-button"]').exists()).toBe(
      false,
    )
    const member = await mountPage(sample, sample.length, 'member')
    expect(member.wrapper.find('[data-test="add-job-button"]').exists()).toBe(
      true,
    )
    const admin = await mountPage(sample, sample.length, 'admin')
    expect(admin.wrapper.find('[data-test="add-job-button"]').exists()).toBe(
      true,
    )
  })

  it('hides the delete button when the row is not editable', async () => {
    const { wrapper } = await mountPage(sample, sample.length, 'viewer')
    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="detail-delete-button"]').exists()).toBe(
      false,
    )
  })

  it('shows the delete button when the row is editable (can_edit)', async () => {
    const { wrapper } = await mountPage(ownedSample, ownedSample.length, 'admin')
    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="detail-delete-button"]').exists()).toBe(
      true,
    )
  })

  it('admin delete goes through the password dialog and refetches on success', async () => {
    const remove = vi.spyOn(jobsApi, 'remove').mockResolvedValue()
    const { wrapper, listSpy } = await mountPage(
      ownedSample,
      ownedSample.length,
      'admin',
    )

    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="detail-delete-button"]').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })
    expect(dialog.exists()).toBe(true)
    listSpy.mockClear()
    dialog.vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(ownedSample[0].id, 'admin-pw')
    expect(listSpy).toHaveBeenCalledTimes(1)
  })

  it('member owner delete confirms then removes without a password', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const remove = vi.spyOn(jobsApi, 'remove').mockResolvedValue()
    const { wrapper, listSpy } = await mountPage(
      ownedSample,
      ownedSample.length,
      'member',
    )

    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    listSpy.mockClear()
    await wrapper.find('[data-test="detail-delete-button"]').trigger('click')
    await flushPromises()

    // Bodyless delete (no password) and no password dialog is mounted.
    expect(remove).toHaveBeenCalledWith(ownedSample[0].id)
    expect(
      wrapper.findComponent({ name: 'DeleteWithPasswordDialog' }).props(
        'modelValue',
      ),
    ).toBe(false)
    expect(listSpy).toHaveBeenCalledTimes(1)
  })

  it('surfaces a 422 password-error message instead of refetching', async () => {
    const remove = vi.spyOn(jobsApi, 'remove').mockRejectedValue({
      response: { status: 422 },
    })
    const { wrapper, listSpy } = await mountPage(
      ownedSample,
      ownedSample.length,
      'admin',
    )

    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="detail-delete-button"]').trigger('click')
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

describe('Jobs.vue — cache invalidation on mutation', () => {
  it('invalidates the jobs cache after a successful delete', async () => {
    vi.spyOn(jobsApi, 'remove').mockResolvedValue()
    const { wrapper } = await mountPage(ownedSample, ownedSample.length, 'admin')
    const invalidate = vi.spyOn(useJobsStore(), 'invalidate')

    await wrapper.find('[data-test="record-card"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="detail-delete-button"]').trigger('click')
    await flushPromises()
    wrapper
      .findComponent({ name: 'DeleteWithPasswordDialog' })
      .vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    expect(invalidate).toHaveBeenCalled()
  })

  it('invalidates the jobs cache when the form reports saved', async () => {
    const { wrapper } = await mountPage()
    const invalidate = vi.spyOn(useJobsStore(), 'invalidate')

    wrapper.findComponent({ name: 'JobFormDialog' }).vm.$emit('saved')
    await flushPromises()

    expect(invalidate).toHaveBeenCalled()
  })
})
