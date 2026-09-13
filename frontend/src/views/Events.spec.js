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
    media_count: 3,
    cover_media_type: 'photo',
    cover_media_id: 10,
  },
  {
    id: 2,
    title: '溪頭兩日遊',
    event_date: '2025-09-01',
    location: '南投',
    description_md: null,
    tags: ['出遊'],
    photo_count: 0,
    media_count: 0,
    cover_media_type: null,
    cover_media_id: null,
  },
]

// The same rows as the backend returns them to someone allowed to edit
// (admin, or the owning member): can_edit drives the edit/delete affordances.
const ownedSample = sample.map((e) => ({ ...e, can_edit: true }))

let pendingTeardowns = []

beforeEach(() => {
  setActivePinia(createPinia())
  routeQuery.value = {}
  replaceMock.mockClear()
  vi.spyOn(eventsApi, 'listTags').mockResolvedValue([])
})

afterEach(() => {
  for (const w of pendingTeardowns) w.unmount()
  pendingTeardowns = []
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
  pendingTeardowns.push(wrapper)
  await flushPromises()
  return wrapper
}

describe('Events — card likes', () => {
  it('likes an event straight from its card without opening it', async () => {
    const items = [{ ...sample[0], like_count: 2, liked_by_me: false }]
    const likeSpy = vi
      .spyOn(eventsApi, 'like')
      .mockResolvedValue({ like_count: 3, liked: true })
    const wrapper = await mountPage(items, 1, 'member')

    const card = wrapper.findAll('[data-test="timeline-entry"]')[0]
    expect(card.find('[data-test="like-count"]').text()).toBe('2')
    await card.find('[data-test="like-toggle"]').trigger('click')
    await flushPromises()

    expect(likeSpy).toHaveBeenCalledWith(1)
    expect(card.find('[data-test="like-count"]').text()).toBe('3')
  })
})

describe('Events — timeline', () => {
  it('renders one entry per event', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('[data-test="timeline-entry"]')).toHaveLength(2)
  })

  it('restricts to accepted events when an admin previews as a member', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    auth.previewAsMember = true
    const listSpy = vi
      .spyOn(eventsApi, 'list')
      .mockResolvedValue({ items: sample, total: sample.length })
    const wrapper = mount(Events)
    pendingTeardowns.push(wrapper)
    await flushPromises()
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'accepted' }),
    )
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

  it('shows a filter-specific empty state with a clear-filters action', async () => {
    routeQuery.value = { q: 'no-such-event' }
    const wrapper = await mountPage([], 0)
    const empty = wrapper.find('[data-test="empty-state"]')
    expect(empty.text()).toContain('找不到符合條件的活動')
    expect(empty.text()).not.toContain('還沒有任何活動')
    expect(wrapper.find('[data-test="clear-filters"]').exists()).toBe(true)
  })

  it('shows the no-data empty state (no clear-filters) when nothing is filtered', async () => {
    routeQuery.value = {}
    const wrapper = await mountPage([], 0)
    const empty = wrapper.find('[data-test="empty-state"]')
    expect(empty.text()).toContain('還沒有任何活動紀錄')
    expect(wrapper.find('[data-test="clear-filters"]').exists()).toBe(false)
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
  it('hides the add button for viewers but shows it for members and admins', async () => {
    const viewer = await mountPage(sample, 2, 'viewer')
    expect(viewer.find('[data-test="add-event-button"]').exists()).toBe(false)
    // Viewers get a read-only hint in place of the add button.
    expect(viewer.find('[data-test="viewer-readonly-hint"]').exists()).toBe(
      true,
    )

    const member = await mountPage(sample, 2, 'member')
    expect(member.find('[data-test="add-event-button"]').exists()).toBe(true)
    expect(member.find('[data-test="viewer-readonly-hint"]').exists()).toBe(
      false,
    )

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
  it('shows the detail delete button only when the event is editable', async () => {
    const admin = await mountPage(ownedSample, 2, 'admin')
    admin.vm.detailEvent = ownedSample[0]
    await flushPromises()
    expect(admin.find('[data-test="detail-delete-button"]').exists()).toBe(true)

    const viewer = await mountPage(sample, 2, 'viewer')
    viewer.vm.detailEvent = sample[0]
    await flushPromises()
    expect(viewer.find('[data-test="detail-delete-button"]').exists()).toBe(
      false,
    )
  })

  it('member owner delete confirms then removes without a password', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const remove = vi.spyOn(eventsApi, 'remove').mockResolvedValue()
    const wrapper = await mountPage(ownedSample, 2, 'member')

    await wrapper.vm.requestDeleteEvent(ownedSample[0])
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(ownedSample[0].id)
    expect(
      wrapper.findComponent(DeleteWithPasswordDialog).props('modelValue'),
    ).toBe(false)
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

describe('Events.vue — video covers', () => {
  it('uses the poster for a video cover and marks the card as playable', async () => {
    // A card that opens into a player should say so before the click rather
    // than surprising the viewer with one.
    const wrapper = await mountPage([
      {
        ...sample[0],
        media_count: 2,
        photo_count: 1,
        cover_media_type: 'video',
        cover_media_id: 7,
      },
    ])
    const entry = wrapper.findAll('[data-test="timeline-entry"]')[0]
    expect(entry.find('.tl-thumb img').attributes('src')).toBe(
      '/api/events/1/videos/7/poster',
    )
    expect(entry.find('.cover-play').exists()).toBe(true)
  })

  it('takes a YouTube cover thumbnail from YouTube, not the poster endpoint', async () => {
    // A linked video has no poster on our disk, so asking for one would put
    // a broken image on the card.
    const wrapper = await mountPage([
      {
        ...sample[0],
        cover_media_type: 'video',
        cover_media_id: 7,
        cover_youtube_id: 'dQw4w9WgXcQ',
      },
    ])
    const entry = wrapper.findAll('[data-test="timeline-entry"]')[0]
    expect(entry.find('.tl-thumb img').attributes('src')).toBe(
      'https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
    )
  })

  it('counts videos in the card badge', async () => {
    // photo_count alone would show 1 for an event holding a photo and two
    // clips, and 0 — an empty-looking card — for one holding only video.
    const wrapper = await mountPage([
      { ...sample[0], photo_count: 1, media_count: 3 },
    ])
    const entry = wrapper.findAll('[data-test="timeline-entry"]')[0]
    expect(entry.find('.photo-badge').text()).toContain('3')
  })
})
