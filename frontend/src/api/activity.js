import client from './client'

export const activityApi = {
  async options(signal) {
    const { data } = await client.get('/activity/options', { signal })
    return data
  },
  async analytics(filters, signal) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item !== '' && item != null) params.append(key, String(item))
      }
    }
    const { data } = await client.get('/activity/analytics', { params, signal })
    return data
  },
}
