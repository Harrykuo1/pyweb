import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'

import { useMediaReorder } from './useMediaReorder'
import { eventsApi } from '../api/events'

// Sortable is driven by real pointer events, which jsdom does not produce.
// Capturing its options lets the tests invoke onEnd directly — what is worth
// testing here is what happens after a drop, not the library's dragging.
let lastOptions = null
vi.mock('sortablejs', () => ({
  default: {
    create: (_el, options) => {
      lastOptions = options
      return { destroy: vi.fn(), sort: vi.fn(), toArray: () => [] }
    },
  },
}))

function host(initial) {
  const items = ref(initial)
  let api
  const Host = defineComponent({
    setup() {
      api = useMediaReorder({
        getEventId: () => 1,
        getItems: () => items.value,
        onReordered: (next) => {
          items.value = next
        },
      })
      return () => h('div', { ref: api.container })
    },
  })
  const wrapper = mount(Host)
  return { wrapper, items, api: () => api }
}

const MEDIA = [
  { type: 'photo', key: 'photo-1', row: { id: 1 } },
  { type: 'photo', key: 'photo-2', row: { id: 2 } },
  { type: 'video', key: 'video-9', row: { id: 9 } },
]

afterEach(() => {
  vi.restoreAllMocks()
  lastOptions = null
})

describe('useMediaReorder', () => {
  it('sends the complete order, not the move that produced it', async () => {
    const reorder = vi.spyOn(eventsApi, 'reorderMedia').mockResolvedValue()
    const { items } = host([...MEDIA])
    await nextTick()

    // Drag the video from the end to the middle.
    await lastOptions.onEnd({ oldIndex: 2, newIndex: 1 })
    await Promise.resolve()

    expect(reorder).toHaveBeenCalledWith(1, [
      { type: 'photo', id: 1 },
      { type: 'video', id: 9 },
      { type: 'photo', id: 2 },
    ])
    expect(items.value.map((m) => m.key)).toEqual([
      'photo-1',
      'video-9',
      'photo-2',
    ])
  })

  it('puts the grid back when the save fails', async () => {
    vi.spyOn(eventsApi, 'reorderMedia').mockRejectedValue(new Error('nope'))
    const { items } = host([...MEDIA])
    await nextTick()

    await lastOptions.onEnd({ oldIndex: 0, newIndex: 2 })
    await new Promise((r) => setTimeout(r, 0))

    // Leaving the moved order on screen would tell the user something was
    // saved that was not.
    expect(items.value.map((m) => m.key)).toEqual([
      'photo-1',
      'photo-2',
      'video-9',
    ])
  })

  it('ignores a drag that ends where it started', async () => {
    const reorder = vi.spyOn(eventsApi, 'reorderMedia').mockResolvedValue()
    host([...MEDIA])
    await nextTick()

    await lastOptions.onEnd({ oldIndex: 1, newIndex: 1 })
    expect(reorder).not.toHaveBeenCalled()
  })

  it('drags from the thumbnail only', async () => {
    // The cell also holds a caption box and a delete button; a whole-cell
    // handle would make both unusable on touch.
    host([...MEDIA])
    await nextTick()
    expect(lastOptions.handle).toBe('[data-drag-handle]')
    expect(lastOptions.delayOnTouchOnly).toBe(true)
  })
})
