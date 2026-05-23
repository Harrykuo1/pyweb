<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElIcon,
  ElMessage,
  ElSkeleton,
  ElUpload,
} from 'element-plus'
import {
  ArrowRight,
  Close,
  Delete,
  Document,
  Folder,
  FolderOpened,
  InfoFilled,
  Loading,
  Picture,
  UploadFilled,
} from '@element-plus/icons-vue'

import { jobAttachmentsApi } from '../api/jobAttachments'
import { settingsApi } from '../api/settings'
import {
  attachmentsUnder,
  breadcrumbSegments as buildBreadcrumb,
  buildListing,
  joinPath,
} from '../utils/attachmentTree'
import AttachmentConflictDialog from './AttachmentConflictDialog.vue'
import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'

const props = defineProps({
  jobId: { type: Number, required: true },
})

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp'])

// OS-spat metadata files that appear inside folder uploads but the
// admin never actually wants archived. The backend rejects these too
// as a safety net; filtering client-side is the optimisation.
const JUNK_BASENAMES = new Set(['.DS_Store', 'Thumbs.db', 'desktop.ini'])

// Extensions that show "(Office 檔案需轉檔)" hint during upload —
// OnlyOffice conversion adds 5–15s, worth telling the user.
const OFFICE_EXTS = new Set(['.doc', '.docx', '.ppt', '.pptx'])

function isJunk(relpath) {
  const last = relpath.includes('/')
    ? relpath.slice(relpath.lastIndexOf('/') + 1)
    : relpath
  return JUNK_BASENAMES.has(last)
}

const attachments = ref([])
const loading = ref(true)
const uploading = ref(false)
// Human-readable status line shown while a batch is in flight.
const uploadStatus = ref('')
const maxAttachments = ref(null)
const maxMb = ref(null)

// "" = root. Mirrors the viewer's tree-browsing model so uploads
// land in the folder the user is looking at.
const currentPath = ref('')

const conflictDialogOpen = ref(false)
const conflictRows = ref([])
let resolveConflictPromise = null

const folderInputRef = ref(null)

// Selection state for the bulk-delete UX. Files are tracked by row
// id; folders by their *full* path (e.g. "src/components") because
// a "Bar" folder at root and at src/Bar would otherwise collide.
// Folder selection is semantically "every descendant" — the bulk
// action expands it on submit via attachmentsUnder().
const selectedFileIds = ref(new Set())
const selectedFolderPaths = ref(new Set())

const existingNames = computed(
  () => new Set(attachments.value.map((a) => a.filename)),
)
const atCapacity = computed(
  () =>
    maxAttachments.value !== null &&
    attachments.value.length >= maxAttachments.value,
)

const currentListing = computed(() =>
  buildListing(attachments.value, currentPath.value),
)
const breadcrumbSegments = computed(() => buildBreadcrumb(currentPath.value))

const currentPathLabel = computed(() =>
  currentPath.value ? currentPath.value : '附件根目錄',
)

function folderFullPath(folderName) {
  return joinPath(currentPath.value, folderName)
}

const selectedFileCount = computed(() => selectedFileIds.value.size)
const selectedFolderCount = computed(() => selectedFolderPaths.value.size)
const selectionCount = computed(
  () => selectedFileCount.value + selectedFolderCount.value,
)

// Total file rows the bulk delete would actually remove: every
// directly-selected file plus every descendant of any selected
// folder (dedup-ed because a folder might contain a file the user
// also ticked individually).
const selectedAttachmentIds = computed(() => {
  const out = new Set(selectedFileIds.value)
  for (const folderPath of selectedFolderPaths.value) {
    for (const a of attachmentsUnder(attachments.value, folderPath)) {
      out.add(a.id)
    }
  }
  return out
})

const visibleFolderPaths = computed(() =>
  currentListing.value.folders.map((f) => folderFullPath(f.name)),
)
const visibleFileIds = computed(() =>
  currentListing.value.files.map((entry) => entry.attachment.id),
)
const visibleEntryCount = computed(
  () => visibleFolderPaths.value.length + visibleFileIds.value.length,
)

