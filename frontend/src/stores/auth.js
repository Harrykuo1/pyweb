import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)

  // Admin-only UI affordance: while true, isAdmin pretends to be false so
  // every v-if="auth.isAdmin" hides itself, letting an admin preview the
  // viewer experience without losing real backend permissions.
  const viewAsViewer = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const actualRole = computed(() => user.value?.role ?? null)
  const isActuallyAdmin = computed(() => actualRole.value === 'admin')
  const isAdmin = computed(() => isActuallyAdmin.value && !viewAsViewer.value)
  const isViewingAsViewer = computed(
    () => isActuallyAdmin.value && viewAsViewer.value,
  )

  async function login(password) {
    user.value = await authApi.login(password)
    viewAsViewer.value = false
  }

  async function logout() {
    await authApi.logout()
    user.value = null
    viewAsViewer.value = false
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

  function setViewAsViewer(flag) {
    if (!isActuallyAdmin.value) return
    viewAsViewer.value = !!flag
  }

  async function updateUsername(role, username) {
    const updated = await authApi.updateUsername(role, username)
    // If the admin renamed themselves, reflect it in the current session
    // so the navbar shows the new name without a re-login.
    if (user.value && updated.id === user.value.id) {
      user.value = { ...user.value, username: updated.username }
    }
    return updated
  }

  async function updatePassword(role, currentPassword, newPassword) {
    await authApi.updatePassword(role, currentPassword, newPassword)
  }

  return {
    user,
    viewAsViewer,
    isAuthenticated,
    isAdmin,
    isActuallyAdmin,
    isViewingAsViewer,
    actualRole,
    login,
    logout,
    fetchMe,
    setViewAsViewer,
    updateUsername,
    updatePassword,
  }
})
