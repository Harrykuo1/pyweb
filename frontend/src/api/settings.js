import client from './client'

// Public path for the <img src=...>; appended cache-bust token forces a
// reload after upload/delete because the browser otherwise serves the
// cached old image.
export function settingImageUrl(key, cacheBustToken) {
  const base = `/api/settings/${encodeURIComponent(key)}/image`
  if (!cacheBustToken) return base
  return `${base}?v=${encodeURIComponent(cacheBustToken)}`
}

export const settingsApi = {
  async uploadImage(key, file) {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post(
      `/settings/${encodeURIComponent(key)}/image`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  async deleteImage(key) {
    await client.delete(`/settings/${encodeURIComponent(key)}/image`)
  },
  async getConfig() {
    const { data } = await client.get('/settings/config')
    return data
  },
  async updateConfig(values) {
    const { data } = await client.put('/settings/config', { values })
    return data
  },
}
