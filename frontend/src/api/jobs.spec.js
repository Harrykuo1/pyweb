import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { jobsApi } from './jobs'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('jobsApi.list', () => {
  it('GETs /jobs with default sort=created_at, order=desc', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list()
    expect(get).toHaveBeenCalledWith('/jobs', {
      params: { sort: 'created_at', order: 'desc' },
    })
  })

  it('passes sort/order/year/company/kind/q through', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({
      sort: 'company',
      order: 'asc',
      year: 2024,
      company: 'Acme',
      kind: 'fulltime',
      q: 'interview',
    })
    expect(get).toHaveBeenCalledWith('/jobs', {
      params: {
        sort: 'company',
        order: 'asc',
        year: 2024,
        company: 'Acme',
        kind: 'fulltime',
        q: 'interview',
      },
    })
  })

  it('omits empty filter params from the request', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({ year: '', company: '', kind: '', q: '' })
    expect(get).toHaveBeenCalledWith('/jobs', {
      params: { sort: 'created_at', order: 'desc' },
    })
  })

  it('returns the {items, total} envelope unchanged', async () => {
    const fake = {
      items: [{ id: 1, company: 'Acme', kind: 'internship' }],
      total: 1,
    }
    vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await jobsApi.list()
    expect(result).toEqual(fake)
  })
})

describe('jobsApi.get', () => {
  it('GETs /jobs/:id', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: { id: 7 } })
    const result = await jobsApi.get(7)
    expect(get).toHaveBeenCalledWith('/jobs/7')
    expect(result).toEqual({ id: 7 })
  })
})

describe('jobsApi.create / update', () => {
  it('POSTs to /jobs', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const payload = {
      job_year: 2025,
      company: 'Acme',
      kind: 'internship',
      experience_md: 'x',
    }
    const result = await jobsApi.create(payload)
    expect(post).toHaveBeenCalledWith('/jobs', payload)
    expect(result).toEqual({ id: 1 })
  })

  it('PUTs partial payload to /jobs/:id', async () => {
    const put = vi
      .spyOn(client, 'put')
      .mockResolvedValue({ data: { id: 5, kind: 'fulltime' } })
    const result = await jobsApi.update(5, { kind: 'fulltime' })
    expect(put).toHaveBeenCalledWith('/jobs/5', { kind: 'fulltime' })
    expect(result.kind).toBe('fulltime')
  })
})

describe('jobsApi.remove', () => {
  it('DELETEs with the admin password in the body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await jobsApi.remove(9, 'pw')
    expect(del).toHaveBeenCalledWith('/jobs/9', {
      data: { password: 'pw' },
    })
  })
})

describe('jobsApi.listCompanies', () => {
  it('GETs /jobs/companies with no prefix by default', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: ['Acme'] })
    const result = await jobsApi.listCompanies()
    expect(get).toHaveBeenCalledWith('/jobs/companies', { params: {} })
    expect(result).toEqual(['Acme'])
  })

  it('passes prefix when provided', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await jobsApi.listCompanies('ac')
    expect(get).toHaveBeenCalledWith('/jobs/companies', {
      params: { prefix: 'ac' },
    })
  })
})
