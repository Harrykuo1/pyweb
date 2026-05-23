<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElSkeleton,
  ElTag,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'

import { authApi } from '../../api/auth'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()

// Role metadata drives both list grouping and the detail header. Adding
// a new role here is enough to slot it into the layout — the rest of
// the section iterates over whatever roles the API returns.
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

// Today the backend returns one admin + one viewer. The layout is built
// to handle N rows per group so multi-viewer support drops in without
// further UI changes.
const ROLE_ORDER = ['admin', 'viewer']

const loadingUsers = ref(false)
const accounts = ref([])
const search = ref('')

const selectedKey = ref(null)
const selected = computed(
  () =>
    accounts.value.find((a) => a.key === selectedKey.value) ??
    accounts.value[0] ??
    null,
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
    // The form state is still keyed by role because the backend update
    // endpoints route by role today — that's a known limitation when
    // multiple accounts share a role, see /settings notes.
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
    // verify — see _require_admin_password / update_password rationale
    // for why it's not 401 here.
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

defineExpose({ accounts, usernameForm, passwordForm })
</script>

<template>
  <div class="account-section">
    <header class="account-toolbar">
      <div class="account-toolbar__search">
        <el-input
          v-model="search"
          placeholder="搜尋帳號名稱…"
          :prefix-icon="Search"
          clearable
          data-test="account-search"
        />
      </div>
      <div class="account-toolbar__stat">
        <span class="account-toolbar__total" data-test="account-total">
          {{ totalCount }}
        </span>
        <span class="account-toolbar__label">個帳號</span>
        <span
          v-if="search && visibleCount !== totalCount"
          class="account-toolbar__filtered"
        >
          · 顯示 {{ visibleCount }}
        </span>
      </div>
    </header>

    <div class="account-layout">
      <aside class="account-list" aria-label="帳號清單">
        <div
          v-for="group in filteredGroups"
          :key="group.role"
          class="account-group"
          :class="group.meta.accentClass"
        >
          <header class="account-group__header">
            <span class="account-group__title">{{ group.meta.title }}</span>
            <span class="account-group__count">
              {{ group.accounts.length }}
            </span>
          </header>
          <button
            v-for="acct in group.accounts"
            :key="acct.key"
            type="button"
            class="account-row"
            :class="[
              group.meta.accentClass,
              { 'is-active': acct.key === selected?.key },
            ]"
            :data-test="`account-row-${acct.key}`"
            @click="select(acct.key)"
          >
            <span class="account-row__avatar">
              {{ initial(acct.username) }}
            </span>
            <span class="account-row__meta">
              <span class="account-row__name">{{ acct.username }}</span>
              <span class="account-row__role">{{ group.meta.subtitle }}</span>
            </span>
          </button>
          <div
            v-if="!group.accounts.length"
            class="account-group__empty"
          >
            尚無此角色的帳號
          </div>
        </div>

        <div
          v-if="search && !visibleCount"
          class="account-list__empty"
          data-test="account-empty"
        >
          找不到符合「{{ search }}」的帳號
        </div>
      </aside>

      <div class="account-detail">
        <el-skeleton v-if="loadingUsers && !selected" :rows="6" animated />

        <template v-else-if="selected">
          <header
            class="account-profile"
            :class="selectedMeta.accentClass"
            :data-test="`account-profile-${selectedRole}`"
          >
            <span class="account-profile__avatar">
              {{ initial(selected.username) }}
            </span>
            <div class="account-profile__body">
              <div class="account-profile__name-row">
                <h3 class="account-profile__name">{{ selected.username }}</h3>
                <el-tag
                  :type="selectedMeta.tagType"
                  size="small"
                  effect="light"
                  round
                >
                  {{ selectedMeta.title }}
                </el-tag>
              </div>
              <p class="account-profile__sub">{{ selectedMeta.subtitle }}</p>
            </div>
          </header>

          <article class="account-card">
            <header class="account-card__header">
              <h4>使用者名稱</h4>
              <p>變更後其他人會立即看到新的名稱。</p>
            </header>
            <el-form
              class="account-card__form"
              @submit.prevent="submitUsername(selectedRole)"
            >
              <el-form-item>
                <div
                  :data-test="`username-input-${selectedRole}`"
                  class="account-card__field"
                >
                  <el-input
                    v-model="usernameForm[selectedRole]"
                    :placeholder="selected.username"
                    :disabled="loadingUsers"
                    maxlength="64"
                    show-word-limit
                  />
                </div>
              </el-form-item>
              <div class="account-card__actions">
                <el-button
                  type="primary"
                  :loading="usernameSubmitting[selectedRole]"
                  :disabled="loadingUsers"
                  :data-test="`username-submit-${selectedRole}`"
                  @click="submitUsername(selectedRole)"
                >
                  更新名稱
                </el-button>
              </div>
            </el-form>
          </article>

          <article class="account-card">
            <header class="account-card__header">
              <h4>變更密碼</h4>
              <p>更新後需以新密碼重新登入。</p>
            </header>
            <el-form
              class="account-card__form"
              label-position="top"
              @submit.prevent="submitPassword(selectedRole)"
            >
              <div class="account-card__grid">
                <el-form-item label="目前管理員密碼">
                  <div
                    :data-test="`password-current-${selectedRole}`"
                    class="account-card__field"
                  >
                    <el-input
                      v-model="passwordForm[selectedRole].current_password"
                      type="password"
                      show-password
                      autocomplete="current-password"
                    />
                  </div>
                </el-form-item>
                <el-form-item label="新密碼">
                  <div
                    :data-test="`password-new-${selectedRole}`"
                    class="account-card__field"
                  >
                    <el-input
                      v-model="passwordForm[selectedRole].new_password"
                      type="password"
                      show-password
                      autocomplete="new-password"
                    />
                  </div>
                </el-form-item>
                <el-form-item label="確認新密碼">
                  <div
                    :data-test="`password-confirm-${selectedRole}`"
                    class="account-card__field"
                  >
                    <el-input
                      v-model="passwordForm[selectedRole].confirm"
                      type="password"
                      show-password
                      autocomplete="new-password"
                    />
                  </div>
                </el-form-item>
              </div>
              <div class="account-card__actions">
                <el-button
                  type="primary"
                  :loading="passwordSubmitting[selectedRole]"
                  :data-test="`password-submit-${selectedRole}`"
                  @click="submitPassword(selectedRole)"
                >
                  更新密碼
                </el-button>
              </div>
            </el-form>
          </article>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.account-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ---------- Toolbar ---------- */
