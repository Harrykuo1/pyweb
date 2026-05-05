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

import PhotoCropDialog from './PhotoCropDialog.vue'
import { authApi } from '../api/auth'
import { settingImageUrl, settingsApi } from '../api/settings'
import { useAuthStore } from '../stores/auth'

const LOGO_KEY = 'login_logo'
const LOGO_MAX_BYTES = 2 * 1024 * 1024
const LOGO_ALLOWED_TYPES = [
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/svg+xml',
]
// Cropping happens in a <canvas>, which can't rasterize SVG without losing
// the vector form. Skip the crop step for SVG and upload as-is.
const LOGO_CROPPABLE_TYPES = ['image/png', 'image/jpeg', 'image/webp']

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

// Logo tab state. cacheToken bumps on upload/delete so <img> reloads even
// when the URL is otherwise identical and the browser would have cached.
const logoCacheToken = ref(Date.now())
const logoExists = ref(false)
const logoFileInput = ref(null)
const pendingLogoFile = ref(null)
const pendingLogoPreviewUrl = ref('')
const logoUploading = ref(false)
const logoDeleting = ref(false)
const cropOpen = ref(false)
const cropSourceFile = ref(null)
const cropOutputType = ref('image/png')

const currentLogoUrl = computed(() =>
  logoExists.value ? settingImageUrl(LOGO_KEY, logoCacheToken.value) : '',
)

function probeLogo() {
  // The cheapest way to learn whether the asset exists is to try loading it
  // into a throwaway Image. Backend returns 404 when unset, which fires the
  // onerror handler.
  const img = new Image()
  img.onload = () => {
    logoExists.value = true
  }
  img.onerror = () => {
    logoExists.value = false
  }
  img.src = settingImageUrl(LOGO_KEY, logoCacheToken.value)
}

function clearPendingLogo() {
  if (pendingLogoPreviewUrl.value) {
    URL.revokeObjectURL(pendingLogoPreviewUrl.value)
  }
  pendingLogoFile.value = null
  pendingLogoPreviewUrl.value = ''
  if (logoFileInput.value) logoFileInput.value.value = ''
}

function setPendingLogo(file) {
  if (pendingLogoPreviewUrl.value) {
    URL.revokeObjectURL(pendingLogoPreviewUrl.value)
  }
  pendingLogoFile.value = file
  pendingLogoPreviewUrl.value = URL.createObjectURL(file)
}

function onLogoFileChange(event) {
  const file = event.target?.files?.[0] ?? null
  if (!file) {
    clearPendingLogo()
    return
  }
  if (!LOGO_ALLOWED_TYPES.includes(file.type)) {
    ElMessage.error('僅支援 PNG / JPEG / WebP / SVG')
    clearPendingLogo()
    return
  }
  if (file.size > LOGO_MAX_BYTES) {
    ElMessage.error('圖片不可超過 2 MB')
    clearPendingLogo()
    return
  }
  // Reset the file input so picking the same file again still re-triggers
  // change (browsers swallow it otherwise).
  if (logoFileInput.value) logoFileInput.value.value = ''

  if (LOGO_CROPPABLE_TYPES.includes(file.type)) {
    cropSourceFile.value = file
    // Match output type to input so we don't drop transparency on a PNG
    // upload by re-encoding it as JPEG.
    cropOutputType.value = file.type === 'image/jpeg' ? 'image/jpeg' : 'image/png'
    cropOpen.value = true
  } else {
    // SVG bypasses cropping; render directly as the pending preview.
    setPendingLogo(file)
  }
}

function onCropConfirmed(croppedFile) {
  setPendingLogo(croppedFile)
}

// Whether the user confirmed or just closed the crop dialog, drop the
// stashed source file so the next pick starts fresh.
watch(cropOpen, (open) => {
  if (!open) cropSourceFile.value = null
})

