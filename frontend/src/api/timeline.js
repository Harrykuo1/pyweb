import client from './client'

export const timelineApi = {
  async list({ limit, before } = {}) {
    const params = {}
    if (limit !== undefined && limit !== null) params.limit = limit
    // `before` is the timestamp of the last item the caller already has.
    // Server returns rows strictly older than this — caller walks the
    // feed backwards as the user scrolls.
    if (before !== undefined && before !== null) params.before = before
    const { data } = await client.get('/timeline', { params })
    return data
  },
}
