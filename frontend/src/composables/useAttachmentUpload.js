import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { jobAttachmentsApi } from '../api/jobAttachments'
import { joinPath } from '../utils/attachmentTree'
import { extractError } from '../utils/apiError'

// OS-spat metadata files that appear inside folder uploads but the admin
// never actually wants archived. The backend rejects these too as a safety
// net; filtering client-side is the optimisation.
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

// The attachments upload pipeline: queue files added in one gesture, run a
// capacity precheck and a single batched conflict prompt, then upload each
// with progress. It reads the shared attachments/currentPath/maxAttachments
// from the host component and mutates attachments in place on success.
// pushPending is the single intake point — the file/folder inputs and the
// drag-drop composable all funnel through it.
export function useAttachmentUpload({
  jobId,
  attachments,
  currentPath,
  maxAttachments,
}) {
  const uploading = ref(false)
  // Human-readable status line shown while a batch is in flight.
  const uploadStatus = ref('')
  // 0–100, populated from axios's onUploadProgress for the currently
  // in-flight file. Drives the progress bar inside the status banner.
  const uploadProgressPercent = ref(0)

  const conflictDialogOpen = ref(false)
  const conflictRows = ref([])
  let resolveConflictPromise = null

  // Queue files added in one user gesture so we can ask about all conflicts
  // in a single modal instead of one-by-one. Each entry is {file, relpath} —
  // relpath is the FULL path the upload should land at, already prefixed
  // with currentPath so uploads "into" a folder land where the user expects.
  const pendingFiles = ref([])
  let batchScheduled = false

  const existingNames = computed(
    () => new Set(attachments.value.map((a) => a.filename)),
  )

  function relpathOf(file) {
    // webkitRelativePath is the directory-relative path Chrome/Edge/Safari
    // expose on File objects sourced from <input webkitdirectory> (and the
    // drag-drop walker stamps it too). Plain file pickers leave it empty;
    // fall back to name.
    return file.webkitRelativePath || file.name
  }

  function pushPending(file) {
    const source = relpathOf(file)
    if (isJunk(source)) return // drop .DS_Store / Thumbs.db / desktop.ini
    // Stamp every upload with the breadcrumb's current location — a bare
    // "foo.pdf" picked from inside src/components/ becomes
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

  function handleFileInputChange(event) {
    // Native <input multiple> selection — same destination as
    // handleFileSelected, just without the el-upload wrapper.
    const files = event.target?.files
    if (!files) return
    for (const file of files) pushPending(file)
    event.target.value = ''
  }

  function handleFolderPicked(event) {
    const files = event.target?.files
    if (!files) return
    for (const file of files) pushPending(file)
    // Reset so the same folder can be picked again later.
    event.target.value = ''
  }

  async function processBatch() {
    batchScheduled = false
    let batch = pendingFiles.value
    pendingFiles.value = []
    if (batch.length === 0) return

    // Capacity precheck: estimate worst case = every queued file becomes a
    // new row (conflict resolutions haven't been chosen yet, so we can't
    // subtract overwrites). If that exceeds the per-job cap, ask the user up
    // front rather than letting the first N succeed and the rest 409.
    if (maxAttachments.value != null) {
      const remaining = Math.max(
        0,
        maxAttachments.value - attachments.value.length,
      )
      if (batch.length > remaining) {
        const keep = remaining
        try {
          await ElMessageBox.confirm(
            `你選了 ${batch.length} 個檔案，但目前只剩 ${remaining} 個名額。要先上傳前 ${keep} 個，其餘略過嗎？`,
            '附件名額不足',
            {
              type: 'warning',
              confirmButtonText: keep > 0 ? `只上傳前 ${keep} 個` : '了解',
              cancelButtonText: '取消整批',
            },
          )
        } catch {
          ElMessage.info('已取消上傳')
          return
        }
        batch = batch.slice(0, keep)
        if (batch.length === 0) return
      }
    }

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

    const queue = batch.filter((entry) => resolutions[entry.relpath] !== 'skip')

    uploading.value = true
    try {
      for (let i = 0; i < queue.length; i += 1) {
        const { file, relpath } = queue[i]
        const ext = relpath.toLowerCase().slice(relpath.lastIndexOf('.'))
        const officeHint = OFFICE_EXTS.has(ext)
          ? '（Office 檔案需轉檔，約 5–15 秒）'
          : ''
        uploadStatus.value = `正在上傳 ${i + 1}/${queue.length}：${relpath}${officeHint}`
        uploadProgressPercent.value = 0
        await uploadOne(file, relpath, resolutions[relpath] ?? null)
      }
    } finally {
      uploading.value = false
      uploadStatus.value = ''
      uploadProgressPercent.value = 0
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
        jobId.value,
        file,
        strategy,
        relpath,
        (percent) => {
          uploadProgressPercent.value = percent
        },
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
      const message = extractError(
        err,
        status === 413
          ? '超過大小上限'
          : status === 415
            ? '不支援的檔案類型'
            : status === 409
              ? '上傳被拒'
              : '上傳失敗',
      )
      ElMessage.error(`${relpath}：${message}`)
    }
  }

  return {
    uploading,
    uploadStatus,
    uploadProgressPercent,
    conflictDialogOpen,
    conflictRows,
    pendingFiles,
    pushPending,
    handleFileSelected,
    handleFileInputChange,
    handleFolderPicked,
    onConflictResolved,
  }
}
