import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { useEventPeek } from './useEventPeek'
import { eventsApi } from '../api/events'

// Host component so the composable's onMounted/onUnmounted run in a real
// instance. Returns the peek API on the vm for the test to drive.
function mountPeek() {
  const Host = {
    setup() {
      return useEventPeek()
    },
    template: '<div />',
  }
  return mount(Host)
}

const fakeEnter = { currentTarget: {} }

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('useEventPeek', () => {
  it('does not start a slideshow for events with fewer than 2 photos', async () => {
    const list = vi.spyOn(eventsApi, 'listPhotos')
    const vm = mountPeek().vm
    vm.onCardEnter(fakeEnter, { id: 1, cover_photo_id: 10, photo_count: 1 })
    await flushPromises()
    expect(list).not.toHaveBeenCalled()
    expect(vm.peekLayers[1]).toBeUndefined()
  })

  it('loads photos and cross-dissolves slides on an interval while hovered', async () => {
    vi.spyOn(eventsApi, 'listPhotos').mockResolvedValue([
      { id: 10 },
      { id: 11 },
      { id: 12 },
    ])
    vi.spyOn(eventsApi, 'photoUrl').mockImplementation(
      (eid, pid) => `/api/events/${eid}/photos/${pid}`,
    )
    vi.useFakeTimers()
    const vm = mountPeek().vm

    vm.onCardEnter(fakeEnter, { id: 1, cover_photo_id: 10, photo_count: 3 })
    await flushPromises() // resolve listPhotos, arm the interval
    // Layer record is initialized to the cover-only state.
    expect(vm.peekLayers[1]).toEqual({ a: null, b: null, active: 'a' })

    await vi.advanceTimersByTimeAsync(1800) // first tick paints a slide
    expect(vm.peekLayers[1].active).toBe('b')
    expect(vm.peekLayers[1].b).toBe('/api/events/1/photos/11')
  })

  it('stops the interval on card leave', async () => {
    vi.spyOn(eventsApi, 'listPhotos').mockResolvedValue([
      { id: 10 },
      { id: 11 },
      { id: 12 },
    ])
    vi.spyOn(eventsApi, 'photoUrl').mockImplementation((e, p) => `${e}/${p}`)
    vi.useFakeTimers()
    const vm = mountPeek().vm

    const ev = { id: 1, cover_photo_id: 10, photo_count: 3 }
    vm.onCardEnter(fakeEnter, ev)
    await flushPromises()
    vm.onCardLeave(ev)

    const before = JSON.stringify(vm.peekLayers[1])
    await vi.advanceTimersByTimeAsync(1800 * 3)
    expect(JSON.stringify(vm.peekLayers[1])).toBe(before)
    expect(vm.tlProgress).toBe(0)
  })
})
