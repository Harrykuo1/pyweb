import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Events from './Events.vue'
import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import { eventsApi } from '../api/events'
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

// Heavy dialog children pull in md-editor; stub them so the view spec
// stays focused on the timeline rendering + filters.
vi.mock('../components/events/EventFormDialog.vue', () => ({
  default: {
    name: 'EventFormDialog',
    props: ['modelValue', 'event'],
    template: '<div />',
  },
}))
vi.mock('../components/events/EventDetailDialog.vue', () => ({
  default: {
    name: 'EventDetailDialog',
    props: ['modelValue', 'event'],
    // Render the footer-extra slot so the admin-only delete button passed
    // in from Events.vue becomes testable.
    template: '<div><slot name="footer-extra" /></div>',
  },
}))

const sample = [
  {
    id: 1,
    title: '春酒聚餐',
    event_date: '2026-03-15',
    location: '台北',
    description_md: '很開心',
    tags: ['春酒', '聚餐'],
    photo_count: 3,
    cover_photo_id: 10,
  },
  {
    id: 2,
    title: '溪頭兩日遊',
    event_date: '2025-09-01',
    location: '南投',
    description_md: null,
    tags: ['出遊'],
    photo_count: 0,
    cover_photo_id: null,
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  routeQuery.value = {}
  replaceMock.mockClear()
  vi.spyOn(eventsApi, 'listTags').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function mountPage(
  items = sample,
  total = items.length,
  role = 'viewer',
) {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
  vi.spyOn(eventsApi, 'list').mockResolvedValue({ items, total })
  const wrapper = mount(Events)
  await flushPromises()
  return wrapper
}

describe('Events — timeline', () => {
  it('renders one entry per event', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('[data-test="timeline-entry"]')).toHaveLength(2)
  })

  it('groups entries by year with a marker per year', async () => {
    const wrapper = await mountPage()
    const labels = wrapper.findAll('[data-test="year-label"]')
    expect(labels.map((m) => m.text())).toEqual(['2026', '2025'])
  })

  it('shows the cover image and a photo-count badge when >1 photo', async () => {
    const wrapper = await mountPage()
    const firstEntry = wrapper.findAll('[data-test="timeline-entry"]')[0]
    expect(firstEntry.find('img').attributes('src')).toBe(
      '/api/events/1/photos/10',
    )
    expect(firstEntry.find('.photo-badge').text()).toContain('3')
  })

  it('renders the empty state when there are no events', async () => {
    const wrapper = await mountPage([], 0)
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
  })
})

describe('Events — filters', () => {
  it('toggles sort order and re-queries', async () => {
    const wrapper = await mountPage()
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: sample, total: 2 })
    await wrapper.find('[data-test="sort-toggle"]').trigger('click')
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ order: 'asc' }),
    )
  })
})

describe('Events — admin', () => {
  it('shows the add button only for admins', async () => {
    const viewer = await mountPage(sample, 2, 'viewer')
    expect(viewer.find('[data-test="add-event-button"]').exists()).toBe(false)

    const admin = await mountPage(sample, 2, 'admin')
    expect(admin.find('[data-test="add-event-button"]').exists()).toBe(true)
  })

  it('has no inline edit/delete on cards — admin edits via the detail dialog', async () => {
    const wrapper = await mountPage(sample, 2, 'admin')
    expect(wrapper.find('[data-test="edit-event-button"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-event-button"]').exists()).toBe(
      false,
    )
  })
})

describe('Events — delete', () => {
  it('confirms deletion with the typed password and reloads', async () => {
    const wrapper = await mountPage(sample, 2, 'admin')
    const remove = vi.spyOn(eventsApi, 'remove').mockResolvedValue()
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: sample, total: 2 })

    wrapper.vm.askDelete(sample[0])
    await flushPromises()
    wrapper
      .findComponent(DeleteWithPasswordDialog)
      .vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(1, 'admin-pw')
    expect(listSpy).toHaveBeenCalled() // reloaded after delete
  })

  it('maps a 422 delete error to a password message and keeps the dialog open', async () => {
    const wrapper = await mountPage(sample, 2, 'admin')
    vi.spyOn(eventsApi, 'remove').mockRejectedValue({
      response: { status: 422 },
    })

    wrapper.vm.askDelete(sample[0])
    await flushPromises()
    wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'wrong')
    await flushPromises()

    const dialog = wrapper.findComponent(DeleteWithPasswordDialog)
    expect(dialog.props('errorMessage')).toBe('密碼錯誤')
    expect(dialog.props('modelValue')).toBe(true)
  })
})

describe('Events — detail delete permission', () => {
  it('shows the detail delete button only for admins', async () => {
    const admin = await mountPage(sample, 2, 'admin')
    admin.vm.detailEvent = sample[0]
    await flushPromises()
    expect(admin.find('[data-test="detail-delete-button"]').exists()).toBe(true)

    const viewer = await mountPage(sample, 2, 'viewer')
    viewer.vm.detailEvent = sample[0]
    await flushPromises()
    expect(viewer.find('[data-test="detail-delete-button"]').exists()).toBe(
      false,
    )
  })
})

describe('Events — filter params', () => {
  it('passes the year filter to the API', async () => {
    const wrapper = await mountPage()
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: [], total: 0 })
    wrapper.vm.year = 2026
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ year: 2026 }),
    )
  })

  it('passes selected tags to the API', async () => {
    const wrapper = await mountPage()
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: [], total: 0 })
    wrapper.vm.tag = ['出遊']
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ tag: ['出遊'] }),
    )
  })

  it('passes the debounced search query to the API', async () => {
    const wrapper = await mountPage()
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: [], total: 0 })
    vi.useFakeTimers()
    wrapper.vm.q = '桌遊'
    await vi.advanceTimersByTimeAsync(300)
    expect(listSpy).toHaveBeenCalledWith(expect.objectContaining({ q: '桌遊' }))
    vi.useRealTimers()
  })
})
