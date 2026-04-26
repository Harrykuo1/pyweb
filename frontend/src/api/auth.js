import client from './client'

export const authApi = {
  async login(username, password) {
    const { data } = await client.post('/auth/login', { username, password })
    return data
  },
  async logout() {
    await client.post('/auth/logout')
  },
  async getMe() {
    const { data } = await client.get('/auth/me')
    return data
  },
}
