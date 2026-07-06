import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { authApi } from '../api/auth'

// Admin registration-invite panel logic, lifted out of InvitesSection.vue so
// the component stays presentation-only and this stays independently testable.
// An invite is a one-time link an admin shares; the new member clicks it to
// start Discord OAuth registration. Shape:
//   { id, token, created_at, expires_at, used_at|null, used_by_user_id|null }
export function useRegistrationInvites() {
  const loading = ref(false)
  const invites = ref([])
  const creating = ref(false)

  async function load() {
    loading.value = true
    try {
      invites.value = await authApi.listRegistrationInvites()
    } catch (err) {
      ElMessage.error('載入邀請連結失敗')
    } finally {
      loading.value = false
    }
  }

  async function create() {
    creating.value = true
    try {
      const inv = await authApi.createRegistrationInvite()
      invites.value = [inv, ...invites.value]
      ElMessage.success('已產生邀請連結')
    } catch (err) {
      ElMessage.error('產生失敗，請稍後再試')
    } finally {
      creating.value = false
    }
  }

  function inviteUrl(inv) {
    return `${window.location.origin}/api/auth/discord/register?token=${inv.token}`
  }

  // 'used' once redeemed, else 'expired' past the TTL, else 'active'. Only
  // 'active' invites are worth copying — the section disables the rest.
  function status(inv) {
    if (inv.used_at) return 'used'
    if (new Date(inv.expires_at) < new Date()) return 'expired'
    return 'active'
  }

  function statusLabel(inv) {
    const s = status(inv)
    if (s === 'used') return '已使用'
    if (s === 'expired') return '已過期'
    return '可使用'
  }

  async function copy(inv) {
    if (!navigator.clipboard) {
      ElMessage.error('瀏覽器不支援複製')
      return
    }
    try {
      await navigator.clipboard.writeText(inviteUrl(inv))
      ElMessage.success('已複製連結')
    } catch (err) {
      ElMessage.error('複製失敗')
    }
  }

  onMounted(load)

  return {
    loading,
    invites,
    creating,
    load,
    create,
    inviteUrl,
    status,
    statusLabel,
    copy,
  }
}
