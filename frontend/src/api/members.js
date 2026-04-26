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
  async remove(id) {
    await client.delete(`/members/${id}`)
  },
}
