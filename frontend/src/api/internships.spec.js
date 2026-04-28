import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { internshipsApi } from './internships'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('internshipsApi.list', () => {
  it('GETs /internships with default sort=created_at, order=desc', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await internshipsApi.list()
    expect(get).toHaveBeenCalledWith('/internships', {
      params: { sort: 'created_at', order: 'desc' },
    })
  })

  it('passes sort/order/year/company/kind/q through', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await internshipsApi.list({
      sort: 'company',
      order: 'asc',
      year: 2024,
      company: 'Acme',
      kind: 'fulltime',
      q: 'interview',
    })
    expect(get).toHaveBeenCalledWith('/internships', {
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
    await internshipsApi.list({ year: '', company: '', kind: '', q: '' })
    expect(get).toHaveBeenCalledWith('/internships', {
      params: { sort: 'created_at', order: 'desc' },
    })
  })

  it('returns the {items, total} envelope unchanged', async () => {
    const fake = {
      items: [{ id: 1, company: 'Acme', kind: 'internship' }],
      total: 1,
    }
    vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await internshipsApi.list()
    expect(result).toEqual(fake)
  })
})

describe('internshipsApi.get', () => {
  it('GETs /internships/:id', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: { id: 7 } })
    const result = await internshipsApi.get(7)
    expect(get).toHaveBeenCalledWith('/internships/7')
    expect(result).toEqual({ id: 7 })
  })
})

describe('internshipsApi.create / update', () => {
  it('POSTs to /internships', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const payload = {
      job_year: 2025,
      company: 'Acme',
      kind: 'internship',
      experience_md: 'x',
    }
    const result = await internshipsApi.create(payload)
    expect(post).toHaveBeenCalledWith('/internships', payload)
    expect(result).toEqual({ id: 1 })
  })

  it('PUTs partial payload to /internships/:id', async () => {
    const put = vi
      .spyOn(client, 'put')
      .mockResolvedValue({ data: { id: 5, kind: 'fulltime' } })
    const result = await internshipsApi.update(5, { kind: 'fulltime' })
    expect(put).toHaveBeenCalledWith('/internships/5', { kind: 'fulltime' })
    expect(result.kind).toBe('fulltime')
  })
})

describe('internshipsApi.remove', () => {
  it('DELETEs with the admin password in the body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await internshipsApi.remove(9, 'pw')
    expect(del).toHaveBeenCalledWith('/internships/9', {
      data: { password: 'pw' },
    })
  })
})

describe('internshipsApi.listCompanies', () => {
  it('GETs /internships/companies with no prefix by default', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: ['Acme'] })
    const result = await internshipsApi.listCompanies()
    expect(get).toHaveBeenCalledWith('/internships/companies', { params: {} })
    expect(result).toEqual(['Acme'])
  })

  it('passes prefix when provided', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await internshipsApi.listCompanies('ac')
    expect(get).toHaveBeenCalledWith('/internships/companies', {
      params: { prefix: 'ac' },
    })
  })
})
