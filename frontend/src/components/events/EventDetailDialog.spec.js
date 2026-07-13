import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventDetailDialog from './EventDetailDialog.vue'
import { useAuthStore } from '../../stores/auth'
import { eventsApi } from '../../api/events'

vi.mock('md-editor-v3', () => ({
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue'],
    template: '<div class="md-preview-stub">{{ modelValue }}</div>',
  },
}))
vi.mock('md-editor-v3/lib/preview.css', () => ({}))

const sample = {
  id: 1,
  title: '春酒聚餐',
  event_date: '2026-03-15',
  location: '台北',
  description_md: '# 很開心的一天',
  created_at: '2026-03-16T00:00:00+00:00',
  tags: ['春酒', '聚餐'],
  photo_count: 2,
  cover_photo_id: 10,
}

const PHOTOS = [
  {
    id: 10,
    event_id: 1,
    filename: '10.jpg',
    mime_type: 'image/jpeg',
    size_bytes: 1,
    caption: '合照',
    uploaded_at: 'x',
  },
  {
    id: 11,
    event_id: 1,
    filename: '11.jpg',
    mime_type: 'image/jpeg',
    size_bytes: 1,
    caption: null,
    uploaded_at: 'x',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(eventsApi, 'listPhotos').mockResolvedValue(PHOTOS)
  // The embedded comment section fetches on open; stub it so these tests
  // don't hit the real client.
  vi.spyOn(eventsApi, 'listComments').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}, role = 'admin') {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
  const wrapper = mount(EventDetailDialog, {
    props: { modelValue: true, event: sample, ...props },
  })
  await flushPromises()
  return wrapper
}

describe('EventDetailDialog — mounts closed (regression)', () => {
  it('mounts with modelValue=false without a TDZ error in the immediate watcher', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() =>
      mount(EventDetailDialog, { props: { modelValue: false, event: sample } }),
    ).not.toThrow()
    const tdz = errorSpy.mock.calls
      .flat()
      .some((a) => String(a?.message ?? a).includes('before initialization'))
    expect(tdz).toBe(false)
  })
})

describe('EventDetailDialog — header', () => {
  it('shows title, tags and location', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.find('[data-test="detail-title"]').text()).toContain(
      '春酒聚餐',
    )
    expect(wrapper.find('[data-test="detail-tags"]').text()).toContain('#春酒')
    expect(wrapper.find('[data-test="detail-location"]').text()).toContain(
      '台北',
    )
  })
})

describe('EventDetailDialog — gallery', () => {
  it('fetches and renders the photo gallery', async () => {
    const wrapper = await mountDialog()
    expect(eventsApi.listPhotos).toHaveBeenCalledWith(1)
    expect(wrapper.findAll('[data-test="gallery-thumb"]')).toHaveLength(2)
  })

  it('renders the markdown description', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.find('[data-test="detail-description"]').text()).toContain(
      '很開心的一天',
    )
  })

  it('opens the lightbox when a thumbnail is clicked', async () => {
    const wrapper = await mountDialog()
    expect(document.querySelector('[data-test="lightbox"]')).toBeNull()
    await wrapper.findAll('[data-test="gallery-thumb"]')[0].trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-test="lightbox"]')).not.toBeNull()
  })
})

describe('EventDetailDialog — edit', () => {
  it('emits edit when the event is editable (can_edit)', async () => {
    const wrapper = await mountDialog({ event: { ...sample, can_edit: true } })
    expect(wrapper.find('[data-test="detail-edit-button"]').exists()).toBe(true)
    await wrapper.find('[data-test="detail-edit-button"]').trigger('click')
    expect(wrapper.emitted('edit')).toBeTruthy()
  })

  it('hides the edit button when can_edit is false', async () => {
    const wrapper = await mountDialog({ event: { ...sample, can_edit: false } })
    expect(wrapper.find('[data-test="detail-edit-button"]').exists()).toBe(
      false,
    )
  })
})

describe('EventDetailDialog — status + author', () => {
  it('shows the author, a status pill and the rejection reason', async () => {
    const wrapper = await mountDialog({
      event: {
        ...sample,
        author_display_name: '王小明',
        status: 'rejected',
        review_reason: '照片不足',
      },
    })
    expect(wrapper.find('[data-test="detail-author"]').text()).toContain(
      '王小明',
    )
    expect(
      wrapper.find('[data-test="detail-status-rejected"]').text(),
    ).toContain('已退回')
    expect(wrapper.find('[data-test="detail-reject-reason"]').text()).toContain(
      '照片不足',
    )
  })
})
