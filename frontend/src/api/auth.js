import client from './client'

// Discord OAuth is a full-page browser redirect (not an XHR), so the login
// button navigates the window here rather than calling it via axios.
export const DISCORD_LOGIN_URL = '/api/auth/discord/login'

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
  async listUsers() {
    const { data } = await client.get('/auth/users')
    return data
  },
  async updateUsername(role, username) {
    const { data } = await client.patch(`/auth/users/${role}/username`, {
      username,
    })
    return data
  },
  async updatePassword(role, currentPassword, newPassword) {
    await client.patch(`/auth/users/${role}/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}
