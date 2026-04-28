import client from './client'

export const internshipsApi = {
  async list({
    sort = 'created_at',
    order = 'desc',
    year,
    company,
    kind,
    q,
  } = {}) {
    const params = { sort, order }
    if (year !== undefined && year !== null && year !== '') params.year = year
    if (company) params.company = company
    if (kind) params.kind = kind
    if (q) params.q = q
    const { data } = await client.get('/internships', { params })
    return data
  },
  async get(id) {
    const { data } = await client.get(`/internships/${id}`)
    return data
  },
  async create(payload) {
    const { data } = await client.post('/internships', payload)
    return data
  },
  async update(id, payload) {
    const { data } = await client.put(`/internships/${id}`, payload)
    return data
  },
  async remove(id, password) {
    await client.delete(`/internships/${id}`, { data: { password } })
  },
  async listCompanies(prefix) {
    const params = {}
    if (prefix) params.prefix = prefix
    const { data } = await client.get('/internships/companies', { params })
    return data
  },
}
