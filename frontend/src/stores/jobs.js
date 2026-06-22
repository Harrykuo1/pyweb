import { jobsApi } from '../api/jobs'
import { createListStore } from './createListStore'

// Holds the job-list result so it survives leaving and returning to the
// page within an SPA session. Filters are deliberately NOT stored here —
// they live in the URL (see useUrlQuerySync) so a bare /jobs from the nav
// bar always lands on a clean, complete list. SWR caching + invalidation
// come from the shared createListStore factory.
export const useJobsStore = createListStore('jobs', (params) =>
  jobsApi.list(params),
)
