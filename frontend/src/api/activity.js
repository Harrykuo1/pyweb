import client from './client'

export const activityApi = {
  async list({ limit } = {}) {
    const params = {}
    if (limit !== undefined && limit !== null) params.limit = limit
    const { data } = await client.get('/activity', { params })
    return data
  },
}
