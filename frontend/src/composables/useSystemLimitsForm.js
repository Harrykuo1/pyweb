import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { settingsApi } from '../api/settings'

// Field metadata that's not in the API response (labels, help text) lives
// here so the backend stays free of locale strings. Unknown keys fall back
// to the raw key — a setting added on the backend before the frontend
// ships still renders, just without polish.
const FIELD_COPY = {
  max_attachments_per_job: {
    label: '單筆求職紀錄附件數上限',
    description: '每筆求職紀錄最多可掛上的附件總數。',
    unit: '個附件',
  },
  max_attachment_mb: {
    label: '附件單檔大小上限',
    description: '每個附件檔案的最大上傳大小。',
    unit: 'MB',
  },
  max_photos_per_event: {
    label: '單場活動照片數上限',
    description: '每場活動最多可上傳的照片張數。',
    unit: '張照片',
  },
  max_photo_mb: {
    label: '照片單檔大小上限',
    description:
      '每張照片的最大上傳大小。手機高像素模式拍出的照片可能超過 10 MB。',
    unit: 'MB',
  },
  max_videos_per_event: {
    label: '單場活動影片數上限',
    description: '每場活動最多可上傳的影片支數。',
    unit: '支影片',
  },
  max_video_mb: {
    label: '影片單檔大小上限',
    description:
      '每支影片的最大上傳大小，約等於 4K 一分鐘或 1080p 四分鐘。上限卡在 nginx 的 client_max_body_size，調更高會在代理層就被擋掉。',
    unit: 'MB',
  },
}

// The system-limits config form: load the server values, edit, save (with
// dirty tracking + reset). formVersion is bumped on every refresh so the
// el-input-number :key changes and Vue rebuilds each input — otherwise a
// server-side clamp (typed 999, clamped to 50) leaves the spinner's
// internal currentValue stale because the v-model prop didn't change.
// Lifted out of SystemLimitsSection so the component is presentation only.
export function useSystemLimitsForm(group) {
  // Each tab owns only its own fields, so it saves and dirty-tracks
  // independently of the others.
  const fields = ref([])
  const form = reactive({})
  const loading = ref(true)
  const saving = ref(false)
  const loadError = ref('')
  const formVersion = ref(0)

  function applyFromResponse(payload) {
    fields.value = (payload.fields ?? []).filter((f) => f.group === group)
    for (const f of fields.value) {
      form[f.key] = f.value
    }
    formVersion.value += 1
  }

  async function load() {
    loading.value = true
    loadError.value = ''
    try {
      applyFromResponse(await settingsApi.getConfig())
    } catch (err) {
      loadError.value = '載入設定失敗，請稍後再試。'
    } finally {
      loading.value = false
    }
  }

  async function handleSave() {
    saving.value = true
    try {
      // Only send keys the form actually has a value for — protects against
      // clobbering future fields the frontend doesn't know about yet.
      const values = {}
      for (const f of fields.value) {
        values[f.key] = form[f.key]
      }
      applyFromResponse(await settingsApi.updateConfig(values))
      ElMessage.success('設定已儲存')
    } catch (err) {
      const status = err?.response?.status
      if (status === 422 || status === 400) {
        ElMessage.error(err.response.data?.detail ?? '輸入值不符合限制')
      } else if (status === 403) {
        ElMessage.error('需要管理員權限')
      } else {
        ElMessage.error('儲存失敗，請稍後再試')
      }
    } finally {
      saving.value = false
    }
  }

  const dirty = computed(() =>
    fields.value.some((f) => form[f.key] !== f.value),
  )

  function handleReset() {
    for (const f of fields.value) {
      form[f.key] = f.value
    }
  }

  function copyFor(key) {
    return FIELD_COPY[key] ?? { label: key, description: '', unit: '' }
  }

  onMounted(load)

  return {
    fields,
    form,
    loading,
    saving,
    loadError,
    formVersion,
    dirty,
    handleSave,
    handleReset,
    copyFor,
  }
}
