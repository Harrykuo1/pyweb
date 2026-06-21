import { ref } from 'vue'
import { defineStore } from 'pinia'

import { eventsApi } from '../api/events'

// Holds the event-list result so it survives leaving and returning to the
// page within an SPA session. Filters stay in the URL (see useUrlQuerySync),
// not here. Caching is stale-while-revalidate, keyed by the request params:
// a repeat request for params we've seen paints the cached rows immediately
// (no skeleton) and silently refetches, while a new query shows the loading
// state. In-memory only — a full reload starts cold. create/update/delete
// must call invalidate() so the next fetch is authoritative. Mirrors
// useJobsStore.
export const useEventsStore = defineStore('events', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const revalidating = ref(false)

  const cache = new Map()

  function keyOf(params) {
    return JSON.stringify(params)
  }

  async function request(params, key) {
    const data = await eventsApi.list(params)
    cache.set(key, { items: data.items, total: data.total })
    items.value = data.items
    total.value = data.total
    return data
  }

  async function fetch(params) {
    const key = keyOf(params)
    const cached = cache.get(key)
    if (cached) {
      items.value = cached.items
      total.value = cached.total
      revalidating.value = true
      try {
        await request(params, key)
      } finally {
        revalidating.value = false
      }
      return
    }
    loading.value = true
    try {
      await request(params, key)
    } finally {
      loading.value = false
    }
  }

  function invalidate() {
    cache.clear()
  }

  return { items, total, loading, revalidating, fetch, invalidate }
})
