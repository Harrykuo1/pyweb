import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventPhotosManager from './EventPhotosManager.vue'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import { eventsApi } from '../../api/events'

function setNativeValue(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

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

import { ElMessage } from 'element-plus'

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
    await wrapper
      .findAll('[data-test="delete-photo-button"]')[0]
      .trigger('click')
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
    const native =
      input.tagName === 'INPUT' ? input : input.querySelector('input')
    native.dispatchEvent(new Event('focus', { bubbles: true }))
    setNativeValue(native, '新說明')
    native.dispatchEvent(new Event('blur', { bubbles: true }))
    await flushPromises()
    expect(update).toHaveBeenCalledWith(1, 10, '新說明')
  })

  it('uploads a chosen file and reloads the list', async () => {
    const wrapper = await mountManager()
    const upload = vi.spyOn(eventsApi, 'uploadPhoto').mockResolvedValue({})

    const file = new File([new Uint8Array([1, 2, 3])], 'new.png', {
      type: 'image/png',
    })
    const input = wrapper.find('[data-test="photo-file-input"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })
    await input.trigger('change')
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(1, file)
    // initial load + reload after a successful upload
    expect(eventsApi.listPhotos).toHaveBeenCalledTimes(2)
  })

  it('skips an oversized file with a warning and no upload', async () => {
    const wrapper = await mountManager()
    const upload = vi.spyOn(eventsApi, 'uploadPhoto').mockResolvedValue({})

    const file = new File([new Uint8Array([1])], 'huge.png', {
      type: 'image/png',
    })
    Object.defineProperty(file, 'size', {
      value: 8 * 1024 * 1024 + 1,
      configurable: true,
    })
    const input = wrapper.find('[data-test="photo-file-input"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })
    await input.trigger('change')
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('maps a 415 upload error to a format message', async () => {
    const wrapper = await mountManager()
    vi.spyOn(eventsApi, 'uploadPhoto').mockRejectedValue({
      response: { status: 415 },
    })

    const file = new File([new Uint8Array([1])], 'weird.png', {
      type: 'image/png',
    })
    const input = wrapper.find('[data-test="photo-file-input"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })
    await input.trigger('change')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('「weird.png」格式不支援')
  })

  it('confirms deletion with the typed password and reloads', async () => {
    const wrapper = await mountManager()
    const remove = vi.spyOn(eventsApi, 'removePhoto').mockResolvedValue()

    await wrapper
      .findAll('[data-test="delete-photo-button"]')[0]
      .trigger('click')
    await flushPromises()
    wrapper
      .findComponent(DeleteWithPasswordDialog)
      .vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    // PHOTOS[0].id === 10, eventId prop === 1
    expect(remove).toHaveBeenCalledWith(1, 10, 'admin-pw')
    expect(eventsApi.listPhotos).toHaveBeenCalledTimes(2)
  })

  it('surfaces a 422 delete as a password error and keeps the dialog open', async () => {
    const wrapper = await mountManager()
    vi.spyOn(eventsApi, 'removePhoto').mockRejectedValue({
      response: { status: 422 },
    })

    await wrapper
      .findAll('[data-test="delete-photo-button"]')[0]
      .trigger('click')
    await flushPromises()
    wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'wrong')
    await flushPromises()

    const dialog = wrapper.findComponent(DeleteWithPasswordDialog)
    expect(dialog.props('errorMessage')).toBe('密碼錯誤')
    expect(dialog.props('modelValue')).toBe(true)
  })

  it('does not save a caption that has not changed on blur', async () => {
    const update = vi.spyOn(eventsApi, 'updatePhotoCaption')
    // Fresh photo object so prior tests can't leak a mutated caption.
    const wrapper = await mountManager([
      {
        id: 10,
        event_id: 1,
        filename: '10.jpg',
        mime_type: 'image/jpeg',
        size_bytes: 1,
        caption: '合照',
        uploaded_at: 'x',
      },
    ])
    const host = wrapper.element.querySelectorAll(
      '[data-test="caption-input"]',
    )[0]
    const native = host.tagName === 'INPUT' ? host : host.querySelector('input')
    native.dispatchEvent(new Event('focus', { bubbles: true }))
    native.dispatchEvent(new Event('blur', { bubbles: true }))
    await flushPromises()

    expect(update).not.toHaveBeenCalled()
  })
})
