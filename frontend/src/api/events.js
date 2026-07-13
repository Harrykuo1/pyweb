import client from './client'

export const eventsApi = {
  async list({
    sort = 'event_date',
    order = 'desc',
    year,
    tag,
    q,
    status,
  } = {}) {
    // Build the query by hand so tag=[A,B] serializes as ?tag=A&tag=B
    // (FastAPI repeated-param style), matching jobsApi.list.
    const search = new URLSearchParams()
    search.set('sort', sort)
    search.set('order', order)
    if (year !== undefined && year !== null && year !== '') {
      search.set('year', year)
    }
    if (Array.isArray(tag)) {
      for (const t of tag) if (t) search.append('tag', t)
    } else if (tag) {
      search.append('tag', tag)
    }
    if (q) search.set('q', q)
    if (status) search.set('status', status)
    const { data } = await client.get(`/events?${search.toString()}`)
    return data
  },
  async get(id) {
    const { data } = await client.get(`/events/${id}`)
    return data
  },
  async create(payload) {
    const { data } = await client.post('/events', payload)
    return data
  },
  async update(id, payload) {
    const { data } = await client.put(`/events/${id}`, payload)
    return data
  },
  // Admin review actions.
  async accept(id) {
    const { data } = await client.post(`/events/${id}/accept`)
    return data
  },
  async reject(id, reason) {
    const { data } = await client.post(`/events/${id}/reject`, { reason })
    return data
  },
  // password is admin-only re-auth; an owning member deletes their own event
  // with no body at all (a bodyless DELETE is "no password" for the owner).
  async remove(id, password) {
    const config = password === undefined ? undefined : { data: { password } }
    await client.delete(`/events/${id}`, config)
  },
  async listTags(prefix) {
    const params = {}
    if (prefix) params.prefix = prefix
    const { data } = await client.get('/events/tags', { params })
    return data
  },

  // ---- photos ----
  async listPhotos(eventId) {
    const { data } = await client.get(`/events/${eventId}/photos`)
    return data
  },
  async uploadPhoto(eventId, file, caption) {
    const form = new FormData()
    form.append('file', file)
    if (caption) form.append('caption', caption)
    const { data } = await client.post(`/events/${eventId}/photos`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  async updatePhotoCaption(eventId, photoId, caption) {
    const { data } = await client.put(`/events/${eventId}/photos/${photoId}`, {
      caption,
    })
    return data
  },
  async removePhoto(eventId, photoId, password) {
    // Admins send their password to re-authenticate; the post author omits
    // the body entirely so the backend takes the owner (no-password) path.
    const config = password ? { data: { password } } : undefined
    await client.delete(`/events/${eventId}/photos/${photoId}`, config)
  },
  // Content-addressed photo URL (bytes for an id never change), so no
  // cache-buster needed — see the backend's immutable Cache-Control.
  photoUrl(eventId, photoId) {
    return `/api/events/${eventId}/photos/${photoId}`
  },

  // ---- comments ----
  async listComments(eventId) {
    const { data } = await client.get(`/events/${eventId}/comments`)
    return data
  },
  async createComment(eventId, body) {
    const { data } = await client.post(`/events/${eventId}/comments`, { body })
    return data
  },
  async updateComment(eventId, commentId, body) {
    const { data } = await client.put(
      `/events/${eventId}/comments/${commentId}`,
      { body },
    )
    return data
  },
  async removeComment(eventId, commentId, password) {
    // Author omits the body (owner path); an admin moderating someone else's
    // comment sends the admin password to re-authenticate.
    const config = password ? { data: { password } } : undefined
    await client.delete(`/events/${eventId}/comments/${commentId}`, config)
  },

  // ---- routing ----
  // Single source of truth for the "open this event's detail dialog" URL
  // shape, mirroring jobsApi.detailRoute.
  detailRoute(id) {
    return { path: '/events', query: { detail: String(id) } }
  },
}
