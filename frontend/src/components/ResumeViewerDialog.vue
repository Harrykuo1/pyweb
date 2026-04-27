<script setup>
import { computed, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElMessage,
  ElSegmented,
  ElUpload,
} from 'element-plus'
import { Delete, Upload } from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'changed'])

const auth = useAuthStore()

const cacheBuster = ref(Date.now())
const tab = ref('pdf')

const availableFormats = computed(() => {
  if (!props.member) return []
  const list = []
  if (props.member.has_resume_pdf) list.push({ label: 'PDF', value: 'pdf' })
  if (props.member.has_resume_md) list.push({ label: 'Markdown', value: 'md' })
  return list
})

const pdfSrc = computed(() => {
  if (!props.member) return ''
  // Tell the browser's built-in PDF viewer to drop its toolbar and side
  // navigation pane, and fit the page to the iframe width. Chromium-based
  // browsers (Chrome / Edge) respect these fragment parameters; others
  // ignore them and fall back to their defaults.
  const url = membersApi.resumePdfUrl(props.member.id, cacheBuster.value)
  return `${url}#toolbar=0&navpanes=0&view=FitH`
})

watch(
  () => [props.modelValue, props.member?.id, props.member?.has_resume_pdf, props.member?.has_resume_md],
  ([open]) => {
    if (!open || !props.member) return
    cacheBuster.value = Date.now()
    if (props.member.has_resume_pdf) tab.value = 'pdf'
    else if (props.member.has_resume_md) tab.value = 'md'
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

async function handleUploadPdf(uploadFile) {
  if (!props.member) return
  // el-upload's on-change passes its UploadFile wrapper; .raw holds the
  // native File needed for FormData.
  const file = uploadFile?.raw ?? uploadFile
  if (!file || typeof file.size !== 'number') return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('PDF 不可超過 10 MB')
    return
  }
  if (file.type !== 'application/pdf') {
    ElMessage.error('檔案必須是 PDF')
    return
  }
  try {
    await membersApi.uploadResumePdf(props.member.id, file)
    cacheBuster.value = Date.now()
    ElMessage.success('已上傳履歷 PDF')
    tab.value = 'pdf'
    emit('changed')
  } catch (err) {
    if (err?.response?.status === 413) ElMessage.error('檔案過大')
    else if (err?.response?.status === 415) ElMessage.error('格式不支援')
    else ElMessage.error('上傳失敗')
  }
}

// ---------- Delete PDF with admin-password confirmation ----------
const deletePdfDialogOpen = ref(false)
const deletePdfSubmitting = ref(false)
const deletePdfError = ref('')

function askDeletePdf() {
  deletePdfError.value = ''
  deletePdfDialogOpen.value = true
}

async function handleDeletePdf(password) {
  if (!props.member) return
  deletePdfSubmitting.value = true
  deletePdfError.value = ''
  try {
    await membersApi.deleteResumePdf(props.member.id, password)
    ElMessage.success('已刪除履歷 PDF')
    deletePdfDialogOpen.value = false
    emit('changed')
    if (props.member.has_resume_md) {
      tab.value = 'md'
    }
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) deletePdfError.value = '密碼錯誤'
    else if (status === 403) deletePdfError.value = '權限不足'
    else deletePdfError.value = '刪除失敗，請稍後再試'
  } finally {
    deletePdfSubmitting.value = false
  }
}

defineExpose({ handleUploadPdf, handleDeletePdf, askDeletePdf })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="member ? `${member.real_name} 的履歷` : '履歷'"
    width="1000"
    class="resume-dialog"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="member" class="resume-viewer">
      <div v-if="availableFormats.length > 1" class="switcher-row">
        <el-segmented
          v-model="tab"
          :options="availableFormats"
          size="large"
          class="rounded-switcher"
          data-test="format-segmented"
        />
      </div>
      <div v-else-if="availableFormats.length === 1" class="single-tag-row">
        僅有 {{ availableFormats[0].label }} 格式
      </div>

      <div class="viewer-body" :class="{ 'is-pdf': tab === 'pdf' && availableFormats.length }">
        <div v-if="availableFormats.length === 0" class="empty-state">
          <el-empty description="尚未上傳履歷" />
        </div>

        <iframe
          v-else-if="tab === 'pdf'"
          :src="pdfSrc"
          class="pdf-frame"
          data-test="pdf-frame"
        />

        <div v-else-if="tab === 'md'" class="md-frame" data-test="md-preview">
          <MdPreview :model-value="member.resume_md ?? ''" theme="light" />
        </div>
      </div>
    </div>

    <template #footer>
      <div class="footer-row">
        <div class="footer-admin">
          <template v-if="auth.isAdmin && member">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="application/pdf"
              :on-change="handleUploadPdf"
              data-test="upload-pdf"
            >
              <el-button :icon="Upload" size="small" plain>
                {{ member.has_resume_pdf ? '替換 PDF' : '上傳 PDF' }}
              </el-button>
            </el-upload>
            <el-button
              v-if="member.has_resume_pdf"
              :icon="Delete"
              size="small"
              type="danger"
              plain
              data-test="delete-pdf"
              @click="askDeletePdf"
            >
              刪除 PDF
            </el-button>
          </template>
        </div>
        <el-button @click="close">關閉</el-button>
      </div>
    </template>
  </el-dialog>

  <DeleteWithPasswordDialog
    v-model="deletePdfDialogOpen"
    title="刪除履歷 PDF"
    :item-name="member?.real_name ?? ''"
    warning="將永久刪除這位成員的 PDF 履歷檔。此操作無法復原。"
    :loading="deletePdfSubmitting"
    :error-message="deletePdfError"
    @confirm="handleDeletePdf"
  />
</template>

<style scoped>
.resume-dialog :deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

.resume-dialog :deep(.el-dialog__body) {
  padding: 16px 24px 0;
}

.resume-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #f2f3f5;
}

.resume-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.switcher-row {
  display: flex;
  justify-content: center;
}

.rounded-switcher :deep(.el-segmented) {
  background: #f0f2f5;
  border-radius: 999px;
  padding: 4px;
  --el-segmented-item-selected-bg-color: #ffffff;
  --el-segmented-item-selected-color: #303133;
  --el-segmented-item-hover-color: #303133;
  --el-segmented-color: #606266;
}

.rounded-switcher :deep(.el-segmented__item) {
  border-radius: 999px;
  padding: 0 24px;
  min-width: 120px;
  color: #606266;
  transition: color 0.2s;
}

/* Element Plus paints the active state via a separate indicator element
   that absolutely positions behind the selected item — override that one
   instead of the item background. */
.rounded-switcher :deep(.el-segmented__item-selected) {
  background-color: #ffffff !important;
  border-radius: 999px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.rounded-switcher :deep(.el-segmented__item.is-selected) {
  color: #303133 !important;
}

.single-tag-row {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 4px 0;
}

.viewer-body {
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
  min-height: 70vh;
  display: flex;
}

.viewer-body.is-pdf {
  background: #525659;
  border-color: #525659;
}

.pdf-frame {
  flex: 1;
  width: 100%;
  height: 70vh;
  border: 0;
  display: block;
}

.md-frame {
  flex: 1;
  padding: 24px 32px;
  max-height: 70vh;
  overflow: auto;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.footer-admin {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
