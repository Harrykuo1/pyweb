<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  ElAlert,
  ElButton,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElSkeleton,
  ElUpload,
} from 'element-plus'
import {
  Delete,
  Document,
  InfoFilled,
  Loading,
  Picture,
  UploadFilled,
} from '@element-plus/icons-vue'

import { jobAttachmentsApi } from '../api/jobAttachments'
import { settingsApi } from '../api/settings'
import AttachmentConflictDialog from './AttachmentConflictDialog.vue'

const props = defineProps({
  jobId: { type: Number, required: true },
})

// Server enforces these too, but advertising them keeps the picker
// from offering files it'll just reject after upload — saves the
// round-trip and a wasted error toast.
const ACCEPT = '.pdf,.ppt,.pptx,.doc,.docx,.png,.jpg,.jpeg'
const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg'])

const attachments = ref([])
const loading = ref(true)
const uploading = ref(false)
// Human-readable status line shown while a batch is in flight. Office
// formats spend several seconds in server-side conversion (OnlyOffice)
// after the bytes land, so without an explicit notice users wonder
// whether the upload froze. We surface progress as "正在處理 N/M:
// filename..." plus a "Office 檔案需轉檔，請稍候" hint when relevant.
const uploadStatus = ref('')
const maxAttachments = ref(null)
const maxMb = ref(null)

const OFFICE_EXTS = new Set(['.doc', '.docx', '.ppt', '.pptx'])

const conflictDialogOpen = ref(false)
const conflictRows = ref([])
let resolveConflictPromise = null

const existingNames = computed(
  () => new Set(attachments.value.map((a) => a.filename)),
)
const atCapacity = computed(
  () => maxAttachments.value !== null && attachments.value.length >= maxAttachments.value,
)

async function load() {
  loading.value = true
  try {
    const [list, cfg] = await Promise.all([
      jobAttachmentsApi.list(props.jobId),
      settingsApi.getConfig().catch(() => null),
    ])
    attachments.value = list
    if (cfg) {
      const byKey = Object.fromEntries(cfg.fields.map((f) => [f.key, f.value]))
      maxAttachments.value = byKey.max_attachments_per_job ?? null
      maxMb.value = byKey.max_attachment_mb ?? null
    }
  } catch (err) {
    ElMessage.error('載入附件列表失敗')
  } finally {
    loading.value = false
  }
}

onMounted(load)