.account-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.account-toolbar__search {
  flex: 1;
  min-width: 200px;
  max-width: 320px;
}

.account-toolbar__stat {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-500);
  margin-left: auto;
}

.account-toolbar__total {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink-900);
}

.account-toolbar__filtered {
  color: var(--brand-primary);
}

/* ---------- Layout ---------- */
.account-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

/* ---------- List ---------- */
.account-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 12px;
  background: var(--surface-1);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
}

.account-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.account-group__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-500);
}

.account-group__title {
  position: relative;
  padding-left: 10px;
}

.account-group__title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}

.account-group.is-role-admin .account-group__title {
  color: var(--brand-primary);
}

.account-group.is-role-viewer .account-group__title {
  color: var(--accent-career-ink);
}

.account-group__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  font-size: 10px;
  font-weight: 700;
  color: var(--ink-500);
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 999px;
}

.account-group__empty {
  padding: 8px 10px;
  font-size: 12px;
  color: var(--ink-300);
  font-style: italic;
}

.account-row {
  appearance: none;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-md);
  font: inherit;
  color: var(--ink-700);
  transition: border-color var(--dur) var(--ease),
    background-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.account-row:hover {
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.account-row.is-active {
  border-color: rgba(99, 102, 241, 0.45);
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.1),
    rgba(139, 92, 246, 0.06)
  );
  box-shadow: var(--shadow-sm);
}

.account-row.is-role-viewer.is-active {
  border-color: rgba(16, 185, 129, 0.45);
  background: linear-gradient(
    135deg,
    rgba(16, 185, 129, 0.1),
    rgba(6, 182, 212, 0.06)
  );
}

.account-row__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  flex: 0 0 auto;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.28);
}

.account-row.is-role-viewer .account-row__avatar {
  background: linear-gradient(
    135deg,
    var(--accent-career-from),
    var(--accent-career-to)
  );
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.25);
}

.account-row__meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.account-row__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-row__role {
  font-size: 11px;
  color: var(--ink-500);
  margin-top: 2px;
}

.account-list__empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--ink-500);
  background: var(--surface-0);
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: var(--radius-md);
}

/* ---------- Detail pane ---------- */
.account-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Profile header — sets the role accent for the rest of the detail
   pane through a subtle gradient backdrop + matching avatar. */
.account-profile {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  border-radius: var(--radius-lg);
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12),
    rgba(139, 92, 246, 0.06)
  );
  border: 1px solid rgba(99, 102, 241, 0.18);
  position: relative;
  overflow: hidden;
}

.account-profile.is-role-viewer {
  background: linear-gradient(
    135deg,
    rgba(16, 185, 129, 0.12),
    rgba(6, 182, 212, 0.06)
  );
  border-color: rgba(16, 185, 129, 0.22);
}

.account-profile::after {
  content: '';
  position: absolute;
  right: -40px;
  top: -40px;
  width: 140px;
  height: 140px;
  background: radial-gradient(
    circle at center,
    rgba(255, 255, 255, 0.5),
    rgba(255, 255, 255, 0) 70%
  );
  pointer-events: none;
}

.account-profile__avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #ffffff;
  flex: 0 0 auto;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.32);
  position: relative;
  z-index: 1;
}

.account-profile.is-role-viewer .account-profile__avatar {
  background: linear-gradient(
    135deg,
    var(--accent-career-from),
    var(--accent-career-to)
  );
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.28);
}

.account-profile__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  position: relative;
  z-index: 1;
}

.account-profile__name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.account-profile__name {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: -0.01em;
}

.account-profile__sub {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
}

/* ---------- Card (one per editable surface) ---------- */
.account-card {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
}

.account-card__header {
  margin: 0 0 16px;
}

.account-card__header h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}

.account-card__header p {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
}

.account-card__form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.account-card__form :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.account-card__field {
  width: 100%;
}

.account-card__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}

.account-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

/* Element Plus injects margin-left:12px on sibling buttons by default.
   When the row uses flex `gap`, both apply and spacing doubles —
   neutralize the margin so gap alone owns the rhythm. */
.account-card__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

@media (max-width: 720px) {
  .account-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .account-list {
    flex-direction: column;
  }

  .account-toolbar__stat {
    margin-left: 0;
  }
}
</style>
