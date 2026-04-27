<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElTabPane,
  ElTabs,
} from 'element-plus'

import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
})
const emit = defineEmits(['update:modelValue'])

const auth = useAuthStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const activeTab = ref('admin')
const loadingUsers = ref(false)
const users = ref({ admin: null, viewer: null })

const usernameForm = reactive({ admin: '', viewer: '' })
const passwordForm = reactive({
  admin: { current_password: '', new_password: '', confirm: '' },
  viewer: { current_password: '', new_password: '', confirm: '' },
})

const usernameSubmitting = reactive({ admin: false, viewer: false })
const passwordSubmitting = reactive({ admin: false, viewer: false })

async function loadUsers() {
  loadingUsers.value = true
  try {
    const list = await authApi.listUsers()
    const admin = list.find((u) => u.role === 'admin') ?? null
    const viewer = list.find((u) => u.role === 'viewer') ?? null
    users.value = { admin, viewer }
    usernameForm.admin = admin?.username ?? ''
    usernameForm.viewer = viewer?.username ?? ''
  } catch (err) {
    ElMessage.error('載入帳號資訊失敗')
  } finally {
    loadingUsers.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      activeTab.value = 'admin'
      passwordForm.admin = { current_password: '', new_password: '', confirm: '' }
      passwordForm.viewer = { current_password: '', new_password: '', confirm: '' }
      loadUsers()
    }
  },
  { immediate: true },
)

function extractError(err, fallback) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

async function submitUsername(role) {
  const next = usernameForm[role].trim()
  if (!next) {
    ElMessage.warning('使用者名稱不可為空')
    return
  }
  if (next === users.value[role]?.username) {
    ElMessage.info('名稱沒有變更')
    return
  }

  usernameSubmitting[role] = true
  try {
    const updated = await auth.updateUsername(role, next)
    users.value[role] = updated
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
    if (status === 401) {
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
</script>

<template>
  <el-dialog
    v-model="visible"
    title="帳號設定"
    width="520px"
    append-to-body
    destroy-on-close
  >
    <el-tabs v-model="activeTab">
      <el-tab-pane
        v-for="role in ['admin', 'viewer']"
        :key="role"
        :label="role === 'admin' ? '管理員帳號' : '檢視者帳號'"
        :name="role"
      >
        <div class="section-title">使用者名稱</div>
        <el-form
          label-position="top"
          @submit.prevent="submitUsername(role)"
        >
          <el-form-item label="名稱">
            <div :data-test="`username-input-${role}`" class="input-wrap">
              <el-input
                v-model="usernameForm[role]"
                :placeholder="users[role]?.username ?? ''"
                :disabled="loadingUsers"
                maxlength="64"
                show-word-limit
              />
            </div>
          </el-form-item>
          <div class="form-actions">
            <el-button
              type="primary"
              :loading="usernameSubmitting[role]"
              :disabled="loadingUsers"
              :data-test="`username-submit-${role}`"
              @click="submitUsername(role)"
            >
              更新名稱
            </el-button>
          </div>
        </el-form>

        <div class="section-divider" />

        <div class="section-title">變更密碼</div>
        <el-form
          label-position="top"
          @submit.prevent="submitPassword(role)"
        >
          <el-form-item label="目前管理員密碼">
            <div :data-test="`password-current-${role}`" class="input-wrap">
              <el-input
                v-model="passwordForm[role].current_password"
                type="password"
                show-password
                autocomplete="current-password"
              />
            </div>
          </el-form-item>
          <el-form-item label="新密碼">
            <div :data-test="`password-new-${role}`" class="input-wrap">
              <el-input
                v-model="passwordForm[role].new_password"
                type="password"
                show-password
                autocomplete="new-password"
              />
            </div>
          </el-form-item>
          <el-form-item label="確認新密碼">
            <div :data-test="`password-confirm-${role}`" class="input-wrap">
              <el-input
                v-model="passwordForm[role].confirm"
                type="password"
                show-password
                autocomplete="new-password"
              />
            </div>
          </el-form-item>
          <div class="form-actions">
            <el-button
              type="primary"
              :loading="passwordSubmitting[role]"
              :data-test="`password-submit-${role}`"
              @click="submitPassword(role)"
            >
              更新密碼
            </el-button>
          </div>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="visible = false">關閉</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 4px 0 12px;
}

.section-divider {
  height: 1px;
  background: #ebeef5;
  margin: 16px 0 20px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.input-wrap {
  width: 100%;
}
</style>