function iconFor(name) {
  const lower = name.toLowerCase()
  const dot = lower.lastIndexOf('.')
  const ext = dot >= 0 ? lower.slice(dot) : ''
  return IMAGE_EXTS.has(ext) ? Picture : Document
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Queue files added in one user gesture so we can ask about all
// conflicts in a single modal instead of one-by-one.
const pendingFiles = ref([])
let batchScheduled = false

function handleFileSelected(uploadFile) {
  if (!uploadFile?.raw) return
  pendingFiles.value.push(uploadFile.raw)
  if (batchScheduled) return
  batchScheduled = true
  // Microtask: every on-change from the same user gesture lands first.
  Promise.resolve().then(processBatch)
}

async function processBatch() {
  batchScheduled = false
  const batch = pendingFiles.value
  pendingFiles.value = []

  const conflicts = batch.filter((f) => existingNames.value.has(f.name))
  let resolutions = {}
  if (conflicts.length > 0) {
    const result = await askForResolutions(
      conflicts.map((f) => ({ filename: f.name })),
    )
    if (result === null) return
    resolutions = result
  }

  // Filter out skips up-front so the progress counter reflects the
  // files we'll actually upload.
  const queue = batch.filter((f) => resolutions[f.name] !== 'skip')

  uploading.value = true
  try {
    for (let i = 0; i < queue.length; i += 1) {
      const file = queue[i]
      const ext = file.name
        .toLowerCase()
        .slice(file.name.lastIndexOf('.'))
      const officeHint = OFFICE_EXTS.has(ext)
        ? '（Office 檔案需轉檔，約 5–15 秒）'
        : ''
      uploadStatus.value =
        `正在上傳 ${i + 1}/${queue.length}：${file.name}${officeHint}`
      await uploadOne(file, resolutions[file.name] ?? null)
    }
  } finally {
    uploading.value = false
    uploadStatus.value = ''
  }
}

function askForResolutions(rows) {
  conflictRows.value = rows
  conflictDialogOpen.value = true
  return new Promise((resolve) => {
    resolveConflictPromise = resolve
  })
}

function onConflictResolved(result) {
  resolveConflictPromise?.(result)
  resolveConflictPromise = null
}

async function uploadOne(file, strategy) {
  try {
    const created = await jobAttachmentsApi.upload(props.jobId, file, strategy)
    // If overwrite, replace the existing row by id; otherwise append.
    const existingIdx = attachments.value.findIndex((a) => a.id === created.id)
    if (existingIdx >= 0) {
      attachments.value.splice(existingIdx, 1, created)
    } else {
      attachments.value.push(created)
    }
  } catch (err) {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    // Backend now returns Chinese detail strings — use them when
    // available so the user-facing limit/extension echoes the actual
    // admin-configured value (e.g. "檔案大小超過 5 MB 上限").
    const message =
      typeof detail === 'string'
        ? detail
        : status === 413
        ? '超過大小上限'
        : status === 415
        ? '不支援的檔案類型'
        : status === 409
        ? '上傳被拒'
        : '上傳失敗'
    ElMessage.error(`${file.name}：${message}`)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `確定要刪除「${row.filename}」？此動作無法復原。`,
      '刪除附件',
      { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await jobAttachmentsApi.remove(props.jobId, row.id)
    attachments.value = attachments.value.filter((a) => a.id !== row.id)
    ElMessage.success('已刪除附件')
  } catch (err) {
    ElMessage.error('刪除失敗，請稍後再試')
  }
}
</script>

<template>
  <section class="attachments-manager">
    <header class="manager-header">
      <h3 class="title">附件</h3>
      <span class="counter" data-test="attachment-counter">
        {{ attachments.length }}
        <template v-if="maxAttachments !== null">
          / {{ maxAttachments }}
        </template>
      </span>
    </header>

    <p class="manager-hint" data-test="manager-hint">
      <el-icon :size="13"><InfoFilled /></el-icon>
      附件變更（上傳 / 刪除）會立即生效，不需要再按表單下方的「儲存」按鈕。
    </p>

    <el-skeleton v-if="loading" :rows="2" animated />

    <template v-else>
      <div
        v-if="uploadStatus"
        class="upload-status"
        role="status"
        aria-live="polite"
        data-test="upload-status"
      >
        <el-icon class="status-spinner" :size="22"><Loading /></el-icon>
        <span class="status-text">{{ uploadStatus }}</span>
      </div>

      <ul v-if="attachments.length > 0" class="attachment-list">
        <li
          v-for="a in attachments"
          :key="a.id"
          class="attachment-row"
          :data-test="`attachment-row-${a.id}`"
        >
          <el-icon class="row-icon" :size="20">
            <component :is="iconFor(a.filename)" />
          </el-icon>
          <div class="row-meta">
            <a
              :href="`/api/jobs/${jobId}/attachments/${a.id}`"
              :download="a.filename"
              class="row-name"
              :title="a.filename"
            >
              {{ a.filename }}
            </a>
            <span class="row-sub">{{ formatSize(a.size_bytes) }}</span>
          </div>
          <el-button
            text
            :icon="Delete"
            type="danger"
            :data-test="`delete-${a.id}`"
            @click="handleDelete(a)"
          />
        </li>
      </ul>
      <el-alert
        v-else
        type="info"
        :closable="false"
        title="尚未上傳任何附件"
        show-icon
      />

      <el-alert
        v-if="atCapacity"
        class="capacity-alert"
        type="warning"
        :closable="false"
        :title="`已達上限 ${maxAttachments} 個附件，請先刪除舊檔。`"
        show-icon
      />

      <el-upload
        v-else
        ref="uploadRef"
        drag
        multiple
        :auto-upload="false"
        :show-file-list="false"
        :accept="ACCEPT"
        :disabled="uploading"
        :on-change="handleFileSelected"
        data-test="attachment-uploader"
        class="upload-zone"
      >
        <el-icon class="upload-icon" :size="36"><UploadFilled /></el-icon>
        <div class="upload-text">
          將檔案拖到此處，或<em>點擊上傳</em>
        </div>
        <template #tip>
          <div class="upload-tip">
            支援 PDF / Word / PPT / 圖片
            <template v-if="maxMb !== null">
              ；單檔最多 {{ maxMb }} MB
            </template>
          </div>
        </template>
      </el-upload>
    </template>

    <AttachmentConflictDialog
      v-model="conflictDialogOpen"
      :conflicts="conflictRows"
      @resolved="onConflictResolved"
    />
  </section>
</template>

<style scoped>
.attachments-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* High-contrast banner: gradient brand surface + clear motion. Light
   el-alert was too easy to miss during the 5–15s Office conversion. */
.upload-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-radius: 12px;
  background: linear-gradient(
    135deg,
    var(--brand-primary, #6366f1) 0%,
    var(--brand-accent, #8b5cf6) 100%
  );
  color: #ffffff;
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35);
  position: relative;
  overflow: hidden;
}

/* Indeterminate progress bar sliding under the text for extra
   liveness — the spinning icon alone reads as "stalled" to some
   users, but a moving bar always feels "in progress". */
.upload-status::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  width: 40%;
  background: rgba(255, 255, 255, 0.85);
  border-top-right-radius: 3px;
  animation: pyweb-upload-progress 1.6s ease-in-out infinite;
}

.status-spinner {
  flex-shrink: 0;
  animation: pyweb-rotate 1.2s linear infinite;
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.01em;
}

@keyframes pyweb-rotate {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pyweb-upload-progress {
  0% {
    left: -40%;
  }
  100% {
    left: 100%;
  }
}

.manager-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

/* Mental-model reminder: the rest of the form is draft-until-save,
   but attachment ops hit the server immediately. Saying so out loud
   stops the "did I actually save?" confusion. */
.manager-hint {
  margin: -4px 0 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-500, #64748b);
  line-height: 1.5;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.counter {
  font-size: 13px;
  color: var(--ink-500, #64748b);
}

.attachment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.attachment-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  background: var(--surface-1, #f8fafc);
}

.row-icon {
  color: var(--ink-500, #64748b);
}

.row-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-name {
  font-size: 14px;
  color: var(--ink-900, #0f172a);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-name:hover {
  text-decoration: underline;
}

.row-sub {
  font-size: 12px;
  color: var(--ink-500, #64748b);
}

.capacity-alert {
  margin-top: 4px;
}

.upload-zone {
  margin-top: 4px;
}

.upload-icon {
  color: var(--ink-400, #94a3b8);
}

.upload-text {
  font-size: 14px;
  color: var(--ink-700, #334155);
}

.upload-text em {
  color: var(--brand-primary, #6366f1);
  font-style: normal;
}

.upload-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-500, #64748b);
}
</style>
