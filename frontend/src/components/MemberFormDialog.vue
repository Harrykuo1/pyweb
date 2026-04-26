<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElUpload,
} from 'element-plus'
import { Delete, Document, Upload } from '@element-plus/icons-vue'

import { membersApi } from '../api/members'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => props.member !== null)
const title = computed(() => (isEdit.value ? '編輯成員' : '新增成員'))

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  graduation_year: new Date().getFullYear(),
  real_name: '',
  current_position: '',
  resume_md: '',
  joined_at: null,
})

// PDF state lives outside the el-form because the upload is a separate
// API call after the basic save returns.
const pdfFile = ref(null)              // newly selected File, or null
const pdfRemoveExisting = ref(false)   // edit-mode flag: drop the stored PDF on save

const rules = {
  graduation_year: [{ required: true, message: '請輸入畢業年份', trigger: 'blur' }],
  real_name: [{ required: true, message: '請輸入本名', trigger: 'blur' }],
  current_position: [{ required: true, message: '請輸入目前就職／就讀', trigger: 'blur' }],
}

const pdfStatusText = computed(() => {
  if (pdfFile.value) return `已選擇：${pdfFile.value.name}`
  if (isEdit.value && props.member?.has_resume_pdf && !pdfRemoveExisting.value) {
    return '目前已有 PDF'
  }
  if (pdfRemoveExisting.value) return '將於儲存時移除現有 PDF'
  return '尚未提供 PDF'
})

const pdfHasPendingChange = computed(
  () => pdfFile.value !== null || pdfRemoveExisting.value,
)

const pdfUploadButtonText = computed(() => {
  if (pdfFile.value) return '更換選擇'
  if (isEdit.value && props.member?.has_resume_pdf) return '替換 PDF'
  return '選擇 PDF'
})

function resetForm(member) {
  Object.assign(form, {
    graduation_year: member?.graduation_year ?? new Date().getFullYear(),
    real_name: member?.real_name ?? '',
    current_position: member?.current_position ?? '',
    resume_md: member?.resume_md ?? '',
    joined_at: member?.joined_at ?? null,
  })
  pdfFile.value = null
  pdfRemoveExisting.value = false
  formRef.value?.clearValidate()
}

watch(
  () => [props.modelValue, props.member],
  ([open]) => {
    if (open) resetForm(props.member)
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

function handlePdfChange(uploadFile) {
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
  pdfFile.value = file
  // Selecting a new file overrides any pending "remove" choice.
  pdfRemoveExisting.value = false
}

function markPdfForRemoval() {
  pdfRemoveExisting.value = true
  pdfFile.value = null
}

function clearPdfChange() {
  pdfFile.value = null
  pdfRemoveExisting.value = false
}

function buildPayload() {
  const payload = {
    graduation_year: form.graduation_year,
    real_name: form.real_name.trim(),
    current_position: form.current_position.trim(),
    resume_md: form.resume_md.trim() || null,
  }
  if (form.joined_at) {
    const d = form.joined_at instanceof Date ? form.joined_at : new Date(form.joined_at)
    payload.joined_at = d.toISOString()
  }
  return payload
}

async function applyPdfChanges(memberId) {
  if (pdfFile.value) {
    await membersApi.uploadResumePdf(memberId, pdfFile.value)
  } else if (pdfRemoveExisting.value && isEdit.value) {
    await membersApi.deleteResumePdf(memberId)
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  let basicSaveOk = false
  try {
    const payload = buildPayload()
    let memberId
    if (isEdit.value) {
      const updated = await membersApi.update(props.member.id, payload)
      memberId = updated.id
    } else {
      const created = await membersApi.create(payload)
      memberId = created.id
    }
    basicSaveOk = true

    await applyPdfChanges(memberId)

    ElMessage.success(isEdit.value ? '已更新成員' : '已新增成員')
    emit('saved')
    close()
  } catch (err) {
    const status = err?.response?.status
    if (basicSaveOk) {
      // Basic info already saved; only the PDF step failed. Refresh the
      // list so the caller sees the updated basic fields.
      if (status === 413) ElMessage.error('成員已儲存，但 PDF 過大')
      else if (status === 415) ElMessage.error('成員已儲存，但 PDF 格式不支援')
      else ElMessage.error('成員已儲存，但 PDF 處理失敗')
      emit('saved')
      close()
    } else if (status === 422) {
      ElMessage.error('輸入格式不正確')
    } else if (status === 403) {
      ElMessage.error('權限不足')
    } else {
      ElMessage.error('儲存失敗，請稍後再試')
    }
  } finally {
    submitting.value = false
  }
}

defineExpose({ handlePdfChange, markPdfForRemoval, clearPdfChange })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="540"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      label-position="right"
    >
      <el-form-item label="畢業年份" prop="graduation_year">
        <el-input-number v-model="form.graduation_year" :min="1900" :max="2100" />
      </el-form-item>
      <el-form-item label="本名" prop="real_name">
        <el-input v-model="form.real_name" maxlength="64" show-word-limit />
      </el-form-item>
      <el-form-item label="目前就職／就讀" prop="current_position">
        <el-input v-model="form.current_position" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="入群時間">
        <el-date-picker
          v-model="form.joined_at"
          type="date"
          placeholder="留空則使用今天"
          value-format="YYYY-MM-DD"
        />
      </el-form-item>
      <el-form-item label="履歷 (Markdown)">
        <el-input
          v-model="form.resume_md"
          type="textarea"
          :rows="6"
          placeholder="可留空。Phase 7 將升級為 Markdown 編輯器"
        />
      </el-form-item>
      <el-form-item label="履歷 PDF">
        <div class="pdf-control">
          <div class="pdf-status" :class="{ 'is-pending': pdfHasPendingChange }">
            <el-icon><Document /></el-icon>
            <span>{{ pdfStatusText }}</span>
          </div>
          <div class="pdf-buttons">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="application/pdf"
              :on-change="handlePdfChange"
              data-test="upload-pdf"
            >
              <el-button size="small" plain :icon="Upload">
                {{ pdfUploadButtonText }}
              </el-button>
            </el-upload>
            <el-button
              v-if="isEdit && member?.has_resume_pdf && !pdfRemoveExisting && !pdfFile"
              size="small"
              type="danger"
              plain
              :icon="Delete"
              data-test="mark-remove-pdf"
              @click="markPdfForRemoval"
            >
              移除
            </el-button>
            <el-button
              v-if="pdfHasPendingChange"
              size="small"
              plain
              data-test="clear-pdf-change"
              @click="clearPdfChange"
            >
              取消變更
            </el-button>
          </div>
          <p class="pdf-hint">PDF 上限 10 MB，儲存時一併上傳</p>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-test="save-button"
        @click="handleSubmit"
      >
        {{ isEdit ? '儲存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.pdf-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.pdf-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.pdf-status.is-pending {
  color: #e6a23c;
}

.pdf-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* el-upload renders as a block-level wrapper around its trigger button.
   Strip the inherent line-height padding so the button row sits flush
   with sibling el-button siblings. */
.pdf-buttons :deep(.el-upload) {
  display: inline-flex;
  align-items: center;
}

.pdf-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
</style>
