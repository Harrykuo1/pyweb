import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { authApi } from '../api/auth'
import { extractError } from '../utils/apiError'

// Admin-only user role management. Loads every account and lets an admin
// promote/demote between admin and member. Lifted out of UserRolesSection
// so the component stays presentation-only and this logic is testable.
export function useUserRoles() {
  const loading = ref(false)
  const users = ref([])
  const savingId = ref(null)

  async function load() {
    loading.value = true
    try {
      users.value = await authApi.listUsers()
    } catch (err) {
      ElMessage.error('載入使用者失敗')
    } finally {
      loading.value = false
    }
  }

  // Prefer the linked member's real name (backfilled accounts have no handle
  // yet), then the Discord display name / handle, then the seeded username,
  // and finally the id so a row is never blank.
  function displayName(u) {
    return (
      u.member_name ||
      u.discord_global_name ||
      u.discord_username ||
      u.username ||
      `#${u.id}`
    )
  }

  async function changeRole(user, role) {
    if (role === user.role) return

    savingId.value = user.id
    try {
      const updated = await authApi.assignRole(user.id, role)
      // Non-mutating swap so the shared list reference isn't touched — the
      // row re-renders from the server's canonical UserResponse.
      users.value = users.value.map((u) => (u.id === updated.id ? updated : u))
      ElMessage.success('已更新角色')
    } catch (err) {
      // Backend answers 409 "Cannot demote the last admin"; extractError
      // surfaces that detail so the toast explains why it was rejected.
      ElMessage.error(extractError(err, '更新角色失敗'))
    } finally {
      savingId.value = null
    }
  }

  onMounted(load)

  return { loading, users, savingId, displayName, load, changeRole }
}
