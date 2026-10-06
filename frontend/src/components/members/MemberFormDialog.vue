<script setup>
import { computed, markRaw, reactive, ref, watch } from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElUpload,
} from 'element-plus'
import { Delete, Document, Loading, Upload } from '@element-plus/icons-vue'

import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'

import { membersApi } from '../../api/members'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const linkedDiscordId = ref('')
const discordId = ref('')
const linkingDiscord = ref(false)
const discordLinkError = ref('')

const isEdit = computed(() => props.member !== null)
const title = computed(() => (isEdit.value ? '編輯成員' : '新增成員'))

// Admin can set the Discord handle when creating, or fix the pending handle of
// an unclaimed member (linked account not yet bound). A claimed account's
// handle is authoritative and left alone.
const canEditPendingHandle = computed(
  () =>
    isEdit.value &&
    auth.isActuallyAdmin &&
    props.member?.account_status === 'pending' &&
    !linkedDiscordId.value,
)
const showDiscordField = computed(
  () => (!isEdit.value && auth.isActuallyAdmin) || canEditPendingHandle.value,
)

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  graduation_year: new Date().getFullYear(),
  real_name: '',
  institution: '',
  position: '',
  resume_md: '',
  joined_at: null,
  discord_username: '',
})

// PDF state lives outside the el-form because the upload is a separate
// API call after the basic save returns.
const pdfFile = ref(null) // newly selected File, or null
// Tracks an in-session PDF removal — destructive, so it runs through
// DeleteWithPasswordDialog and hits the API immediately rather than
// being batched into the form's save click.
const pdfDeletedThisSession = ref(false)
const pdfDeleteDialogOpen = ref(false)
const pdfDeleteSubmitting = ref(false)
const pdfDeleteError = ref('')

const rules = {
  graduation_year: [
    { required: true, message: '請輸入畢業年份', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '請輸入本名', trigger: 'blur' }],
  institution: [
    { required: true, message: '請輸入學校／公司', trigger: 'blur' },
  ],
}

const hasExistingPdf = computed(
  () =>
    isEdit.value &&
    props.member?.has_resume_pdf &&
    !pdfDeletedThisSession.value,
)

const pdfStatusText = computed(() => {
  if (pdfFile.value) return `已選擇：${pdfFile.value.name}`
  if (hasExistingPdf.value) return '目前已有 PDF'
  if (pdfDeletedThisSession.value) return '已移除 PDF'
  return '尚未提供 PDF'
})

const pdfHasPendingChange = computed(() => pdfFile.value !== null)

const pdfUploadButtonText = computed(() => {
  if (pdfFile.value) return '更換選擇'
  if (isEdit.value && props.member?.has_resume_pdf) return '替換 PDF'
  return '選擇 PDF'
})

function resetForm(member) {
  Object.assign(form, {
    graduation_year: member?.graduation_year ?? new Date().getFullYear(),
    real_name: member?.real_name ?? '',
    institution: member?.institution ?? '',
    position: member?.position ?? '',
    resume_md: member?.resume_md ?? '',
    joined_at: member?.joined_at ?? null,
    discord_username:
      member?.account_discord_username ?? member?.discord_username ?? '',
  })
  discordId.value = ''
  linkedDiscordId.value = ''
  discordLinkError.value = ''
  pdfFile.value = null
  pdfDeletedThisSession.value = false
  pdfDeleteDialogOpen.value = false
  pdfDeleteError.value = ''
  formRef.value?.clearValidate()
}

watch(
  () => [props.modelValue, props.member],
  ([open]) => {
    if (open) resetForm(props.member)
  },
  { immediate: true },
)

const canLinkDiscord = computed(
  () =>
    canEditPendingHandle.value &&
    auth.isAdmin &&
    props.member?.is_active !== false,
)
async function linkDiscord() {
  if (!canLinkDiscord.value || submitting.value || linkingDiscord.value) return
  const id = discordId.value.trim()
  if (!/^[1-9][0-9]{0,19}$/.test(id)) {
    discordLinkError.value =
      '請填入純數字的 Discord 使用者 ID，不能填使用者名稱。'
    return
  }
  linkingDiscord.value = true
  discordLinkError.value = ''
  try {
    await membersApi.linkDiscord(props.member.id, {
      discord_id: id,
      discord_username: form.discord_username.trim() || null,
    })
    linkedDiscordId.value = id
    ElMessage.success('已連結 Discord 帳號，成員狀態已更新為已加入')
    emit('saved')
  } catch (err) {
    const detail = err?.response?.data?.detail
    discordLinkError.value =
      typeof detail === 'string' ? detail : '連結失敗，請稍後再試。'
  } finally {
    linkingDiscord.value = false
  }
}