async function uploadLogo() {
  if (!pendingLogoFile.value) {
    ElMessage.warning('請先選擇圖片')
    return
  }
  logoUploading.value = true
  try {
    await settingsApi.uploadImage(LOGO_KEY, pendingLogoFile.value)
    logoCacheToken.value = Date.now()
    logoExists.value = true
    clearPendingLogo()
    ElMessage.success('登入頁 Logo 已更新')
  } catch (err) {
    const status = err?.response?.status
    if (status === 413) ElMessage.error('圖片過大')
    else if (status === 415) ElMessage.error('不支援的檔案格式')
    else ElMessage.error(extractError(err, '上傳失敗'))
  } finally {
    logoUploading.value = false
  }
}

async function deleteLogo() {
  logoDeleting.value = true
  try {
    await settingsApi.deleteImage(LOGO_KEY)
    logoExists.value = false
    logoCacheToken.value = Date.now()
    ElMessage.success('已恢復為預設圖示')
  } catch (err) {
    ElMessage.error(extractError(err, '刪除失敗'))
  } finally {
    logoDeleting.value = false
  }
}

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
      clearPendingLogo()
      logoCacheToken.value = Date.now()
      loadUsers()
      probeLogo()
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

      <el-tab-pane label="網站圖片" name="site">
        <div class="section-title">登入頁 Logo</div>
        <p class="hint">
          上傳後會取代登入頁原本的鎖頭圖示。選擇 PNG / JPEG / WebP 後可在彈出的對話框裁切成 1:1；SVG 會直接套用、不裁切。上限 2 MB。
        </p>

        <div class="logo-row">
          <div class="logo-current">
            <div class="logo-row-label">目前</div>
            <div class="logo-preview" data-test="logo-current-slot">
              <img
                v-if="logoExists"
                :src="currentLogoUrl"
                alt="login logo"
                data-test="logo-current-img"
              />
              <span v-else class="placeholder">尚未設定（預設鎖頭圖示）</span>
            </div>
          </div>

          <div class="logo-current">
            <div class="logo-row-label">即將上傳</div>
            <div class="logo-preview">
              <img
                v-if="pendingLogoPreviewUrl"
                :src="pendingLogoPreviewUrl"
                alt="pending logo"
                data-test="logo-pending-img"
              />
              <span v-else class="placeholder">尚未選擇檔案</span>
            </div>
          </div>
        </div>

        <input
          ref="logoFileInput"
          type="file"
          class="hidden-file"
          accept="image/png,image/jpeg,image/webp,image/svg+xml"
          data-test="logo-file-input"
          @change="onLogoFileChange"
        />

        <div class="form-actions logo-actions">
          <el-button
            data-test="logo-pick"
            @click="logoFileInput?.click()"
          >
            選擇圖片…
          </el-button>
          <el-button
            type="primary"
            :disabled="!pendingLogoFile"
            :loading="logoUploading"
            data-test="logo-upload"
            @click="uploadLogo"
          >
            上傳
          </el-button>
          <el-button
            v-if="logoExists"
            type="danger"
            :loading="logoDeleting"
            data-test="logo-delete"
            @click="deleteLogo"
          >
            恢復預設
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="visible = false">關閉</el-button>
    </template>

    <PhotoCropDialog
      v-model="cropOpen"
      :source-file="cropSourceFile"
      :output-type="cropOutputType"
      :output-size="512"
      output-filename="login-logo"
      title="裁切登入頁 Logo（1:1）"
      @cropped="onCropConfirmed"
    />
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
  flex-wrap: wrap;
  gap: 8px;
}

.input-wrap {
  width: 100%;
}

.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}

.logo-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.logo-current {
  flex: 1;
  min-width: 0;
}

.logo-row-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.logo-preview {
  height: 120px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #fafafa;
}

.logo-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.logo-preview .placeholder {
  font-size: 12px;
  color: #c0c4cc;
}

.hidden-file {
  display: none;
}

.logo-actions {
  gap: 8px;
}

@media (max-width: 640px) {
  /* Stack the current/pending logo previews vertically so they each get the
     full dialog width to render in. */
  .logo-row {
    flex-direction: column;
  }
}
</style>
