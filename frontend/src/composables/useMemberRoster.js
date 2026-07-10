import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { authApi } from '../api/auth'
import { membersApi } from '../api/members'
import { extractError } from '../utils/apiError'

// Members-first roster: every member profile joined with its linked account's
// role. Pending / suspended / legacy states already live on the member row
// (account_status, is_active, account_discord_username); the accounts list
// only contributes `role`, keyed by member.account_id -> user.id.
export function useMemberRoster() {
  const loading = ref(false)
  const rows = ref([])
  const savingId = ref(null)
  const statusFilter = ref('all')

  async function load() {
    loading.value = true
    try {
      const [members, users] = await Promise.all([
        membersApi.list(),
        authApi.listUsers(),
      ])
      const roleByAccountId = Object.fromEntries(
        users.map((u) => [u.id, u.role]),
      )
      rows.value = members.map((m) => ({
        ...m,
        role:
          m.account_id != null ? (roleByAccountId[m.account_id] ?? null) : null,
      }))
    } catch (err) {
      ElMessage.error('載入成員名冊失敗')
    } finally {
      loading.value = false
    }
  }

  const reload = load

  const counts = computed(() => {
    const c = { all: rows.value.length, claimed: 0, pending: 0, suspended: 0 }
    for (const r of rows.value) {
      if (r.account_status === 'claimed') c.claimed += 1
      else if (r.account_status === 'pending') c.pending += 1
      else if (r.account_status === 'suspended') c.suspended += 1
    }
    return c
  })

  const filteredRows = computed(() => {
    if (statusFilter.value === 'all') return rows.value
    return rows.value.filter((r) => r.account_status === statusFilter.value)
  })

  // Members always have a real name, but fall back so a row is never blank.
  function displayName(member) {
    return (
      member.real_name || member.account_discord_username || `#${member.id}`
    )
  }

  async function changeRole(member, role) {
    if (role === member.role) return

    savingId.value = member.account_id
    try {
      await authApi.assignRole(member.account_id, role)
      rows.value = rows.value.map((r) =>
        r.id === member.id ? { ...r, role } : r,
      )
      ElMessage.success('已更新角色')
    } catch (err) {
      // Backend answers 409 "Cannot demote the last admin"; surface the detail.
      ElMessage.error(extractError(err, '更新角色失敗'))
    } finally {
      savingId.value = null
    }
  }

  async function setActive(member, isActive) {
    savingId.value = member.account_id
    try {
      await authApi.setUserActive(member.account_id, isActive)
      // account_status is recomputed server-side (claimed <-> suspended), so
      // reload rather than patch a single field.
      await reload()
      ElMessage.success(isActive ? '已復權' : '已停權')
    } catch (err) {
      // Backend answers 409 when suspending an admin; surface the detail.
      ElMessage.error(extractError(err, isActive ? '復權失敗' : '停權失敗'))
    } finally {
      savingId.value = null
    }
  }

  onMounted(load)

  return {
    loading,
    rows,
    statusFilter,
    filteredRows,
    counts,
    savingId,
    load,
    reload,
    changeRole,
    setActive,
    displayName,
  }
}
