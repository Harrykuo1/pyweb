import { markRaw, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

import { membersApi } from '../api/members'
import { useDeleteWithPassword } from './useDeleteWithPassword'

// Member photo flow in one place: crop-then-upload, and a
// password-confirmed remove (composed from the shared
// useDeleteWithPassword). Single dialogs are driven from here so the
// member grid's cards don't each carry their own hidden el-dialogs.
// onChanged is called after a successful upload or delete so the caller
// can reload the list.
export function useMemberPhoto({ onChanged } = {}) {
  // ---- crop + upload ----
  const cropOpen = ref(false)
  const cropFile = ref(null)
  const cropTarget = ref(null)
  const uploadingMemberId = ref(null)

  function onUploadRequest(member, file) {
    cropTarget.value = member
    cropFile.value = file
    cropOpen.value = true
  }

  async function onCropped(croppedFile) {
    const target = cropTarget.value
    if (!target) return
    uploadingMemberId.value = target.id
    const toast = ElMessage({
      message: '上傳照片中…',
      icon: markRaw(Loading),
      duration: 0,
      customClass: 'message-uploading',
    })
    try {
      await membersApi.uploadPhoto(target.id, croppedFile)
      toast.close()
      ElMessage.success('已上傳照片')
      onChanged?.()
    } catch (err) {
      toast.close()
      const status = err?.response?.status
      if (status === 413) ElMessage.error('檔案過大')
      else if (status === 415) ElMessage.error('格式不支援')
      else ElMessage.error('上傳失敗')
    } finally {
      cropFile.value = null
      cropTarget.value = null
      uploadingMemberId.value = null
    }
  }

  // ---- delete (password-confirmed) ----
  // The original used '移除失敗' copy and had no specific 404, so pin both
  // 404 and the fallback to it.
  const {
    dialogOpen: deleteDialogOpen,
    target: deleteTarget,
    submitting: deleteSubmitting,
    error: deleteError,
    open: onDeleteRequest,
    confirm: onDeleteConfirm,
  } = useDeleteWithPassword({
    remove: (member, password) => membersApi.deletePhoto(member.id, password),
    messages: { 404: '移除失敗，請稍後再試', fallback: '移除失敗，請稍後再試' },
    onSuccess: () => {
      ElMessage.success('已移除照片')
      onChanged?.()
    },
  })

  return {
    cropOpen,
    cropFile,
    cropTarget,
    uploadingMemberId,
    onUploadRequest,
    onCropped,
    deleteDialogOpen,
    deleteTarget,
    deleteSubmitting,
    deleteError,
    onDeleteRequest,
    onDeleteConfirm,
  }
}
