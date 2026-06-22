import { eventsApi } from '../api/events'
import { createListStore } from './createListStore'

// Holds the event-list result so it survives leaving and returning to the
// page within an SPA session. Filters stay in the URL (see useUrlQuerySync),
// not here. SWR caching + invalidation come from the shared createListStore
// factory.
export const useEventsStore = createListStore('events', (params) =>
  eventsApi.list(params),
)
