import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)

  // Admin-only UI affordance: while true, isAdmin pretends to be false so
  // every v-if="auth.isAdmin" hides itself, letting an admin preview the
  // member experience (all data visible, only your own card editable)
  // without losing real backend permissions. Member is the going-forward
  // non-admin role; the legacy viewer role is retired in a later phase.
  const previewAsMember = ref(false)

  // Set when the last session check failed because the account is suspended,
  // so the guard can send the user to /login with a reason instead of the
  // generic "please log in" redirect.
  const suspended = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const actualRole = computed(() => user.value?.role ?? null)
  const isActuallyAdmin = computed(() => actualRole.value === 'admin')
  const isAdmin = computed(() => isActuallyAdmin.value && !previewAsMember.value)
  const isPreviewingAsMember = computed(
    () => isActuallyAdmin.value && previewAsMember.value,
  )

  // A member who hasn't completed their profile is gated out of the app
  // until they do — mirrors the backend require_completed_member gate.
  const needsProfile = computed(
    () => actualRole.value === 'member' && user.value?.has_profile === false,
  )

  // The id of this account's own member card, or null. Drives the
  // self-edit affordances on the Members page (edit / photo / resume of
  // exactly this card, even for non-admins).
  const myMemberId = computed(() => user.value?.member_id ?? null)

  async function login(password) {
    user.value = await authApi.login(password)
    previewAsMember.value = false
    suspended.value = false
  }

  async function logout() {
    await authApi.logout()
    user.value = null
    previewAsMember.value = false
    suspended.value = false
  }

  // Reset client-side auth state without touching the server. Used by the
  // axios 401 interceptor — the cookie is already invalid backend-side, so
  // calling /auth/logout would just produce another 401.
  function clearLocal() {
    user.value = null
    previewAsMember.value = false
    suspended.value = false
  }

  // Used by router guard on first navigation to restore session from cookie.
  // Swallows 401 because "no session" is not an error in that context.
  async function fetchMe() {
    try {
      user.value = await authApi.getMe()
      suspended.value = false
    } catch (err) {
      if (err?.response?.status === 401) {
        user.value = null
        suspended.value =
          err.response?.data?.detail === 'Account suspended'
        return
      }
      throw err
    }
  }

  function setPreviewAsMember(flag) {
    if (!isActuallyAdmin.value) return
    previewAsMember.value = !!flag
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
    previewAsMember,
    suspended,
    isAuthenticated,
    isAdmin,
    isActuallyAdmin,
    isPreviewingAsMember,
    needsProfile,
    myMemberId,
    actualRole,
    login,
    logout,
    clearLocal,
    fetchMe,
    setPreviewAsMember,
    updateUsername,
    updatePassword,
  }
})
