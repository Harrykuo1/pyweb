import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

// Role metadata drives both list grouping and the detail header. Adding a
// new role here is enough to slot it into the layout — the rest iterates
// over whatever roles the API returns.
const ROLE_META = {
  admin: {
    title: '管理員',
    subtitle: '系統管理權限',
    tagType: 'danger',
    accentClass: 'is-role-admin',
  },
  viewer: {
    title: '檢視者',
    subtitle: '唯讀使用者',
    tagType: 'info',
    accentClass: 'is-role-viewer',
  },
}

// Today the backend returns one admin + one viewer. The layout handles N
// rows per group so multi-viewer support drops in without UI changes.
const ROLE_ORDER = ['admin', 'viewer']

// All of the account-settings data and form logic, lifted out of
// AccountSection.vue so the component is presentation-only and the logic
// is independently testable. Owns the account list + search + selection,
// and the per-role username / password edit forms with their submit flows.
export function useAccounts() {
  const auth = useAuthStore()

  const loadingUsers = ref(false)
  const accounts = ref([])
  const search = ref('')

  const selectedKey = ref(null)
  const selected = computed(
    () => accounts.value.find((a) => a.key === selectedKey.value) ?? null,
  )
  const selectedRole = computed(() => selected.value?.role ?? 'admin')
  const selectedMeta = computed(() => ROLE_META[selectedRole.value])

  // Per-role form state. Today the backend updates by role; once viewer
  // accounts go multi-record, switch the keying here to account id.
  const usernameForm = reactive({ admin: '', viewer: '' })
  const passwordForm = reactive({
    admin: { current_password: '', new_password: '', confirm: '' },
    viewer: { current_password: '', new_password: '', confirm: '' },
  })
  const usernameSubmitting = reactive({ admin: false, viewer: false })
  const passwordSubmitting = reactive({ admin: false, viewer: false })

  const usersByRole = computed(() => {
    const m = {}
    for (const a of accounts.value) m[a.role] = a
    return m
  })

  const filteredGroups = computed(() => {
    const q = search.value.trim().toLowerCase()
    const out = []
    for (const role of ROLE_ORDER) {
      const inRole = accounts.value.filter((a) => a.role === role)
      const matched = q
        ? inRole.filter((a) => a.username.toLowerCase().includes(q))
        : inRole
      if (matched.length || !q) {
        // Keep empty groups visible when search is blank so the layout
        // signals "multi-role support" even with one account per role.
        out.push({ role, accounts: matched, meta: ROLE_META[role] })
      }
    }
    return out
  })

  const totalCount = computed(() => accounts.value.length)
  const visibleCount = computed(() =>
    filteredGroups.value.reduce((n, g) => n + g.accounts.length, 0),
  )

  function extractError(err, fallback) {
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string') return detail
    return fallback
  }

  async function loadUsers() {
    loadingUsers.value = true
    try {
      const list = await authApi.listUsers()
      // Key by id so two accounts in the same role highlight independently.
      // Form state is still keyed by role because the backend update
      // endpoints route by role today — a known limitation when multiple
      // accounts share a role.
      accounts.value = list.map((u) => ({ ...u, key: String(u.id) }))
      for (const a of accounts.value) {
        usernameForm[a.role] = a.username
      }
      if (!selectedKey.value && accounts.value.length) {
        selectedKey.value = accounts.value[0].key
      }
    } catch (err) {
      ElMessage.error('載入帳號資訊失敗')
    } finally {
      loadingUsers.value = false
    }
  }

  function select(key) {
    selectedKey.value = key
  }

  function patchAccount(role, updated) {
    const idx = accounts.value.findIndex((a) => a.role === role)
    if (idx >= 0) {
      accounts.value[idx] = { ...accounts.value[idx], ...updated }
    }
  }

  async function submitUsername(role) {
    const next = usernameForm[role].trim()
    if (!next) {
      ElMessage.warning('使用者名稱不可為空')
      return
    }
    if (next === usersByRole.value[role]?.username) {
      ElMessage.info('名稱沒有變更')
      return
    }

    usernameSubmitting[role] = true
    try {
      const updated = await auth.updateUsername(role, next)
      patchAccount(role, updated)
      usernameForm[role] = updated.username
      ElMessage.success('使用者名稱已更新')
    } catch (err) {
      if (err?.response?.status === 409) {
        ElMessage.error('該名稱已被另一個帳號使用')
      } else {
        ElMessage.error(extractError(err, '更新失敗，請稍後再試'))
      }
    } finally {
      usernameSubmitting[role] = false
    }
  }

  async function submitPassword(role) {
    const f = passwordForm[role]
    if (!f.current_password || !f.new_password) {
      ElMessage.warning('請完整填寫密碼欄位')
      return
    }
    if (f.new_password !== f.confirm) {
      ElMessage.error('兩次輸入的新密碼不一致')
      return
    }

    passwordSubmitting[role] = true
    try {
      await auth.updatePassword(role, f.current_password, f.new_password)
      passwordForm[role] = { current_password: '', new_password: '', confirm: '' }
      ElMessage.success('密碼已更新')
    } catch (err) {
      const status = err?.response?.status
      // Backend returns 422 when the typed-in current password doesn't
      // verify — see _require_admin_password / update_password rationale.
      if (status === 422) {
        ElMessage.error('目前管理員密碼不正確')
      } else if (status === 409) {
        ElMessage.error('新密碼與另一個帳號相同，請改用其他密碼')
      } else {
        ElMessage.error(extractError(err, '更新失敗，請稍後再試'))
      }
    } finally {
      passwordSubmitting[role] = false
    }
  }

  function initial(name) {
    return (name || '?').charAt(0).toUpperCase()
  }

  onMounted(loadUsers)

  return {
    loadingUsers,
    accounts,
    search,
    selected,
    selectedRole,
    selectedMeta,
    filteredGroups,
    totalCount,
    visibleCount,
    usernameForm,
    passwordForm,
    usernameSubmitting,
    passwordSubmitting,
    select,
    submitUsername,
    submitPassword,
    initial,
  }
}
