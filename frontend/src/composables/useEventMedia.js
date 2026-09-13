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
export function useEventMedia(getEventId) {
  const eventId = () => getEventId()
  const photos = ref([])
  const videos = ref([])
  const loading = ref(false)
  let pollTimer = null

  const items = computed(() => [
    ...photos.value.map((p) => ({
      type: 'photo',
      id: p.id,
      key: `photo-${p.id}`,
      caption: p.caption,
      thumbUrl: eventsApi.photoUrl(eventId(), p.id),
      raw: p,
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
      // A row that is still transcoding, or failed, has no poster to show.
      thumbUrl: v.has_poster ? eventsApi.videoPosterUrl(eventId(), v.id) : null,
      fileUrl:
        v.status === 'ready' ? eventsApi.videoFileUrl(eventId(), v.id) : null,
      raw: v,
    })),
  ])

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
      // A transient failure should not kill the poll loop; the next tick
      // retries. A persistent one stops it via the status check below.
      videos.value = videos.value
    }
    syncPolling()
  }

  async function load() {
    loading.value = true
    try {
      const [p, v] = await Promise.all([
        eventsApi.listPhotos(eventId()),
        eventsApi.listVideos(eventId()),
      ])
      photos.value = p
      videos.value = v
    } catch {
      photos.value = []
      videos.value = []
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
