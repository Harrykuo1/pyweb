import client from './client'

export const apiDocsApi = {
  async get(signal) {
    const { data } = await client.get('/admin/api-docs', { signal })
    return data
  },
}
