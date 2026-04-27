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
  async update(id, payload) {
    const { data } = await client.put(`/members/${id}`, payload)
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
  async deletePhoto(id, password) {
    await client.delete(`/members/${id}/photo`, { data: { password } })
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
  async deleteResumePdf(id, password) {
    await client.delete(`/members/${id}/resume.pdf`, { data: { password } })
  },
}
