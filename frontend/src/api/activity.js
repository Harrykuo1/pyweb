import client from './client'

function queryParams(filters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== '' && item != null) params.append(key, String(item))
    }
  }
  return params
}

export const activityApi = {
  async updateChannel(id, name) {
    const { data } = await client.patch(`/activity/channels/${id}`, { name })
    return data
  },
  async memberTrends(filters, signal) {
    const { data } = await client.get('/activity/member-trends', {
      params: queryParams(filters),
      signal,
    })
    return data
  },
  async options(signal) {
    const { data } = await client.get('/activity/options', { signal })
    return data
  },
  async analytics(filters, signal) {
    const params = queryParams(filters)
    const { data } = await client.get('/activity/analytics', { params, signal })
    return data
  },
}
