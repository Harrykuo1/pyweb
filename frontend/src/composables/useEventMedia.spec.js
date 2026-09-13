import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

import { useEventMedia } from './useEventMedia'
import { eventsApi } from '../api/events'

const PHOTOS = [{ id: 1, caption: '合照' }]

function readyVideo(overrides = {}) {
  return {
    id: 7,
    kind: 'upload',
    status: 'ready',
    caption: null,
    duration_seconds: 65,
    has_poster: true,
    youtube_id: null,
    error_detail: null,
    ...overrides,
  }
}

/** Mount the composable inside a host so onUnmounted actually fires. */
function host(getId = () => 1) {
  let api
  const Host = defineComponent({
    setup() {
      api = useEventMedia(getId)
      return () => null
    },
  })
  const wrapper = mount(Host)
  return { wrapper, api: () => api }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(eventsApi, 'listPhotos').mockResolvedValue(PHOTOS)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('useEventMedia', () => {
  it('merges photos and videos into one grid list', async () => {
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([readyVideo()])
    const { api } = host()
    await api().load()

    const items = api().items.value
    expect(items.map((i) => i.type)).toEqual(['photo', 'video'])
    // Keys are namespaced because the two tables number their rows
    // independently — photo 1 and video 1 both exist.
    expect(items.map((i) => i.key)).toEqual(['photo-1', 'video-7'])
    expect(items[1].fileUrl).toContain('/videos/7/file')
    expect(items[1].thumbUrl).toContain('/videos/7/poster')
  })

  it('gives a processing video no poster and no file to play', async () => {
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([
      readyVideo({ status: 'processing', has_poster: false }),
    ])
    const { api } = host()
    await api().load()

    const video = api().items.value[1]
    expect(video.thumbUrl).toBeNull()
    expect(video.fileUrl).toBeNull()
  })

  it('does not poll when nothing is transcoding', async () => {
    const listVideos = vi
      .spyOn(eventsApi, 'listVideos')
      .mockResolvedValue([readyVideo()])
    const { api } = host()
    await api().load()
    expect(listVideos).toHaveBeenCalledTimes(1)

    // An idle event page should issue no background requests at all.
    await vi.advanceTimersByTimeAsync(15000)
    expect(listVideos).toHaveBeenCalledTimes(1)
  })

  it('polls while a video is transcoding and stops once it is ready', async () => {
    const listVideos = vi
      .spyOn(eventsApi, 'listVideos')
      .mockResolvedValue([
        readyVideo({ status: 'processing', has_poster: false }),
      ])
    const { api } = host()
    await api().load()

    await vi.advanceTimersByTimeAsync(3000)
    expect(listVideos).toHaveBeenCalledTimes(2)

    listVideos.mockResolvedValue([readyVideo()])
    await vi.advanceTimersByTimeAsync(3000)
    expect(listVideos).toHaveBeenCalledTimes(3)
    expect(api().hasProcessing.value).toBe(false)

    // The tick that saw it finish must also be the last one.
    await vi.advanceTimersByTimeAsync(30000)
    expect(listVideos).toHaveBeenCalledTimes(3)
  })

  it('stops polling when the dialog closes', async () => {
    const listVideos = vi
      .spyOn(eventsApi, 'listVideos')
      .mockResolvedValue([
        readyVideo({ status: 'processing', has_poster: false }),
      ])
    const { api } = host()
    await api().load()

    api().reset()
    await vi.advanceTimersByTimeAsync(30000)
    // Otherwise closing the dialog would leave a timer hitting an event
    // nobody is looking at, forever.
    expect(listVideos).toHaveBeenCalledTimes(1)
  })

  it('stops polling when the component unmounts', async () => {
    const listVideos = vi
      .spyOn(eventsApi, 'listVideos')
      .mockResolvedValue([
        readyVideo({ status: 'processing', has_poster: false }),
      ])
    const { wrapper, api } = host()
    await api().load()

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(30000)
    expect(listVideos).toHaveBeenCalledTimes(1)
  })

  it('resolves the event id per call, not once at setup', async () => {
    // The detail dialog is reused across events; an id captured at setup
    // would keep fetching the first one the viewer opened.
    let id = 1
    const listVideos = vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([])
    const { api } = host(() => id)

    await api().load()
    expect(listVideos).toHaveBeenLastCalledWith(1)

    id = 2
    await api().load()
    expect(listVideos).toHaveBeenLastCalledWith(2)
  })
})

describe('useEventMedia — YouTube references', () => {
  it('builds the embed URL from the id rather than any stored URL', async () => {
    vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([
      readyVideo({
        kind: 'youtube',
        youtube_id: 'dQw4w9WgXcQ',
        has_poster: false,
      }),
    ])
    const { api } = host()
    await api().load()

    const video = api().items.value[1]
    // nocookie, and assembled here — nothing a user typed reaches the src.
    expect(video.embedUrl).toBe(
      'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
    )
    // A reference owns no file on our side.
    expect(video.fileUrl).toBeNull()
    // YouTube supplies its own thumbnail, so none is stored.
    expect(video.thumbUrl).toContain('img.youtube.com/vi/dQw4w9WgXcQ')
  })

  it('never polls for a YouTube reference', async () => {
    // There is nothing to transcode, so the row is ready on arrival.
    const listVideos = vi.spyOn(eventsApi, 'listVideos').mockResolvedValue([
      readyVideo({
        kind: 'youtube',
        youtube_id: 'dQw4w9WgXcQ',
        has_poster: false,
      }),
    ])
    const { api } = host()
    await api().load()

    await vi.advanceTimersByTimeAsync(30000)
    expect(listVideos).toHaveBeenCalledTimes(1)
  })
})