function close() {
  if (linkingDiscord.value) return
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
}

function clearPdfChange() {
  pdfFile.value = null
}

async function askDeletePdf() {
  pdfDeleteError.value = ''
  // Admins re-authenticate with a password; an owning member just confirms.
  if (auth.isActuallyAdmin) {
    pdfDeleteDialogOpen.value = true
    return
  }
  try {
    await ElMessageBox.confirm(
      '將永久移除你的 PDF 履歷檔，此操作無法復原。',
      '移除 PDF 履歷',
      { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' },
    )
  } catch {
    return // user cancelled
  }
  await handleDeletePdf()
}

async function handleDeletePdf(password) {
  if (!isEdit.value || !props.member?.id) return
  pdfDeleteSubmitting.value = true
  pdfDeleteError.value = ''
  try {
    await membersApi.deleteResumePdf(props.member.id, password)
    pdfDeletedThisSession.value = true
    pdfDeleteDialogOpen.value = false
    ElMessage.success('已移除 PDF 履歷')
    // Tell the parent the member's resume_pdf flag changed so the
    // members list refreshes; the form keeps its local state via
    // pdfDeletedThisSession until close.
    emit('saved')
  } catch (err) {
    const status = err?.response?.status
    if (status === 422) pdfDeleteError.value = '密碼錯誤'
    else if (status === 403) pdfDeleteError.value = '權限不足'
    else pdfDeleteError.value = '移除失敗，請稍後再試'
  } finally {
    pdfDeleteSubmitting.value = false
  }
}

function buildPayload() {
  const trimmedPosition = form.position.trim()
  const payload = {
    graduation_year: form.graduation_year,
    real_name: form.real_name.trim(),
    institution: form.institution.trim(),
    position: trimmedPosition === '' ? null : trimmedPosition,
    resume_md: form.resume_md.trim() || null,
  }
  if (form.joined_at) {
    const d =
      form.joined_at instanceof Date ? form.joined_at : new Date(form.joined_at)
    payload.joined_at = d.toISOString()
  }
  if (!isEdit.value) {
    const dh = form.discord_username.trim()
    if (dh) payload.discord_username = dh
  } else if (canEditPendingHandle.value) {
    payload.discord_username = form.discord_username.trim()
  }
  return payload
}

async function applyPdfChanges(memberId) {
  if (pdfFile.value) {
    await membersApi.uploadResumePdf(memberId, pdfFile.value)
  }
}

async function handleSubmit() {
  if (linkingDiscord.value) return
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  // Persistent top toast — same pattern as the photo / PDF uploads —
  // so the user sees something is happening even before the save
  // button's loading spinner reaches their eye.
  const toast = ElMessage({
    message: isEdit.value ? '儲存中…' : '新增中…',
    icon: markRaw(Loading),
    duration: 0,
    customClass: 'message-uploading',
  })
  let basicSaveOk = false
  try {
    const payload = buildPayload()
    let memberId
    if (isEdit.value) {
      const updated = await membersApi.update(props.member.id, payload)
      memberId = updated.id
      // The navbar shows the member's real name from the auth session; if a
      // member just renamed their own profile, refresh it so the chip updates
      // without a page reload. Best-effort — never let it break the save flow.
      if (auth.user && props.member.id === auth.user.member_id) {
        try {
          await auth.fetchMe()
        } catch (err) {
          // Navbar will catch up on the next natural reload.
        }
      }
    } else {
      const created = await membersApi.create(payload)
      memberId = created.id
    }
    basicSaveOk = true

    await applyPdfChanges(memberId)

    toast.close()
    ElMessage.success(isEdit.value ? '已更新成員' : '已新增成員')
    emit('saved')
    close()
  } catch (err) {
    toast.close()
    const status = err?.response?.status
    if (basicSaveOk) {
      // Basic info already saved; only the PDF step failed. Refresh the
      // list so the caller sees the updated basic fields.
      if (status === 413) ElMessage.error('成員已儲存，但 PDF 過大')
      else if (status === 415) ElMessage.error('成員已儲存，但 PDF 格式不支援')
      else ElMessage.error('成員已儲存，但 PDF 處理失敗')
      emit('saved')
      close()
    } else if (status === 409) {
      ElMessage.error('此 Discord 使用者已註冊，不需重複建檔')
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

defineExpose({ handlePdfChange, clearPdfChange })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="540"
    :close-on-click-modal="false"
    :close-on-press-escape="!linkingDiscord"
    :show-close="!linkingDiscord"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="畢業年份" prop="graduation_year">
        <el-input-number
          v-model="form.graduation_year"
          :min="1900"
          :max="2100"
        />
      </el-form-item>
      <el-form-item label="本名" prop="real_name">
        <el-input v-model="form.real_name" maxlength="64" show-word-limit />
      </el-form-item>
      <el-form-item label="學校／公司" prop="institution">
        <el-input
          v-model="form.institution"
          maxlength="128"
          show-word-limit
          data-test="form-institution"
        />
      </el-form-item>
      <el-form-item label="系所／職位（選填）" prop="position">
        <el-input
          v-model="form.position"
          maxlength="128"
          show-word-limit
          data-test="form-position"
        />
      </el-form-item>
      <el-form-item v-if="auth.isActuallyAdmin" label="入群時間">
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
      <el-form-item
        v-if="showDiscordField"
        label="Discord 使用者名稱（選填，成員登入後自動綁定）"
      >
        <el-input
          v-model="form.discord_username"
          maxlength="64"
          show-word-limit
          placeholder="例如 alice.h"
          data-test="form-discord-username"
        />
      </el-form-item>
      <div
        v-if="canLinkDiscord || linkedDiscordId"
        class="discord-link-panel"
        data-test="discord-link-panel"
      >
        <h4>手動連結 Discord 帳號</h4>
        <p v-if="linkedDiscordId" role="status">
          已連結 {{ linkedDiscordId }}，成員狀態為「已加入」。
        </p>
        <template v-else>
          <p>
            在 Discord 開啟開發者模式，右鍵點選成員並複製「使用者 ID」。請確認
            ID 屬於本人，連結後該 Discord 帳號即可登入此成員帳號。
          </p>
          <el-input
            v-model="discordId"
            aria-label="Discord 使用者 ID"
            placeholder="貼上純數字的使用者 ID"
            maxlength="20"
            :disabled="linkingDiscord || submitting"
            data-test="form-discord-id"
          />
          <p v-if="discordLinkError" role="alert" class="discord-link-error">
            {{ discordLinkError }}
          </p>
          <el-button
            type="primary"
            plain
            :loading="linkingDiscord"
            :disabled="submitting || !discordId.trim()"
            data-test="link-discord-button"
            @click="linkDiscord"
            >連結 Discord 帳號</el-button
          >
          <small
            >連結立即生效，其他表單欄位仍需按「儲存」。實際登入仍會驗證群組資格。</small
          >
        </template>
      </div>
      <el-form-item label="履歷 PDF">
        <div class="pdf-control">
          <div
            class="pdf-status"
            :class="{ 'is-pending': pdfHasPendingChange }"
          >
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
              v-if="hasExistingPdf && !pdfFile"
              size="small"
              type="danger"
              plain
              :icon="Delete"
              data-test="mark-remove-pdf"
              @click="askDeletePdf"
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
      <el-button :disabled="linkingDiscord" @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-test="save-button"
        :disabled="linkingDiscord"
        @click="handleSubmit"
      >
        {{ isEdit ? '儲存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>

  <DeleteWithPasswordDialog
    v-model="pdfDeleteDialogOpen"
    title="移除 PDF 履歷"
    :item-name="member?.real_name ?? ''"
    warning="將永久移除這位成員的 PDF 履歷檔。此操作無法復原。"
    :loading="pdfDeleteSubmitting"
    :error-message="pdfDeleteError"
    @confirm="handleDeletePdf"
  />
</template>

<style scoped>
.discord-link-panel {
  padding: 16px;
  margin-bottom: 22px;
  border: 1px solid #ded9f4;
  border-radius: 12px;
  background: #f9f7ff;
}
.discord-link-panel h4 {
  margin: 0 0 8px;
  color: #6857b3;
}
.discord-link-panel p,
.discord-link-panel small {
  font-size: 12px;
  line-height: 1.8;
  color: #817794;
}
.discord-link-panel .el-button {
  margin-top: 12px;
}
.discord-link-panel small {
  display: block;
  margin-top: 10px;
}
.discord-link-panel .discord-link-error {
  color: #c45162;
}

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
