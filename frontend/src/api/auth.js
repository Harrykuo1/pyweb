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
  // Admin: promote/demote an account between admin and member. 409 when it
  // would demote the last remaining admin.
  async assignRole(userId, role) {
    const { data } = await client.patch(`/auth/users/${userId}/role`, { role })
    return data
  },
  // Admin: one-time registration invite links (48h, single-use).
  async listRegistrationInvites() {
    const { data } = await client.get('/auth/registration-invites')
    return data
  },
  async createRegistrationInvite() {
    const { data } = await client.post('/auth/registration-invites')
    return data
  },
  async deleteRegistrationInvite(inviteId) {
    await client.delete(`/auth/registration-invites/${inviteId}`)
  },
  // Admin: Discord logins that matched no pre-created account, awaiting a
  // manual link to an existing member.
  async listPendingLinks() {
    const { data } = await client.get('/auth/pending-links')
    return data
  },
  async resolvePendingLink(discordId, memberId) {
    const { data } = await client.post(
      `/auth/pending-links/${discordId}/resolve`,
      { member_id: memberId },
    )
    return data
  },
  async deletePendingLink(discordId) {
    await client.delete(`/auth/pending-links/${discordId}`)
  },
  // Admin: the target Discord guild used for OAuth membership checks.
  async getGuildConfig() {
    const { data } = await client.get('/auth/discord/guild')
    return data
  },
  async setGuildConfig(guildId) {
    const { data } = await client.put('/auth/discord/guild', {
      guild_id: guildId,
    })
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
