import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { jobAttachmentsApi } from '../api/jobAttachments'

// Password-confirmed delete engine for attachments. The three entry points
// (single file, whole folder, multi-select bulk) all build a descriptor
// and funnel through one dialog; this composable owns that dialog's state,
// runs the right API call by mode, removes the rows from the shared
// attachments ref, and maps the backend status to a message. Descriptor
// construction (which knows about folders and the selection) stays with the
// caller, as does post-delete cleanup via onDeleted(pending).
//
// A descriptor is { mode: 'single' | 'bulk', ids, title, itemName, warning,
// successMsg } — title/itemName/warning drive the dialog copy.
export function useAttachmentDelete({ jobId, attachments, onDeleted }) {
  const deleteDialogOpen = ref(false)
  const deleteSubmitting = ref(false)
  const deleteError = ref('')
  const pendingDelete = ref(null)

  function openDeleteDialog(descriptor) {
    pendingDelete.value = descriptor
    deleteError.value = ''
    deleteDialogOpen.value = true
  }

  async function onDeleteConfirm(password) {
    const pending = pendingDelete.value
    if (!pending) return
    deleteSubmitting.value = true
    deleteError.value = ''
    try {
      if (pending.mode === 'single') {
        await jobAttachmentsApi.remove(jobId.value, pending.ids[0], password)
      } else {
        await jobAttachmentsApi.bulkRemove(jobId.value, pending.ids, password)
      }
      const idSet = new Set(pending.ids)
      attachments.value = attachments.value.filter((a) => !idSet.has(a.id))
      onDeleted?.(pending)
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

  return {
    deleteDialogOpen,
    deleteSubmitting,
    deleteError,
    pendingDelete,
    openDeleteDialog,
    onDeleteConfirm,
  }
}
