import client from './client'

export const statsApi = {
  async get() {
    const { data } = await client.get('/stats')
    return data
  },
}
