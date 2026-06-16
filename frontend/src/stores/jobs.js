import { ref } from 'vue'
import { defineStore } from 'pinia'

import { jobsApi } from '../api/jobs'

// Holds the job-list result so it survives leaving and returning to the
// page within an SPA session. Filters are deliberately NOT stored here —
// they live in the URL (see useUrlQuerySync) so a bare /jobs from the nav
// bar always lands on a clean, complete list. The store owns only the
// server data and the in-flight flag; SWR caching lands on top in a later
// step.
export const useJobsStore = defineStore('jobs', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)

  async function fetch(params) {
    loading.value = true
    try {
      const data = await jobsApi.list(params)
      items.value = data.items
      total.value = data.total
      return data
    } finally {
      loading.value = false
    }
  }

  return { items, total, loading, fetch }
})
