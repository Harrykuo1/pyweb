import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

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
      try {
        await writeClipboard(inviteUrl(inv))
        ElMessage.success('已產生邀請連結，並已複製到剪貼簿')
      } catch (err) {
        // Creation still succeeded even if the clipboard write didn't.
        ElMessage.success('已產生邀請連結')
      }
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

  // navigator.clipboard only exists in a secure context (https or
  // localhost). When the site is reached over plain http on a LAN IP it is
  // undefined, so fall back to a transient off-screen textarea + execCommand
  // which works everywhere. Throws if neither path copies.
  async function writeClipboard(text) {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text)
        return
      } catch (err) {
        // API present but blocked — fall through to the legacy path.
      }
    }
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.top = '-9999px'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    try {
      if (!document.execCommand('copy'))
        throw new Error('copy command rejected')
    } finally {
      document.body.removeChild(ta)
    }
  }

  async function copy(inv) {
    try {
      await writeClipboard(inviteUrl(inv))
      ElMessage.success('已複製連結')
    } catch (err) {
      ElMessage.error('複製失敗')
    }
  }

  async function remove(inv) {
    try {
      await ElMessageBox.confirm(
        '確定要刪除這個邀請連結嗎？已分享出去的連結將立即失效。',
        '刪除邀請連結',
        {
          type: 'warning',
          confirmButtonText: '刪除',
          cancelButtonText: '取消',
        },
      )
    } catch {
      return // user cancelled
    }
    try {
      await authApi.deleteRegistrationInvite(inv.id)
      invites.value = invites.value.filter((i) => i.id !== inv.id)
      ElMessage.success('已刪除邀請連結')
    } catch (err) {
      ElMessage.error('刪除失敗，請稍後再試')
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
    remove,
  }
}
