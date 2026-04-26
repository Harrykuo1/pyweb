import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username, password) {
    user.value = await authApi.login(username, password)
  }

  async function logout() {
    await authApi.logout()
    user.value = null
  }

  // Used by router guard on first navigation to restore session from cookie.
  // Swallows 401 because "no session" is not an error in that context.
  async function fetchMe() {
    try {
      user.value = await authApi.getMe()
    } catch (err) {
      if (err?.response?.status === 401) {
        user.value = null
        return
      }
      throw err
    }
  }

  return { user, isAuthenticated, isAdmin, login, logout, fetchMe }
})
