import { ref } from 'vue'
import { defineStore } from 'pinia'

import { membersApi } from '../api/members'

// Holds the full members list so it survives leaving and returning to the
// page within an SPA session. Members filter/sort entirely client-side, so
// the list is fetched whole and the cache is a single flag rather than a
// params map. Stale-while-revalidate: once loaded, a revisit paints the
// cached rows immediately (no skeleton) and refetches in the background; a
// cold load shows loading. In-memory only. create/update/delete and photo
// changes must call invalidate() so the next fetch is authoritative.
export const useMembersStore = defineStore('members', () => {
  const members = ref([])
  const loading = ref(false)
  const revalidating = ref(false)
  let loaded = false

  async function request() {
    members.value = await membersApi.list()
    loaded = true
  }

  async function fetch() {
    if (loaded) {
      revalidating.value = true
      try {
        await request()
      } finally {
        revalidating.value = false
      }
      return
    }
    loading.value = true
    try {
      await request()
    } finally {
      loading.value = false
    }
  }

  function invalidate() {
    loaded = false
  }

  return { members, loading, revalidating, fetch, invalidate }
})
