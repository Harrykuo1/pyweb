import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { settingImageUrl, settingsApi } from '../api/settings'

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

// The login-page logo flow: probe whether one is set, pick a file (with
// type/size validation), crop raster images (SVG bypasses), upload and
// delete. Lifted out of AppearanceSection so the component is presentation
// only and the flow is independently testable. Mirrors useMemberPhoto.
export function useLogoUpload() {
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
    // The cheapest way to learn whether the asset exists is to try loading
    // it into a throwaway Image. Backend returns 404 when unset, firing
    // onerror.
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
    // Reset the input so picking the same file again still re-triggers
    // change (browsers swallow it otherwise).
    if (logoFileInput.value) logoFileInput.value.value = ''

    if (LOGO_CROPPABLE_TYPES.includes(file.type)) {
      cropSourceFile.value = file
      // Match output type to input so we don't drop transparency on a PNG
      // upload by re-encoding it as JPEG.
      cropOutputType.value =
        file.type === 'image/jpeg' ? 'image/jpeg' : 'image/png'
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

  return {
    logoExists,
    logoFileInput,
    pendingLogoFile,
    pendingLogoPreviewUrl,
    logoUploading,
    logoDeleting,
    cropOpen,
    cropSourceFile,
    cropOutputType,
    currentLogoUrl,
    onLogoFileChange,
    onCropConfirmed,
    uploadLogo,
    deleteLogo,
    clearPendingLogo,
  }
}
