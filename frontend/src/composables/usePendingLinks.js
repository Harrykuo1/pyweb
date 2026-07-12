import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { authApi } from '../api/auth'
import { membersApi } from '../api/members'
import { extractError } from '../utils/apiError'

// Admin panel for Discord logins that matched no pre-created account. Each
// pending link is resolved by binding the Discord identity to an existing
// member (one whose user has no discord_id yet). Logic lives here so
// PendingLinksSection.vue stays presentation-only.
export function usePendingLinks() {
  const loading = ref(false)
  const links = ref([])
  const members = ref([])
  const resolvingId = ref(null)
  // discord_id -> chosen member id, driven by each row's el-select.
  const picked = reactive({})

  // Only unclaimed members are valid resolve targets — the backend returns 409
  // for members whose account is already claimed/suspended, so keep them out of
  // the dropdown instead of surfacing the error after selection.
  const selectableMembers = computed(() =>
    members.value.filter((m) => m.account_status === 'pending'),
  )

  async function load() {
    loading.value = true
    try {
      const [pending, memberList] = await Promise.all([
        authApi.listPendingLinks(),
        membersApi.list(),
      ])
      links.value = pending
      members.value = memberList
    } catch (err) {
      ElMessage.error('載入待處理連結失敗')
    } finally {
      loading.value = false
    }
  }

  function displayName(link) {
    return link.discord_global_name || link.discord_username || link.discord_id
  }

  function memberLabel(m) {
    return `${m.real_name}（${m.graduation_year}）`
  }

  async function resolve(link) {
    const memberId = picked[link.discord_id]
    if (!memberId) {
      ElMessage.warning('請先選擇要連結的成員')
      return
    }
    resolvingId.value = link.discord_id
    try {
      await authApi.resolvePendingLink(link.discord_id, memberId)
      links.value = links.value.filter((l) => l.discord_id !== link.discord_id)
      ElMessage.success('已完成連結')
    } catch (err) {
      // Backend returns 409 "Member already linked" / 404 — surface the detail.
      ElMessage.error(extractError(err, '連結失敗，請稍後再試'))
    } finally {
      resolvingId.value = null
    }
  }

  async function dismiss(link) {
    try {
      await ElMessageBox.confirm(
        `確定要忽略「${displayName(link)}」的連結請求嗎？對方重新登入後會再次出現。`,
        '忽略連結請求',
        {
          type: 'warning',
          confirmButtonText: '忽略',
          cancelButtonText: '取消',
        },
      )
    } catch {
      return // user cancelled
    }
    resolvingId.value = link.discord_id
    try {
      await authApi.deletePendingLink(link.discord_id)
      links.value = links.value.filter((l) => l.discord_id !== link.discord_id)
      ElMessage.success('已忽略')
    } catch (err) {
      ElMessage.error(extractError(err, '操作失敗，請稍後再試'))
    } finally {
      resolvingId.value = null
    }
  }

  onMounted(load)

  return {
    loading,
    links,
    members,
    selectableMembers,
    picked,
    resolvingId,
    displayName,
    memberLabel,
    load,
    resolve,
    dismiss,
  }
}
