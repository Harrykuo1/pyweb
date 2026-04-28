import client from './client'

export const jobsApi = {
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
    const { data } = await client.get('/jobs', { params })
    return data
  },
  async get(id) {
    const { data } = await client.get(`/jobs/${id}`)
    return data
  },
  async create(payload) {
    const { data } = await client.post('/jobs', payload)
    return data
  },
  async update(id, payload) {
    const { data } = await client.put(`/jobs/${id}`, payload)
    return data
  },
  async remove(id, password) {
    await client.delete(`/jobs/${id}`, { data: { password } })
  },
  async listCompanies(prefix) {
    const params = {}
    if (prefix) params.prefix = prefix
    const { data } = await client.get('/jobs/companies', { params })
    return data
  },
}
