import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { membersApi } from './members'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('membersApi.list', () => {
  it('GETs /members with default order=asc', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await membersApi.list()
    expect(get).toHaveBeenCalledWith('/members', { params: { order: 'asc' } })
  })

  it('passes through order=desc', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await membersApi.list({ order: 'desc' })
    expect(get).toHaveBeenCalledWith('/members', { params: { order: 'desc' } })
  })

  it('returns the response data array', async () => {
    const fake = [{ id: 1, real_name: 'A' }]
    vi.spyOn(client, 'get').mockResolvedValue({ data: fake })
    const result = await membersApi.list()
    expect(result).toEqual(fake)
  })
})

describe('membersApi.get', () => {
  it('GETs /members/:id', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: { id: 5 } })
    const result = await membersApi.get(5)
    expect(get).toHaveBeenCalledWith('/members/5')
    expect(result).toEqual({ id: 5 })
  })
})

describe('membersApi.create', () => {
  it('POSTs payload to /members', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const payload = { graduation_year: 2024, real_name: 'A', institution: 'B' }
    const result = await membersApi.create(payload)
    expect(post).toHaveBeenCalledWith('/members', payload)
    expect(result).toEqual({ id: 1 })
  })
})

describe('membersApi.update', () => {
  it('PUTs partial payload to /members/:id', async () => {
    const put = vi.spyOn(client, 'put').mockResolvedValue({
      data: { id: 5, real_name: 'New' },
    })
    const result = await membersApi.update(5, { real_name: 'New' })
    expect(put).toHaveBeenCalledWith('/members/5', { real_name: 'New' })
    expect(result.real_name).toBe('New')
  })
})

describe('membersApi.remove', () => {
  it('DELETEs /members/:id with the admin password in the request body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({ data: null })
    await membersApi.remove(7, 'pw-1')
    expect(del).toHaveBeenCalledWith('/members/7', { data: { password: 'pw-1' } })
  })
})

describe('membersApi.photoUrl', () => {
  it('returns the absolute /api path', () => {
    expect(membersApi.photoUrl(7)).toBe('/api/members/7/photo')
  })

  it('appends a cache-buster when provided', () => {
    const url = membersApi.photoUrl(7, 'abc 1')
    expect(url).toBe('/api/members/7/photo?v=abc%201')
  })
})

describe('membersApi.uploadPhoto', () => {
  it('POSTs multipart form-data with the file field', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: { id: 1, has_photo: true },
    })
    const file = new File(['data'], 'a.png', { type: 'image/png' })

    const result = await membersApi.uploadPhoto(1, file)

    expect(post).toHaveBeenCalledTimes(1)
    const [url, body, options] = post.mock.calls[0]
    expect(url).toBe('/members/1/photo')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file')).toBeInstanceOf(File)
    expect(body.get('file').name).toBe('a.png')
    expect(options.headers['Content-Type']).toBe('multipart/form-data')
    expect(result.has_photo).toBe(true)
  })
})

describe('membersApi.deletePhoto', () => {
  it('DELETEs /members/:id/photo with the admin password in the request body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await membersApi.deletePhoto(7, 'pw-2')
    expect(del).toHaveBeenCalledWith('/members/7/photo', { data: { password: 'pw-2' } })
  })
})

describe('membersApi.resumePdfUrl', () => {
  it('returns /api path with .pdf suffix', () => {
    expect(membersApi.resumePdfUrl(7)).toBe('/api/members/7/resume.pdf')
  })

  it('supports cache-buster', () => {
    expect(membersApi.resumePdfUrl(7, 't')).toBe('/api/members/7/resume.pdf?v=t')
  })
})

describe('membersApi.uploadResumePdf', () => {
  it('POSTs multipart with the file', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: { id: 1, has_resume_pdf: true },
    })
    const file = new File(['%PDF'], 'a.pdf', { type: 'application/pdf' })

    const result = await membersApi.uploadResumePdf(1, file)

    const [url, body, options] = post.mock.calls[0]
    expect(url).toBe('/members/1/resume.pdf')
    expect(body.get('file')).toBeInstanceOf(File)
    expect(options.headers['Content-Type']).toBe('multipart/form-data')
    expect(result.has_resume_pdf).toBe(true)
  })
})

describe('membersApi.deleteResumePdf', () => {
  it('DELETEs /members/:id/resume.pdf with the admin password in the request body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await membersApi.deleteResumePdf(9, 'pw-3')
    expect(del).toHaveBeenCalledWith('/members/9/resume.pdf', { data: { password: 'pw-3' } })
  })
})

describe('membersApi.focusRoute', () => {
  it('returns a router location object pointing at /members with focus=<id>', () => {
    expect(membersApi.focusRoute(12)).toEqual({
      path: '/members',
      query: { focus: '12' },
    })
  })

  it('coerces numeric ids to string for query consistency', () => {
    expect(membersApi.focusRoute(7).query.focus).toBe('7')
  })
})
