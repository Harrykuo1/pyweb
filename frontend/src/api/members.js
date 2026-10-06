import client from './client'

export const membersApi = {
  async list({ order = 'asc' } = {}) {
    const { data } = await client.get('/members', { params: { order } })
    return data
  },
  async get(id) {
    const { data } = await client.get(`/members/${id}`)
    return data
  },
  async create(payload) {
    const { data } = await client.post('/members', payload)
    return data
  },
  // Self-service: a freshly-registered member creates their own profile once.
  async createMyProfile(payload) {
    const { data } = await client.post('/members/me', payload)
    return data
  },
  async update(id, payload) {
    const { data } = await client.put(`/members/${id}`, payload)
    return data
  },
  async getDiscordLink(id) {
    const { data } = await client.get(`/members/${id}/discord-link`)
    return data
  },
  async replaceDiscordLink(id, payload) {
    const { data } = await client.patch(`/members/${id}/discord-link`, payload)
    return data
  },
  async linkDiscord(id, payload) {
    const { data } = await client.post(`/members/${id}/discord-link`, payload)
    return data
  },
  async remove(id, password) {
    await client.delete(`/members/${id}`, { data: { password } })
  },

  // ---- photo ----
  // The browser sends cookies cross-origin via the axios client only because
  // withCredentials is set. For <img>/<iframe> src URLs the browser handles
  // cookies the same way for same-origin resources.
  photoUrl(id, cacheBuster = '') {
    const suffix = cacheBuster ? `?v=${encodeURIComponent(cacheBuster)}` : ''
    return `/api/members/${id}/photo${suffix}`
  },
  async uploadPhoto(id, file) {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post(`/members/${id}/photo`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  // password is admin-only re-auth; an owning member deletes their own photo
  // with no body at all (the backend treats a bodyless DELETE as "no password
  // required" for the owner). Sending {password: undefined} would serialize to
  // an empty object and fail validation, so omit the body entirely.
  async deletePhoto(id, password) {
    const config = password === undefined ? undefined : { data: { password } }
    await client.delete(`/members/${id}/photo`, config)
  },

  // ---- resume pdf ----
  resumePdfUrl(id, cacheBuster = '') {
    const suffix = cacheBuster ? `?v=${encodeURIComponent(cacheBuster)}` : ''
    return `/api/members/${id}/resume.pdf${suffix}`
  },
  async uploadResumePdf(id, file) {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post(`/members/${id}/resume.pdf`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
  // See deletePhoto: owning members delete without a password body.
  async deleteResumePdf(id, password) {
    const config = password === undefined ? undefined : { data: { password } }
    await client.delete(`/members/${id}/resume.pdf`, config)
  },

  // ---- routing ----
  // Single source of truth for "scroll to and highlight this member" URLs.
  // Members has no detail dialog, so we deep-link via a transient ?focus=
  // param that Members.vue consumes to scroll and flash the row, then
  // strips from the URL. See jobsApi.detailRoute for the analogous helper.
  focusRoute(id) {
    return { path: '/members', query: { focus: String(id) } }
  },
}
