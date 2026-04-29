import client from './client'

export const jobsApi = {
  async list({
    sort = 'created_at',
    order = 'desc',
    year,
    company,
    category,
    kind,
    q,
  } = {}) {
    // Build the query string by hand so company=[A,B] serializes as
    // ?company=A&company=B (FastAPI repeated-param style) instead of
    // axios's default ?company[]=A&company[]=B which would not match
    // FastAPI's Query(default_factory=list).
    const search = new URLSearchParams()
    search.set('sort', sort)
    search.set('order', order)
    if (year !== undefined && year !== null && year !== '') {
      search.set('year', year)
    }
    if (Array.isArray(company)) {
      for (const c of company) if (c) search.append('company', c)
    } else if (company) {
      search.append('company', company)
    }
    if (Array.isArray(category)) {
      for (const c of category) if (c) search.append('category', c)
    } else if (category) {
      search.append('category', category)
    }
    if (kind) search.set('kind', kind)
    if (q) search.set('q', q)
    const { data } = await client.get(`/jobs?${search.toString()}`)
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
  async listCategories(prefix) {
    const params = {}
    if (prefix) params.prefix = prefix
    const { data } = await client.get('/jobs/categories', { params })
    return data
  },
}
