import client from './client'

export const authApi = {
  async login(password) {
    const { data } = await client.post('/auth/login', { password })
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
