import { computed, onUnmounted, ref } from 'vue'

import { eventsApi } from '../api/events'

// How often to re-check an event that has something transcoding. Long enough
// not to hammer the API, short enough that a 10-second clip does not look
// stuck. Polling stops entirely once nothing is processing.
const POLL_INTERVAL_MS = 3000

/**
 * Photos and videos as one ordered media list.
 *
 * They live in separate tables and separate endpoints, but the event page
 * shows them as one grid — a video is a poster frame until you click it, so
 * splitting them into two sections would only make the viewer decide which
 * half to look in.
 *
 * Takes a getter rather than an id: the detail dialog is reused across
 * events, so an id captured at setup would go stale the moment the viewer
 * opened a different one.
 */
// Merged on sort_order, not concatenated: the two lists come from separate
// tables sharing one sequence, so appending one to the other would always
// put every photo before every video regardless of how they were arranged.
// Ties fall back to type then id so the result is stable for media that
// predates any reordering, where everything still sits at 0.
export function bySortOrder(a, b) {
  return (
    a.sortOrder - b.sortOrder || a.type.localeCompare(b.type) || a.id - b.id
  )
}

export function useEventMedia(getEventId) {
  const eventId = () => getEventId()
  const photos = ref([])
  const videos = ref([])
  const loading = ref(false)
  let pollTimer = null

  const items = computed(() =>
    [
      ...photos.value.map((p) => ({
        type: 'photo',
        id: p.id,
        key: `photo-${p.id}`,
        caption: p.caption,
        thumbUrl: eventsApi.photoUrl(eventId(), p.id),
        raw: p,
        sortOrder: p.sort_order ?? 0,
      })),
      ...videos.value.map((v) => ({
        type: 'video',
        id: v.id,
        key: `video-${v.id}`,
        caption: v.caption,
        status: v.status,
        durationSeconds: v.duration_seconds,
        errorDetail: v.error_detail,
        youtubeId: v.youtube_id,
        fileUrl:
          v.kind === 'upload' && v.status === 'ready'
            ? eventsApi.videoFileUrl(eventId(), v.id)
            : null,
        kind: v.kind,
        // Rebuilt from the stored id rather than echoed from anything a user
        // typed, so the only thing reaching an iframe src is 11 characters of
        // a fixed alphabet. nocookie keeps YouTube's trackers off the page
        // until the viewer actually presses play.
        embedUrl: v.youtube_id
          ? `https://www.youtube-nocookie.com/embed/${v.youtube_id}`
          : null,
        // YouTube serves its own thumbnail, so no poster is stored for it.
        thumbUrl: v.youtube_id
          ? eventsApi.youtubeThumbUrl(v.youtube_id)
          : v.has_poster
            ? eventsApi.videoPosterUrl(eventId(), v.id)
            : null,
        raw: v,
        sortOrder: v.sort_order ?? 0,
      })),
    ].sort(bySortOrder),
  )

  const hasProcessing = computed(() =>
    videos.value.some((v) => v.status === 'processing'),
  )

  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // Only runs while something is actually transcoding, and shuts itself off
  // the moment nothing is — an idle event page issues no background requests.
  function syncPolling() {
    if (hasProcessing.value && pollTimer === null) {
      pollTimer = setInterval(refreshVideos, POLL_INTERVAL_MS)
    } else if (!hasProcessing.value) {
      stopPolling()
    }
  }

  async function refreshVideos() {
    try {
      videos.value = await eventsApi.listVideos(eventId())
    } catch {
      // A transient failure should not kill the poll loop: keep the last
      // good list and let the next tick retry.
    }
    syncPolling()
  }

  // Reports whether the fetch worked. The editor says so out loud when it
  // did not, because an empty grid there reads as "my photos are gone".
  async function load() {
    loading.value = true
    try {
      const [p, v] = await Promise.all([
        eventsApi.listPhotos(eventId()),
        eventsApi.listVideos(eventId()),
      ])
      photos.value = p
      videos.value = v
      return true
    } catch {
      photos.value = []
      videos.value = []
      return false
    } finally {
      loading.value = false
      syncPolling()
    }
  }

  function reset() {
    stopPolling()
    photos.value = []
    videos.value = []
  }

  onUnmounted(stopPolling)

  return {
    photos,
    videos,
    items,
    loading,
    hasProcessing,
    load,
    reset,
    refreshVideos,
    stopPolling,
  }
}
