import { ref } from 'vue'
import { defineStore } from 'pinia'

import { jobsApi } from '../api/jobs'

// Holds the job-list result so it survives leaving and returning to the
// page within an SPA session. Filters are deliberately NOT stored here —
// they live in the URL (see useUrlQuerySync) so a bare /jobs from the nav
// bar always lands on a clean, complete list.
//
// Caching is stale-while-revalidate, keyed by the request params: a repeat
// request for params we've seen paints the cached rows immediately (no
// skeleton) and silently refetches in the background, while a brand-new
// query shows the loading skeleton. The cache is in-memory only — a full
// page reload starts cold. Any create/update/delete must call invalidate()
// so the next fetch is authoritative rather than serving a stale row.
export const useJobsStore = defineStore('jobs', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false) // cold fetch (no cache) — drives the skeleton
  const revalidating = ref(false) // background refresh over cached rows

  const cache = new Map()

  function keyOf(params) {
    return JSON.stringify(params)
  }

  async function request(params, key) {
    const data = await jobsApi.list(params)
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
