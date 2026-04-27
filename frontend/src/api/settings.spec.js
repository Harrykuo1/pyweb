import { afterEach, describe, expect, it, vi } from 'vitest'

import client from './client'
import { settingImageUrl, settingsApi } from './settings'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('settingImageUrl', () => {
  it('returns the bare path with no token', () => {
    expect(settingImageUrl('login_logo')).toBe('/api/settings/login_logo/image')
  })

  it('appends a v= cache-bust token when given', () => {
    expect(settingImageUrl('login_logo', '2024-05-01T00:00:00')).toBe(
      '/api/settings/login_logo/image?v=2024-05-01T00%3A00%3A00',
    )
  })

  it('encodes special characters in the key', () => {
    expect(settingImageUrl('a/b')).toBe('/api/settings/a%2Fb/image')
  })
})

describe('settingsApi.uploadImage', () => {
  it('POSTs FormData with multipart header to /settings/{key}/image', async () => {
    const fakeFile = new File([new Uint8Array([1, 2, 3])], 'logo.png', {
      type: 'image/png',
    })
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: { key: 'login_logo', size: 3, content_type: 'image/png' },
    })

    const result = await settingsApi.uploadImage('login_logo', fakeFile)

    expect(post).toHaveBeenCalledTimes(1)
    const [path, body, opts] = post.mock.calls[0]
    expect(path).toBe('/settings/login_logo/image')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file')).toBe(fakeFile)
    expect(opts.headers['Content-Type']).toBe('multipart/form-data')
    expect(result.size).toBe(3)
  })
})

describe('settingsApi.deleteImage', () => {
  it('DELETEs /settings/{key}/image', async () => {
    const del = vi.spyOn(client, 'delete').mockResolvedValue({ data: null })

    await settingsApi.deleteImage('login_logo')

    expect(del).toHaveBeenCalledWith('/settings/login_logo/image')
  })
})
