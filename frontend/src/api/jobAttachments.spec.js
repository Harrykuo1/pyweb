import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import {
  attachmentPreviewUrl,
  attachmentUrl,
  jobAttachmentsApi,
} from './jobAttachments'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('attachmentUrl', () => {
  it('builds the inline-preview path', () => {
    expect(attachmentUrl(7, 42)).toBe('/api/jobs/7/attachments/42')
  })
})

describe('attachmentPreviewUrl', () => {
  it('builds the office-preview PDF path', () => {
    expect(attachmentPreviewUrl(7, 42)).toBe('/api/jobs/7/attachments/42/preview')
  })
})

describe('jobAttachmentsApi.list', () => {
  it('GETs /jobs/{id}/attachments', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({ data: [{ id: 1 }] })
    const rows = await jobAttachmentsApi.list(7)
    expect(get).toHaveBeenCalledWith('/jobs/7/attachments')
    expect(rows).toEqual([{ id: 1 }])
  })
})

describe('jobAttachmentsApi.upload', () => {
  it('POSTs multipart form with the file alone when no strategy is given', async () => {
    const file = new File([new Uint8Array([1, 2])], 'a.pdf', { type: 'application/pdf' })
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 11 } })

    const result = await jobAttachmentsApi.upload(7, file)

    expect(post).toHaveBeenCalledTimes(1)
    const [path, body, opts] = post.mock.calls[0]
    expect(path).toBe('/jobs/7/attachments')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file')).toBe(file)
    expect(body.get('conflict_strategy')).toBeNull()
    expect(opts.headers['Content-Type']).toBe('multipart/form-data')
    expect(result.id).toBe(11)
  })

  it('includes conflict_strategy in the form when provided', async () => {
    const file = new File([new Uint8Array([1])], 'a.pdf', { type: 'application/pdf' })
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 12 } })

    await jobAttachmentsApi.upload(7, file, 'overwrite')

    const [, body] = post.mock.calls[0]
    expect(body.get('conflict_strategy')).toBe('overwrite')
  })
})

describe('jobAttachmentsApi.remove', () => {
  it('DELETEs /jobs/{id}/attachments/{aid}', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({ data: null })

    await jobAttachmentsApi.remove(7, 11)

    expect(del).toHaveBeenCalledWith('/jobs/7/attachments/11')
  })
})
