import { ref } from 'vue'
import { defineStore } from 'pinia'

// Factory for a stale-while-revalidate list store keyed by request params.
// A repeat request for params we've already seen paints the cached
// items + total immediately (no skeleton) and silently refetches in the
// background, while a brand-new query shows the loading flag. The cache is
// in-memory only — a full page reload starts cold. Any create/update/
// delete must call invalidate() so the next fetch is authoritative rather
// than serving a stale row.
//
// Used by the Jobs and Events lists, which share this exact shape. (The
// Members store is intentionally NOT built on this — it fetches the whole
// list once with no params and filters client-side, so it has a different
// state shape and a single-flag cache.)
export function createListStore(id, listFn) {
  return defineStore(id, () => {
    const items = ref([])
    const total = ref(0)
    const loading = ref(false) // cold fetch (no cache) — drives the skeleton
    const revalidating = ref(false) // background refresh over cached rows

    const cache = new Map()

    async function request(params, key) {
      const data = await listFn(params)
      cache.set(key, { items: data.items, total: data.total })
      items.value = data.items
      total.value = data.total
    }

    async function fetch(params) {
      const key = JSON.stringify(params)
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
}
