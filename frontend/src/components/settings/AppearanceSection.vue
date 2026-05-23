<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElButton, ElMessage } from 'element-plus'

import PhotoCropDialog from '../PhotoCropDialog.vue'
import { settingImageUrl, settingsApi } from '../../api/settings'

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

function extractError(err, fallback) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

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

onMounted(() => {
  clearPendingLogo()
  logoCacheToken.value = Date.now()
  probeLogo()
})

defineExpose({
  cropOpen,
  cropSourceFile,
  cropOutputType,
  pendingLogoFile,
  onCropConfirmed,
  uploadLogo,
})
</script>

<template>
  <div class="appearance-section">
    <div class="appearance-block">
      <header class="appearance-block__header">
        <h3>登入頁 Logo</h3>
        <p class="appearance-block__hint">
          上傳後會取代登入頁原本的鎖頭圖示。PNG / JPEG / WebP 可在彈出對話框裁切成 1:1；SVG 直接套用、不裁切。上限 2 MB。
        </p>
      </header>

      <div class="logo-row">
        <div class="logo-card">
          <div class="logo-card__label">目前</div>
          <div class="logo-card__preview" data-test="logo-current-slot">
            <img
              v-if="logoExists"
              :src="currentLogoUrl"
              alt="login logo"
              data-test="logo-current-img"
            />
            <span v-else class="logo-card__placeholder">
              尚未設定（預設鎖頭圖示）
            </span>
          </div>
        </div>

        <div class="logo-card">
          <div class="logo-card__label">即將上傳</div>
          <div class="logo-card__preview">
            <img
              v-if="pendingLogoPreviewUrl"
              :src="pendingLogoPreviewUrl"
              alt="pending logo"
              data-test="logo-pending-img"
            />
            <span v-else class="logo-card__placeholder">
              尚未選擇檔案
            </span>
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

      <div class="logo-actions">
        <el-button data-test="logo-pick" @click="logoFileInput?.click()">
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
    </div>

    <PhotoCropDialog
      v-model="cropOpen"
      :source-file="cropSourceFile"
      :output-type="cropOutputType"
      :output-size="512"
      output-filename="login-logo"
      title="裁切登入頁 Logo（1:1）"
      @cropped="onCropConfirmed"
    />
  </div>
</template>

<style scoped>
.appearance-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.appearance-block {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 22px 24px;
  box-shadow: var(--shadow-sm);
}

.appearance-block__header {
  margin: 0 0 18px;
}

.appearance-block__header h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}

.appearance-block__hint {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.55;
}

.logo-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}

.logo-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.logo-card__label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink-500);
  display: flex;
  align-items: center;
  gap: 6px;
}

.logo-card__label::before {
  content: '';
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--brand-primary);
}

.logo-card__preview {
  height: 160px;
  border: 1px dashed rgba(15, 23, 42, 0.14);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.04),
    rgba(139, 92, 246, 0.02)
  );
  transition: border-color var(--dur) var(--ease);
}

.logo-card__preview:hover {
  border-color: rgba(99, 102, 241, 0.3);
}

.logo-card__preview img {
  max-width: 80%;
  max-height: 80%;
  object-fit: contain;
}

.logo-card__placeholder {
  font-size: 12px;
  color: var(--ink-300);
  text-align: center;
  padding: 0 12px;
}

.hidden-file {
  display: none;
}

.logo-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px dashed rgba(15, 23, 42, 0.06);
}

/* Element Plus injects margin-left:12px on sibling buttons by default.
   When the row uses flex `gap`, both apply and spacing doubles —
   neutralize the margin so gap alone owns the rhythm. */
.logo-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

@media (max-width: 640px) {
  .logo-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
