import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventPhotosManager from './EventPhotosManager.vue'
import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'
import { eventsApi } from '../api/events'

function setNativeValue(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

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

const PHOTOS = [
  { id: 10, event_id: 1, filename: '10.jpg', mime_type: 'image/jpeg', size_bytes: 1, caption: '合照', uploaded_at: 'x' },
  { id: 11, event_id: 1, filename: '11.jpg', mime_type: 'image/jpeg', size_bytes: 1, caption: null, uploaded_at: 'x' },
]

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountManager(photos = PHOTOS) {
  vi.spyOn(eventsApi, 'listPhotos').mockResolvedValue(photos)
  const wrapper = mount(EventPhotosManager, { props: { eventId: 1 } })
  await flushPromises()
  return wrapper
}

describe('EventPhotosManager', () => {
  it('loads and renders the photo cells', async () => {
    const wrapper = await mountManager()
    expect(eventsApi.listPhotos).toHaveBeenCalledWith(1)
    expect(wrapper.findAll('[data-test="photo-cell"]')).toHaveLength(2)
  })

  it('flags the first photo as the cover', async () => {
    const wrapper = await mountManager()
    const cells = wrapper.findAll('[data-test="photo-cell"]')
    expect(cells[0].find('.cover-flag').exists()).toBe(true)
    expect(cells[1].find('.cover-flag').exists()).toBe(false)
  })

  it('renders the empty state when there are no photos', async () => {
    const wrapper = await mountManager([])
    expect(wrapper.find('[data-test="photos-empty"]').exists()).toBe(true)
  })

  it('opens the delete-confirm dialog when a delete button is clicked', async () => {
    const wrapper = await mountManager()
    await wrapper.findAll('[data-test="delete-photo-button"]')[0].trigger('click')
    await flushPromises()
    expect(
      wrapper.findComponent(DeleteWithPasswordDialog).props('modelValue'),
    ).toBe(true)
  })

  it('saves a caption on blur only when it changed', async () => {
    const update = vi
      .spyOn(eventsApi, 'updatePhotoCaption')
      .mockResolvedValue({ id: 10, caption: '新說明' })
    const wrapper = await mountManager()
    // data-test lands on the inner <input> (ElInput forwards attrs there).
    const input = wrapper.element.querySelectorAll(
      '[data-test="caption-input"]',
    )[0]
    const native = input.tagName === 'INPUT' ? input : input.querySelector('input')
    native.dispatchEvent(new Event('focus', { bubbles: true }))
    setNativeValue(native, '新說明')
    native.dispatchEvent(new Event('blur', { bubbles: true }))
    await flushPromises()
    expect(update).toHaveBeenCalledWith(1, 10, '新說明')
  })
})
