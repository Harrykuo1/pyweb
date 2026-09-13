import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventPhotosManager from './EventPhotosManager.vue'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import { eventsApi } from '../../api/events'
import { settingsApi } from '../../api/settings'

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

const MOCK_PHOTO_MB = 15

beforeEach(() => {
  setActivePinia(createPinia())
  // The manager now also lists videos and reads the admin-tunable limits;
  // without these the component reaches for a real server.
  vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([])
  vi.spyOn(settingsApi, 'getConfig').mockResolvedValue({
    fields: [
      { key: 'max_photos_per_event', value: 30, group: 'event' },
      { key: 'max_photo_mb', value: MOCK_PHOTO_MB, group: 'event' },
      { key: 'max_videos_per_event', value: 5, group: 'event' },
      { key: 'max_video_mb', value: 240, group: 'event' },
    ],
  })
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
    // Derived from the mocked config rather than a literal: the cap is
    // admin-tunable now, so a hard-coded number here would just re-create
    // the stale-copy problem the component was changed to avoid.
    Object.defineProperty(file, 'size', {
      value: MOCK_PHOTO_MB * 1024 * 1024 + 1,
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

describe('EventPhotosManager — videos in the grid', () => {
  const VIDEOS = [
    {
      id: 7,
      kind: 'upload',
      status: 'ready',
      caption: null,
      has_poster: true,
      youtube_id: null,
      duration_seconds: 12,
    },
    {
      id: 8,
      kind: 'upload',
      status: 'processing',
      caption: null,
      has_poster: false,
      youtube_id: null,
      duration_seconds: null,
    },
    {
      id: 9,
      kind: 'youtube',
      status: 'ready',
      caption: null,
      has_poster: false,
      youtube_id: 'dQw4w9WgXcQ',
      duration_seconds: null,
    },
  ]

  it('renders videos beside photos rather than only photos', async () => {
    // The grid iterated photos alone, so an uploaded video could not be
    // captioned or deleted from the editor at all — it was simply invisible.
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue(VIDEOS)
    const wrapper = await mountManager()

    const cells = wrapper.findAll('[data-test="photo-cell"]')
    expect(cells.length).toBe(PHOTOS.length + VIDEOS.length)
    const types = cells.map((c) => c.attributes('data-media-type'))
    expect(types.filter((t) => t === 'video')).toHaveLength(3)

    expect(wrapper.find('[data-test="manager-processing"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-test="manager-video-flag"]')).toHaveLength(2)
  })

  it('flags the first item with a thumbnail as the cover, not the first item', async () => {
    // A clip still transcoding has no poster, so the card falls through to
    // the next item — the star has to say the same thing the card shows.
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([
      { ...VIDEOS[1], sort_order: 0 },
    ])
    const wrapper = await mountManager(
      PHOTOS.map((p, i) => ({ ...p, sort_order: i + 1 })),
    )

    const cells = wrapper.findAll('[data-test="photo-cell"]')
    expect(cells[0].attributes('data-media-type')).toBe('video')
    expect(cells[0].find('.cover-flag').exists()).toBe(false)
    expect(cells[1].find('.cover-flag').exists()).toBe(true)
  })

  it('sends a caption edit to the video endpoint, not the photo one', async () => {
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([VIDEOS[0]])
    const updateVideo = vi
      .spyOn(eventsApi, 'updateVideoCaption')
      .mockResolvedValue({ ...VIDEOS[0], caption: '開場' })
    const updatePhoto = vi.spyOn(eventsApi, 'updatePhotoCaption')
    const wrapper = await mountManager()

    // PHOTOS come first in the grid, so the video's caption box is the one
    // after them. data-test lands on the inner <input> (ElInput forwards attrs).
    const boxes = wrapper.element.querySelectorAll(
      '[data-test="caption-input"]',
    )
    const host = boxes[PHOTOS.length]
    const native = host.tagName === 'INPUT' ? host : host.querySelector('input')
    native.dispatchEvent(new Event('focus', { bubbles: true }))
    setNativeValue(native, '開場')
    native.dispatchEvent(new Event('blur', { bubbles: true }))
    await flushPromises()

    expect(updateVideo).toHaveBeenCalledWith(1, 7, '開場')
    expect(updatePhoto).not.toHaveBeenCalled()
  })

  it('sends a delete to the video endpoint, not the photo one', async () => {
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([VIDEOS[0]])
    const removeVideo = vi.spyOn(eventsApi, 'removeVideo').mockResolvedValue()
    const removePhoto = vi.spyOn(eventsApi, 'removePhoto')
    const wrapper = await mountManager()

    const videoCell = wrapper
      .findAll('[data-test="photo-cell"]')
      .find((c) => c.attributes('data-media-type') === 'video')
    await videoCell.find('[data-test="delete-photo-button"]').trigger('click')
    await flushPromises()
    await wrapper
      .findComponent(DeleteWithPasswordDialog)
      .vm.$emit('confirm', undefined)
    await flushPromises()

    expect(removeVideo).toHaveBeenCalledWith(1, 7, undefined)
    expect(removePhoto).not.toHaveBeenCalled()
  })
})
