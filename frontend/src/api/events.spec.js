import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { eventsApi } from './events'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('eventsApi.list', () => {
  it('GETs /events with default sort=event_date, order=desc', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await eventsApi.list()
    expect(get).toHaveBeenCalledWith('/events?sort=event_date&order=desc')
  })

  it('passes sort/order/year/tag/q with repeated tag params', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await eventsApi.list({
      sort: 'title',
      order: 'asc',
      year: 2026,
      tag: ['聚餐', '出遊'],
      q: '桌遊',
    })
    expect(get).toHaveBeenCalledWith(
      '/events?sort=title&order=asc&year=2026&tag=%E8%81%9A%E9%A4%90&tag=%E5%87%BA%E9%81%8A&q=%E6%A1%8C%E9%81%8A',
    )
  })

  it('omits empty filter params', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockResolvedValue({ data: { items: [], total: 0 } })
    await eventsApi.list({ year: '', tag: [], q: '' })
    expect(get).toHaveBeenCalledWith('/events?sort=event_date&order=desc')
  })
})

describe('eventsApi CRUD', () => {
  it('GETs /events/:id', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: { id: 3 } })
    expect(await eventsApi.get(3)).toEqual({ id: 3 })
    expect(get).toHaveBeenCalledWith('/events/3')
  })

  it('POSTs to /events', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    const payload = { title: 'x', event_date: '2026-03-01', tags: [] }
    expect(await eventsApi.create(payload)).toEqual({ id: 1 })
    expect(post).toHaveBeenCalledWith('/events', payload)
  })

  it('PUTs partial payload to /events/:id', async () => {
    const put = vi.spyOn(client, 'put').mockResolvedValue({ data: { id: 5 } })
    await eventsApi.update(5, { title: 'y' })
    expect(put).toHaveBeenCalledWith('/events/5', { title: 'y' })
  })

  it('DELETEs with the admin password in the body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await eventsApi.remove(9, 'pw')
    expect(del).toHaveBeenCalledWith('/events/9', { data: { password: 'pw' } })
  })

  it('DELETEs with no body when no password is given (owner)', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await eventsApi.remove(9)
    expect(del).toHaveBeenCalledWith('/events/9', undefined)
  })
})

describe('eventsApi review actions', () => {
  it('forwards a status filter on list', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: {} })
    await eventsApi.list({ status: 'pending' })
    expect(get.mock.calls[0][0]).toContain('status=pending')
  })

  it('POSTs to /events/:id/accept', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 9 } })
    await eventsApi.accept(9)
    expect(post).toHaveBeenCalledWith('/events/9/accept')
  })

  it('POSTs the reason to /events/:id/reject', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 9 } })
    await eventsApi.reject(9, '照片不足')
    expect(post).toHaveBeenCalledWith('/events/9/reject', {
      reason: '照片不足',
    })
  })
})

describe('eventsApi.listTags', () => {
  it('GETs /events/tags with no prefix by default', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: ['聚餐'] })
    expect(await eventsApi.listTags()).toEqual(['聚餐'])
    expect(get).toHaveBeenCalledWith('/events/tags', { params: {} })
  })

  it('passes prefix when provided', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await eventsApi.listTags('聚')
    expect(get).toHaveBeenCalledWith('/events/tags', {
      params: { prefix: '聚' },
    })
  })
})

describe('eventsApi photos', () => {
  it('GETs the photo list', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await eventsApi.listPhotos(2)
    expect(get).toHaveBeenCalledWith('/events/2/photos')
  })

  it('POSTs multipart form data on upload', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 7 } })
    const file = new File(['x'], 'p.png', { type: 'image/png' })
    await eventsApi.uploadPhoto(2, file, '說明')
    const [url, form, opts] = post.mock.calls[0]
    expect(url).toBe('/events/2/photos')
    expect(form).toBeInstanceOf(FormData)
    expect(form.get('caption')).toBe('說明')
    expect(opts.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('PUTs caption updates', async () => {
    const put = vi.spyOn(client, 'put').mockResolvedValue({ data: {} })
    await eventsApi.updatePhotoCaption(2, 7, 'c')
    expect(put).toHaveBeenCalledWith('/events/2/photos/7', { caption: 'c' })
  })

  it('DELETEs a photo with the password', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await eventsApi.removePhoto(2, 7, 'pw')
    expect(del).toHaveBeenCalledWith('/events/2/photos/7', {
      data: { password: 'pw' },
    })
  })

  it('builds a content-addressed photo URL', () => {
    expect(eventsApi.photoUrl(2, 7)).toBe('/api/events/2/photos/7')
  })
})

describe('eventsApi comments', () => {
  it('GETs the comment list', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await eventsApi.listComments(2)
    expect(get).toHaveBeenCalledWith('/events/2/comments')
  })

  it('POSTs a new comment body', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 1 } })
    await eventsApi.createComment(2, '讚')
    expect(post).toHaveBeenCalledWith('/events/2/comments', { body: '讚' })
  })

  it('PUTs an edited comment body', async () => {
    const put = vi.spyOn(client, 'put').mockResolvedValue({ data: { id: 1 } })
    await eventsApi.updateComment(2, 5, '更正')
    expect(put).toHaveBeenCalledWith('/events/2/comments/5', { body: '更正' })
  })

  it('DELETEs own comment with no body', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await eventsApi.removeComment(2, 5)
    expect(del).toHaveBeenCalledWith('/events/2/comments/5', undefined)
  })

  it('DELETEs another comment with the admin password', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})
    await eventsApi.removeComment(2, 5, 'pw')
    expect(del).toHaveBeenCalledWith('/events/2/comments/5', {
      data: { password: 'pw' },
    })
  })
})

describe('eventsApi likes', () => {
  it('POSTs a like and returns the status', async () => {
    const post = vi
      .spyOn(client, 'post')
      .mockResolvedValue({ data: { like_count: 1, liked: true } })
    expect(await eventsApi.like(2)).toEqual({ like_count: 1, liked: true })
    expect(post).toHaveBeenCalledWith('/events/2/like')
  })

  it('DELETEs a like and returns the status', async () => {
    const del = vi
      .spyOn(client, 'delete')
      .mockResolvedValue({ data: { like_count: 0, liked: false } })
    expect(await eventsApi.unlike(2)).toEqual({ like_count: 0, liked: false })
    expect(del).toHaveBeenCalledWith('/events/2/like')
  })

  it('GETs the likers list', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [] })
    await eventsApi.listLikers(2)
    expect(get).toHaveBeenCalledWith('/events/2/likes')
  })
})

describe('eventsApi.detailRoute', () => {
  it('returns a router location pointing at /events with detail=<id>', () => {
    expect(eventsApi.detailRoute(12)).toEqual({
      path: '/events',
      query: { detail: '12' },
    })
  })
})
