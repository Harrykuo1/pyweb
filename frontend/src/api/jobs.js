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
  // password is admin-only re-auth; an owning member deletes their own post
  // with no body at all. Sending {password: undefined} would serialize to an
  // empty object and 422, so omit the body entirely.
  async remove(id, password) {
    const config = password === undefined ? undefined : { data: { password } }
    await client.delete(`/jobs/${id}`, config)
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

  // ---- routing ----
  // Single source of truth for the "open this job's detail dialog" URL
  // shape. Callers that want to deep-link from elsewhere (e.g. the
  // home-page timeline feed) should go through this helper rather than
  // hand-building the query, so renaming the param later only touches
  // one place. Returns a vue-router location object usable with
  // router.push() / router.replace().
  detailRoute(id) {
    return { path: '/jobs', query: { detail: String(id) } }
  },
}
