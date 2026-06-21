import { onMounted, onUnmounted, ref } from 'vue'

import { eventsApi } from '../api/events'

const PEEK_INTERVAL_MS = 1800

// Timeline card hover behaviour for the Events page, in one place:
//   1. Rail fill — `tlProgress` (0..1) lights the warm spine from the top
//      down to the hovered card's node (scroll-independent geometry).
//   2. Photo peek — while a card with 2+ photos is hovered, walk its album
//      on an interval, cross-dissolving between two stacked layers (a/b).
// Both are driven by onCardEnter/onCardLeave so the view just binds those.
// Per-view URL cache survives re-sorts; interval timers are cleared on
// leave and on unmount.
export function useEventPeek() {
  const timelineRef = ref(null)
  const tlProgress = ref(0)

  let reducedMotion = false
  onMounted(() => {
    reducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  // Fraction of the rail to fill so it reaches the hovered card's node. The
  // node sits at the card's vertical centre; offsets are relative to the
  // timeline, so they're scroll-independent.
  function fillToCard(cardEl) {
    const tl = timelineRef.value
    if (!tl || !cardEl) return
    const tlRect = tl.getBoundingClientRect()
    if (tlRect.height <= 0) return
    const cardRect = cardEl.getBoundingClientRect()
    const nodeY = cardRect.top + cardRect.height / 2 - tlRect.top
    tlProgress.value = Math.max(0, Math.min(1, nodeY / tlRect.height))
  }

  const peekUrls = new Map() // ev.id -> [url, ...] | null (none/failed)
  const peekTimers = new Map() // ev.id -> intervalId
  // ev.id -> { a: url|null, b: url|null, active: 'a'|'b' }
  const peekLayers = ref({})

  function setLayer(id, patch) {
    const cur = peekLayers.value[id] || { a: null, b: null, active: 'a' }
    peekLayers.value = { ...peekLayers.value, [id]: { ...cur, ...patch } }
  }

  async function loadPeekUrls(ev) {
    if (peekUrls.has(ev.id)) return peekUrls.get(ev.id)
    peekUrls.set(ev.id, null) // in-flight sentinel
    try {
      const photos = await eventsApi.listPhotos(ev.id)
      // Cover first, then the rest, so the slideshow walks the whole album.
      const ordered = [
        ...photos.filter((p) => p.id === ev.cover_photo_id),
        ...photos.filter((p) => p.id !== ev.cover_photo_id),
      ]
      const urls = ordered.map((p) => eventsApi.photoUrl(ev.id, p.id))
      peekUrls.set(ev.id, urls.length > 1 ? urls : null)
      return peekUrls.get(ev.id)
    } catch {
      peekUrls.set(ev.id, null)
      return null
    }
  }

  async function startPeek(ev) {
    if (reducedMotion) return
    if (!ev?.cover_photo_id || ev.photo_count < 2) return
    if (peekTimers.has(ev.id)) return // already running
    const urls = await loadPeekUrls(ev)
    if (!urls || urls.length < 2) return
    // With 2+ non-cover photos, loop ONLY the real photos so the last
    // cross-dissolves straight back to the first (no dwell on the cover).
    // With a single extra photo, alternate it with the cover so there are
    // still two frames to animate between.
    const rest = urls.slice(1)
    const slides = rest.length >= 2 ? rest : urls
    // startI is chosen so the very first tick lands on the first real photo.
    let i = slides === urls ? 0 : -1
    // Fresh start: cover only (no peek layers yet) until the first tick.
    peekLayers.value = {
      ...peekLayers.value,
      [ev.id]: { a: null, b: null, active: 'a' },
    }
    const id = setInterval(() => {
      i = (i + 1) % slides.length
      const cur = peekLayers.value[ev.id] || { active: 'a' }
      const nextActive = cur.active === 'a' ? 'b' : 'a'
      // Paint the next slide onto the inactive layer, then flip — the two
      // layers cross-dissolve via the opacity transition in CSS.
      setLayer(ev.id, { [nextActive]: slides[i], active: nextActive })
    }, PEEK_INTERVAL_MS)
    peekTimers.set(ev.id, id)
  }

  function stopPeek(ev) {
    const id = peekTimers.get(ev.id)
    if (id !== undefined) {
      clearInterval(id)
      peekTimers.delete(ev.id)
    }
    // Keep the layers; CSS gates visibility on :hover, so the active slide
    // simply fades back to the cover when the pointer leaves.
  }

  function onCardEnter(event, ev) {
    fillToCard(event.currentTarget)
    startPeek(ev)
  }

  function onCardLeave(ev) {
    tlProgress.value = 0
    stopPeek(ev)
  }

  onUnmounted(() => {
    for (const id of peekTimers.values()) clearInterval(id)
    peekTimers.clear()
  })

  return { timelineRef, tlProgress, peekLayers, onCardEnter, onCardLeave }
}
