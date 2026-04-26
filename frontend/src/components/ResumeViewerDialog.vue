<script setup>
import { computed, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElMessage,
  ElPopconfirm,
  ElSegmented,
  ElUpload,
} from 'element-plus'
import { Delete, Document, Upload } from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'changed'])

const auth = useAuthStore()

// Bumping this re-mounts the iframe so the browser refetches the new PDF.
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
  return membersApi.resumePdfUrl(props.member.id, cacheBuster.value)
})

watch(
  () => [props.modelValue, props.member?.id, props.member?.has_resume_pdf, props.member?.has_resume_md],
  ([open]) => {
    if (!open || !props.member) return
    cacheBuster.value = Date.now()
    // Default selection: PDF if available, else Markdown.
    if (props.member.has_resume_pdf) tab.value = 'pdf'
    else if (props.member.has_resume_md) tab.value = 'md'
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

async function handleUploadPdf({ file }) {
  if (!props.member) return
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

async function handleDeletePdf() {
  if (!props.member) return
  try {
    await membersApi.deleteResumePdf(props.member.id)
    ElMessage.success('已刪除履歷 PDF')
    emit('changed')
    if (props.member.has_resume_md) {
      tab.value = 'md'
    }
  } catch (err) {
    ElMessage.error('刪除失敗')
  }
}

defineExpose({ handleUploadPdf, handleDeletePdf })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="member ? `${member.real_name} 的履歷` : '履歷'"
    width="820"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="member" class="resume-viewer">
      <header class="viewer-header">
        <el-segmented
          v-if="availableFormats.length > 1"
          v-model="tab"
          :options="availableFormats"
          data-test="format-segmented"
        />
        <span v-else-if="availableFormats.length === 1" class="single-tag">
          僅有 {{ availableFormats[0].label }} 格式
        </span>

        <div v-if="auth.isAdmin" class="admin-actions">
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
          <el-popconfirm
            v-if="member.has_resume_pdf"
            title="確定要刪除這份 PDF 履歷嗎？"
            confirm-button-text="刪除"
            cancel-button-text="取消"
            confirm-button-type="danger"
            :teleported="false"
            @confirm="handleDeletePdf"
          >
            <template #reference>
              <el-button
                :icon="Delete"
                size="small"
                type="danger"
                plain
                data-test="delete-pdf"
              >
                刪除 PDF
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </header>

      <div class="viewer-body">
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
      <el-button @click="close">關閉</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.resume-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.single-tag {
  color: #909399;
  font-size: 13px;
}

.admin-actions {
  display: flex;
  gap: 8px;
}

.viewer-body {
  min-height: 480px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.empty-state {
  padding: 40px 0;
}

.pdf-frame {
  width: 100%;
  height: 600px;
  border: 0;
}

.md-frame {
  padding: 16px 24px;
  max-height: 600px;
  overflow: auto;
  background: #ffffff;
}
</style>