// "All visible rows are selected" — used for the select-all checkbox
// at the top of the listing.
const allVisibleSelected = computed(() => {
  if (visibleEntryCount.value === 0) return false
  return (
    visibleFileIds.value.every((id) => selectedFileIds.value.has(id)) &&
    visibleFolderPaths.value.every((p) =>
      selectedFolderPaths.value.has(p),
    )
  )
})
const someVisibleSelected = computed(() => {
  if (allVisibleSelected.value) return false
  return (
    visibleFileIds.value.some((id) => selectedFileIds.value.has(id)) ||
    visibleFolderPaths.value.some((p) => selectedFolderPaths.value.has(p))
  )
})

function isFolderSelected(folderName) {
  return selectedFolderPaths.value.has(folderFullPath(folderName))
}

function toggleFileSelection(id, checked) {
  const next = new Set(selectedFileIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedFileIds.value = next
}

function toggleFolderSelection(folderName, checked) {
  const next = new Set(selectedFolderPaths.value)
  const fp = folderFullPath(folderName)
  if (checked) next.add(fp)
  else next.delete(fp)
  selectedFolderPaths.value = next
}

function toggleSelectAllVisible(checked) {
  const nextFiles = new Set(selectedFileIds.value)
  const nextFolders = new Set(selectedFolderPaths.value)
  if (checked) {
    for (const id of visibleFileIds.value) nextFiles.add(id)
    for (const p of visibleFolderPaths.value) nextFolders.add(p)
  } else {
    for (const id of visibleFileIds.value) nextFiles.delete(id)
    for (const p of visibleFolderPaths.value) nextFolders.delete(p)
  }
  selectedFileIds.value = nextFiles
  selectedFolderPaths.value = nextFolders
}

function clearSelection() {
  selectedFileIds.value = new Set()
  selectedFolderPaths.value = new Set()
}

// Reset selection on navigation: a folder selected at root would
// stay "checked" invisibly once the user drilled into a sibling,
// which is the kind of footgun the user would hit blind. Clearing
// on every path change keeps the toolbar counter honest about what
// the user can see right now.
watch(currentPath, clearSelection)

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

function enterFolder(folderName) {
  currentPath.value = joinPath(currentPath.value, folderName)
}

function jumpToPath(path) {
  currentPath.value = path
}

// Queue files added in one user gesture so we can ask about all
// conflicts in a single modal instead of one-by-one. Each entry is
// {file, relpath} — relpath is the FULL path the upload should land
// at, already prefixed with currentPath so uploads "into" a folder
// land where the user expects.
const pendingFiles = ref([])
let batchScheduled = false

function relpathOf(file) {
  // webkitRelativePath is the directory-relative path Chrome/Edge/
  // Safari expose on File objects sourced from <input webkitdirectory>.
  // Plain file pickers leave it empty; fall back to name.
  return file.webkitRelativePath || file.name
}

function pushPending(file) {
  const source = relpathOf(file)
  if (isJunk(source)) return  // drop .DS_Store / Thumbs.db / desktop.ini
  // Stamp every upload with the breadcrumb's current location — a
  // bare "foo.pdf" picked from inside src/components/ becomes
  // "src/components/foo.pdf"; a folder upload of utils/a.py becomes
  // "src/components/utils/a.py".
  const relpath = joinPath(currentPath.value, source)
  pendingFiles.value.push({ file, relpath })
  if (batchScheduled) return
  batchScheduled = true
  Promise.resolve().then(processBatch)
}

function handleFileSelected(uploadFile) {
  if (!uploadFile?.raw) return
  pushPending(uploadFile.raw)
}

function handleFolderPicked(event) {
  const files = event.target?.files
  if (!files) return
  for (const file of files) {
    pushPending(file)
  }
  // Reset so the same folder can be picked again later.
  event.target.value = ''
}

async function processBatch() {
  batchScheduled = false
  const batch = pendingFiles.value
  pendingFiles.value = []

  const conflicts = batch.filter((entry) =>
    existingNames.value.has(entry.relpath),
  )
  let resolutions = {}
  if (conflicts.length > 0) {
    const result = await askForResolutions(
      conflicts.map((entry) => ({ filename: entry.relpath })),
    )
    if (result === null) return
    resolutions = result
  }

  const queue = batch.filter(
    (entry) => resolutions[entry.relpath] !== 'skip',
  )

  uploading.value = true
  try {
    for (let i = 0; i < queue.length; i += 1) {
      const { file, relpath } = queue[i]
      const ext = relpath
        .toLowerCase()
        .slice(relpath.lastIndexOf('.'))
      const officeHint = OFFICE_EXTS.has(ext)
        ? '（Office 檔案需轉檔，約 5–15 秒）'
        : ''
      uploadStatus.value =
        `正在上傳 ${i + 1}/${queue.length}：${relpath}${officeHint}`
      await uploadOne(file, relpath, resolutions[relpath] ?? null)
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

async function uploadOne(file, relpath, strategy) {
  try {
    const created = await jobAttachmentsApi.upload(
      props.jobId,
      file,
      strategy,
      relpath,
    )
    // If overwrite, replace the existing row by id; otherwise append.
    const existingIdx = attachments.value.findIndex(
      (a) => a.id === created.id,
    )
    if (existingIdx >= 0) {
      attachments.value.splice(existingIdx, 1, created)
    } else {
      attachments.value.push(created)
    }
  } catch (err) {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
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
    ElMessage.error(`${relpath}：${message}`)
  }
}

// Three delete entry points all funnel through one password-confirm
// dialog: single file, single folder (expanded to descendants), and
// the multi-select bulk action. The "pending" descriptor carries
// everything the confirm handler needs to do the right thing, plus
// the user-facing title/itemName/warning for the dialog.
const deleteDialogOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteError = ref('')
const pendingDelete = ref(null)

function openDeleteDialog(descriptor) {
  pendingDelete.value = descriptor
  deleteError.value = ''
  deleteDialogOpen.value = true
}

function handleDelete(row) {
  openDeleteDialog({
    mode: 'single',
    title: '刪除附件',
    itemName: row.filename,
    warning: '此操作無法復原。',
    ids: [row.id],
    successMsg: '已刪除附件',
  })
}

function handleDeleteFolder(folderName) {
  const folderPath = folderFullPath(folderName)
  const descendants = attachmentsUnder(attachments.value, folderPath)
  if (descendants.length === 0) return
  openDeleteDialog({
    mode: 'bulk',
    title: '刪除資料夾',
    itemName: folderName,
    warning: `此操作會清除其中 ${descendants.length} 個檔案，無法復原。`,
    ids: descendants.map((a) => a.id),
    successMsg: `已刪除資料夾「${folderName}」`,
  })
}

function handleBulkDelete() {
  const ids = [...selectedAttachmentIds.value]
  if (ids.length === 0) return
  const folderNote =
    selectedFolderCount.value > 0
      ? `（含 ${selectedFolderCount.value} 個資料夾）`
      : ''
  openDeleteDialog({
    mode: 'bulk',
    title: '批次刪除',
    itemName: `已選 ${selectionCount.value} 個項目${folderNote}`,
    warning: `此操作會清除 ${ids.length} 個檔案，無法復原。`,
    ids,
    successMsg: `已刪除 ${ids.length} 個檔案`,
  })
}

async function onDeleteConfirm(password) {
  const pending = pendingDelete.value
  if (!pending) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    if (pending.mode === 'single') {
      await jobAttachmentsApi.remove(props.jobId, pending.ids[0], password)
    } else {
      await jobAttachmentsApi.bulkRemove(props.jobId, pending.ids, password)
    }
    const idSet = new Set(pending.ids)
    attachments.value = attachments.value.filter((a) => !idSet.has(a.id))
    // Drop any of the deleted ids from the selection set so the bulk
    // bar's counter doesn't keep referring to vanished rows.
    if (pending.ids.some((id) => selectedFileIds.value.has(id))) {
      const nextFiles = new Set(selectedFileIds.value)
      for (const id of pending.ids) nextFiles.delete(id)
      selectedFileIds.value = nextFiles
    }
    // For bulk deletes triggered from the toolbar, the user clearly
    // meant "wipe my selection"; clear the rest too.
    if (pending.mode === 'bulk') clearSelection()
    ElMessage.success(pending.successMsg)
    deleteDialogOpen.value = false
    pendingDelete.value = null
  } catch (err) {
    const status = err?.response?.status
    if (status === 422) deleteError.value = '密碼錯誤'
    else if (status === 403) deleteError.value = '權限不足'
    else deleteError.value = '刪除失敗，請稍後再試'
  } finally {
    deleteSubmitting.value = false
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

      <Transition name="bulk-bar">
        <div
          v-if="selectionCount > 0"
          class="bulk-bar"
          role="region"
          aria-label="批次操作"
          data-test="bulk-bar"
        >
          <span class="bulk-bar-summary">
            已選
            <strong class="bulk-bar-count">{{ selectionCount }}</strong>
            個項目
            <span
              v-if="selectedAttachmentIds.size !== selectionCount"
              class="bulk-bar-detail"
            >
              （共 {{ selectedAttachmentIds.size }} 個檔案）
            </span>
          </span>
          <div class="bulk-bar-actions">
            <el-button
              type="danger"
              :icon="Delete"
              data-test="bulk-delete"
              @click="handleBulkDelete"
            >
              刪除選取
            </el-button>
            <el-button
              text
              :icon="Close"
              data-test="bulk-clear"
              @click="clearSelection"
            >
              取消
            </el-button>
          </div>
        </div>
      </Transition>

      <nav
        class="breadcrumb"
        aria-label="附件路徑"
        data-test="manager-breadcrumb"
      >
        <template
          v-for="(seg, i) in breadcrumbSegments"
          :key="`bc-${i}-${seg.path}`"
        >
          <span v-if="i > 0" class="breadcrumb-sep" aria-hidden="true">
            <el-icon :size="11"><ArrowRight /></el-icon>
          </span>
          <button
            v-if="i < breadcrumbSegments.length - 1"
            type="button"
            class="breadcrumb-item is-clickable"
            :data-test="`manager-breadcrumb-${i}`"
            @click="jumpToPath(seg.path)"
          >
            {{ seg.name }}
          </button>
          <span
            v-else
            class="breadcrumb-item is-current"
            data-test="manager-breadcrumb-current"
          >
            {{ seg.name }}
          </span>
        </template>
      </nav>

      <div
        v-if="
          currentListing.folders.length > 0 ||
          currentListing.files.length > 0
        "
        class="list-toolbar"
        data-test="manager-list-toolbar"
      >
        <el-checkbox
          :model-value="allVisibleSelected"
          :indeterminate="someVisibleSelected"
          data-test="select-all"
          @change="toggleSelectAllVisible($event)"
        >
          <span class="select-all-label">
            全選此資料夾
            <span class="select-all-sub">
              （{{ visibleEntryCount }} 個項目）
            </span>
          </span>
        </el-checkbox>
      </div>

      <ul
        v-if="
          currentListing.folders.length > 0 ||
          currentListing.files.length > 0
        "
        class="entry-list"
      >
        <li
          v-for="folder in currentListing.folders"
          :key="`folder:${folder.name}`"
          class="entry-row folder-row"
          :class="{ 'is-selected': isFolderSelected(folder.name) }"
          :data-test="`manager-folder-${folder.name}`"
          @click="enterFolder(folder.name)"
        >
          <el-checkbox
            class="row-checkbox"
            :model-value="isFolderSelected(folder.name)"
            :data-test="`select-folder-${folder.name}`"
            :aria-label="`選取資料夾 ${folder.name}`"
            @click.stop
            @change="toggleFolderSelection(folder.name, $event)"
          />
          <el-icon class="row-icon folder-icon" :size="22"><Folder /></el-icon>
          <div class="row-meta">
            <span class="row-name">{{ folder.name }}</span>
            <span class="row-sub">{{ folder.count }} 個檔案</span>
          </div>
          <el-icon class="row-action" :size="14"><ArrowRight /></el-icon>
          <el-button
            text
            :icon="Delete"
            type="danger"
            class="row-delete"
            :data-test="`delete-folder-${folder.name}`"
            :aria-label="`刪除資料夾 ${folder.name}`"
            @click.stop="handleDeleteFolder(folder.name)"
          />
        </li>

        <li
          v-for="entry in currentListing.files"
          :key="`file:${entry.attachment.id}`"
          class="entry-row file-row"
          :class="{ 'is-selected': selectedFileIds.has(entry.attachment.id) }"
          :data-test="`attachment-row-${entry.attachment.id}`"
        >
          <el-checkbox
            class="row-checkbox"
            :model-value="selectedFileIds.has(entry.attachment.id)"
            :data-test="`select-file-${entry.attachment.id}`"
            :aria-label="`選取檔案 ${entry.displayName}`"
            @change="toggleFileSelection(entry.attachment.id, $event)"
          />
          <el-icon class="row-icon" :size="20">
            <component :is="iconFor(entry.displayName)" />
          </el-icon>
          <div class="row-meta">
            <a
              :href="`/api/jobs/${jobId}/attachments/${entry.attachment.id}`"
              :download="entry.displayName"
              class="row-name file-link"
              :title="entry.attachment.filename"
            >
              {{ entry.displayName }}
            </a>
            <span class="row-sub">{{ formatSize(entry.attachment.size_bytes) }}</span>
          </div>
          <el-button
            text
            :icon="Delete"
            type="danger"
            :data-test="`delete-${entry.attachment.id}`"
            @click="handleDelete(entry.attachment)"
          />
        </li>
      </ul>
      <el-alert
        v-else
        type="info"
        :closable="false"
        :title="
          currentPath
            ? '此資料夾還沒有附件。透過下方上傳區把檔案放進來吧。'
            : '尚未上傳任何附件'
        "
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

      <template v-else>
        <el-upload
          ref="uploadRef"
          drag
          multiple
          :auto-upload="false"
          :show-file-list="false"
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
              上傳目的地：<strong>{{ currentPathLabel }}</strong>
            </div>
            <div class="upload-tip secondary">
              不限檔案類型；PDF、圖片、Office 文件會在頁面內預覽，其他類型一律提供下載
              <template v-if="maxMb !== null">
                。單檔最多 {{ maxMb }} MB
              </template>
            </div>
          </template>
        </el-upload>

        <!-- 資料夾上傳：el-upload 沒有 directory prop，所以開另一個按鈕觸發
             原生 <input webkitdirectory>。瀏覽器把整個資料夾的檔案展平送進來，
             每個 File 帶 webkitRelativePath；前端再用 currentPath 包一層，
             整個資料夾就會落在「當前位置 / 來源資料夾名稱」之下。 -->
        <div class="folder-upload-row">
          <input
            ref="folderInputRef"
            type="file"
            multiple
            webkitdirectory
            directory
            class="folder-input"
            data-test="folder-input"
            @change="handleFolderPicked"
          />
          <el-button
            :icon="FolderOpened"
            :disabled="uploading"
            data-test="folder-upload-button"
            @click="folderInputRef?.click()"
          >
            上傳整個資料夾
          </el-button>
          <span class="folder-tip">
            保留來源資料夾結構，整個放到目前位置之下；自動略過 .DS_Store / Thumbs.db / desktop.ini
          </span>
        </div>
      </template>
    </template>

    <AttachmentConflictDialog
      v-model="conflictDialogOpen"
      :conflicts="conflictRows"
      @resolved="onConflictResolved"
    />

    <DeleteWithPasswordDialog
      v-model="deleteDialogOpen"
      :title="pendingDelete?.title ?? '刪除確認'"
      :item-name="pendingDelete?.itemName ?? ''"
      :warning="pendingDelete?.warning ?? '此操作無法復原。'"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      @confirm="onDeleteConfirm"
    />
  </section>
</template>

<style scoped>
.attachments-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-status :deep(.el-icon.is-loading) {
  animation: pyweb-rotate 1.2s linear infinite;
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

/* ---------- Breadcrumb ---------- */
.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 8px;
  font-size: 13px;
}

.breadcrumb-item {
  border: 0;
  background: transparent;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: var(--brand-primary, #6366f1);
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.breadcrumb-item.is-clickable:hover {
  background: rgba(99, 102, 241, 0.12);
}

.breadcrumb-item.is-current {
  color: var(--ink-900, #0f172a);
  font-weight: 500;
  cursor: default;
}

.breadcrumb-sep {
  display: inline-flex;
  align-items: center;
  color: var(--ink-400, #94a3b8);
  margin: 0 2px;
}

/* ---------- Bulk action bar ---------- */
.bulk-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  border-radius: 10px;
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12) 0%,
    rgba(139, 92, 246, 0.14) 100%
  );
  border: 1px solid rgba(99, 102, 241, 0.32);
  position: sticky;
  top: 0;
  z-index: 5;
  backdrop-filter: blur(6px);
}

.bulk-bar-summary {
  font-size: 13px;
  color: var(--ink-700, #334155);
}

.bulk-bar-count {
  font-weight: 700;
  color: var(--brand-primary, #6366f1);
  margin: 0 2px;
}

.bulk-bar-detail {
  color: var(--ink-500, #64748b);
  font-size: 12px;
  margin-left: 4px;
}

.bulk-bar-actions {
  display: flex;
  gap: 8px;
}

.bulk-bar-enter-from,
.bulk-bar-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.bulk-bar-enter-active,
.bulk-bar-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

/* ---------- List toolbar (select-all row) ---------- */
.list-toolbar {
  display: flex;
  align-items: center;
  padding: 4px 4px 0;
  font-size: 13px;
}

.select-all-label {
  color: var(--ink-700, #334155);
  font-weight: 500;
}

.select-all-sub {
  color: var(--ink-500, #64748b);
  font-weight: 400;
  margin-left: 2px;
}

/* ---------- Entry list (folders + files) ---------- */
.entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.entry-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: var(--surface-1, #f8fafc);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.entry-row:hover {
  background: rgba(99, 102, 241, 0.06);
  border-color: rgba(99, 102, 241, 0.32);
}

.entry-row.is-selected {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.5);
}

.row-checkbox {
  flex-shrink: 0;
  /* Default el-checkbox label has a margin that pushes the next
     row item further than the row's own 12px gap. Strip it so the
     spacing stays consistent across all rows. */
  margin-right: 0;
}

.folder-row {
  cursor: pointer;
}

.row-delete {
  flex-shrink: 0;
}

.row-icon {
  color: var(--ink-500, #64748b);
}

.folder-icon {
  color: var(--brand-primary, #6366f1);
}

.row-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-name {
  font-weight: 500;
  color: var(--ink-900, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-link {
  text-decoration: none;
  color: inherit;
}

.file-link:hover {
  text-decoration: underline;
}

.row-sub {
  font-size: 12px;
  color: var(--ink-500, #64748b);
}

.row-action {
  color: var(--ink-400, #94a3b8);
}

.entry-row:hover .row-action {
  color: var(--brand-primary, #6366f1);
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
  font-size: 13px;
  color: var(--ink-700, #334155);
}

.upload-tip strong {
  color: var(--brand-primary, #6366f1);
  font-weight: 600;
}

.upload-tip.secondary {
  font-size: 12px;
  color: var(--ink-500, #64748b);
  margin-top: 2px;
}

.folder-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.folder-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.folder-tip {
  font-size: 12px;
  color: var(--ink-500, #64748b);
}
</style>
