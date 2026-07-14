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
    expect(get).toHaveBeenCalledWith('/jobs?sort=created_at&order=desc')
  })

  it('passes sort/order/year/company/category/kind/q through with array params repeated', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({
      sort: 'company',
      order: 'asc',
      year: 2024,
      company: ['Acme', 'Globex'],
      category: ['Backend', 'DevOps'],
      kind: 'fulltime',
      q: 'interview',
    })
    expect(get).toHaveBeenCalledWith(
      '/jobs?sort=company&order=asc&year=2024&company=Acme&company=Globex&category=Backend&category=DevOps&kind=fulltime&q=interview',
    )
  })

  it('accepts a bare string category for symmetry with company', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({ category: 'Backend' })
    expect(get).toHaveBeenCalledWith(
      '/jobs?sort=created_at&order=desc&category=Backend',
    )
  })

  it('accepts a bare string company for backwards compatibility', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({ company: 'Acme' })
    expect(get).toHaveBeenCalledWith(
      '/jobs?sort=created_at&order=desc&company=Acme',
    )
  })

  it('omits empty filter params from the request', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await jobsApi.list({
      year: '',
      company: [],
      category: [],
      kind: '',
      q: '',
    })
    expect(get).toHaveBeenCalledWith('/jobs?sort=created_at&order=desc')
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

  it('DELETEs with no body when no password is given (owner)', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await jobsApi.remove(9)
    expect(del).toHaveBeenCalledWith('/jobs/9', undefined)
  })
})

describe('jobsApi review actions', () => {
  it('forwards a status filter on list', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: {} })
    await jobsApi.list({ status: 'pending' })
    expect(get.mock.calls[0][0]).toContain('status=pending')
  })

  it('POSTs to /jobs/:id/accept', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 9 } })
    await jobsApi.accept(9)
    expect(post).toHaveBeenCalledWith('/jobs/9/accept')
  })

  it('POSTs the reason to /jobs/:id/reject', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 9 } })
    await jobsApi.reject(9, '內容不足')
    expect(post).toHaveBeenCalledWith('/jobs/9/reject', { reason: '內容不足' })
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

describe('jobsApi.listCategories', () => {
  it('GETs /jobs/categories with no prefix by default', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: ['Backend'] })
    const result = await jobsApi.listCategories()
    expect(get).toHaveBeenCalledWith('/jobs/categories', { params: {} })
    expect(result).toEqual(['Backend'])
  })

  it('passes prefix when provided', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await jobsApi.listCategories('de')
    expect(get).toHaveBeenCalledWith('/jobs/categories', {
      params: { prefix: 'de' },
    })
  })
})

describe('jobsApi comments + likes', () => {
  it('GETs / POSTs / PUTs / DELETEs comments', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const put = vi.spyOn(client, 'put').mockResolvedValue({ data: { id: 1 } })
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})

    await jobsApi.listComments(2)
    expect(get).toHaveBeenCalledWith('/jobs/2/comments')
    await jobsApi.createComment(2, '推')
    expect(post).toHaveBeenCalledWith('/jobs/2/comments', { body: '推' })
    await jobsApi.updateComment(2, 5, '改')
    expect(put).toHaveBeenCalledWith('/jobs/2/comments/5', { body: '改' })
    await jobsApi.removeComment(2, 5)
    expect(del).toHaveBeenCalledWith('/jobs/2/comments/5', undefined)
    await jobsApi.removeComment(2, 5, 'pw')
    expect(del).toHaveBeenCalledWith('/jobs/2/comments/5', {
      data: { password: 'pw' },
    })
  })

  it('POSTs / DELETEs a like and GETs likers', async () => {
    const post = vi
      .spyOn(client, 'post')
      .mockResolvedValue({ data: { like_count: 1, liked: true } })
    const del = vi
      .spyOn(client, 'delete')
      .mockResolvedValue({ data: { like_count: 0, liked: false } })
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })

    expect(await jobsApi.like(2)).toEqual({ like_count: 1, liked: true })
    expect(post).toHaveBeenCalledWith('/jobs/2/like')
    expect(await jobsApi.unlike(2)).toEqual({ like_count: 0, liked: false })
    expect(del).toHaveBeenCalledWith('/jobs/2/like')
    await jobsApi.listLikers(2)
    expect(get).toHaveBeenCalledWith('/jobs/2/likes')
  })
})

describe('jobsApi.detailRoute', () => {
  it('returns a router location object pointing at /jobs with detail=<id>', () => {
    expect(jobsApi.detailRoute(12)).toEqual({
      path: '/jobs',
      query: { detail: '12' },
    })
  })

  it('coerces numeric ids to string for query consistency', () => {
    // route.query values are always strings — keep our shape consistent
    // so callers can compare against route.query.detail directly.
    expect(jobsApi.detailRoute(7).query.detail).toBe('7')
  })
})
