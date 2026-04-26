<script setup>
import { ref } from 'vue'
import { ElAvatar, ElButton, ElIcon, ElMessage, ElPopconfirm, ElUpload } from 'element-plus'
import { Camera, Delete, UserFilled } from '@element-plus/icons-vue'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  member: { type: Object, required: true },
})

const emit = defineEmits(['changed'])

const auth = useAuthStore()

// Bumping this value remounts the avatar with a fresh ?v= so the browser
// re-fetches after an upload or delete.
const cacheBuster = ref(Date.now())

function photoSrc() {
  if (!props.member.has_photo) return null
  return membersApi.photoUrl(props.member.id, cacheBuster.value)
}

async function handleUpload(uploadFile) {
  // el-upload's on-change passes its UploadFile wrapper; the native File
  // we need for FormData is at .raw.
  const file = uploadFile?.raw ?? uploadFile
  if (!file || typeof file.size !== 'number') return
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('照片大小不可超過 5 MB')
    return
  }
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    ElMessage.error('照片格式必須為 PNG / JPEG / WebP')
    return
  }
  try {
    await membersApi.uploadPhoto(props.member.id, file)
    cacheBuster.value = Date.now()
    ElMessage.success('已上傳照片')
    emit('changed')
  } catch (err) {
    if (err?.response?.status === 413) ElMessage.error('檔案過大')
    else if (err?.response?.status === 415) ElMessage.error('格式不支援')
    else ElMessage.error('上傳失敗')
  }
}

async function handleDelete() {
  try {
    await membersApi.deletePhoto(props.member.id)
    cacheBuster.value = Date.now()
    ElMessage.success('已移除照片')
    emit('changed')
  } catch (err) {
    ElMessage.error('移除失敗')
  }
}

defineExpose({ handleDelete, handleUpload })
</script>

<template>
  <div class="photo-cell">
    <el-avatar
      :size="48"
      :src="photoSrc()"
      shape="square"
      class="avatar"
    >
      <el-icon :size="24"><UserFilled /></el-icon>
    </el-avatar>

    <div v-if="auth.isAdmin" class="photo-actions">
      <el-upload
        :show-file-list="false"
        :auto-upload="false"
        accept="image/png,image/jpeg,image/webp"
        :on-change="handleUpload"
        data-test="upload-photo"
      >
        <el-button size="small" :icon="Camera" plain>
          {{ member.has_photo ? '更換' : '上傳' }}
        </el-button>
      </el-upload>
      <el-popconfirm
        v-if="member.has_photo"
        title="確定要移除這張照片嗎？"
        confirm-button-text="移除"
        cancel-button-text="取消"
        confirm-button-type="danger"
        :teleported="false"
        @confirm="handleDelete"
      >
        <template #reference>
          <el-button
            size="small"
            type="danger"
            plain
            :icon="Delete"
            data-test="delete-photo"
          />
        </template>
      </el-popconfirm>
    </div>
  </div>
</template>

<style scoped>
.photo-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.avatar {
  background: #f0f2f5;
  color: #c0c4cc;
}

.photo-actions {
  display: flex;
  gap: 4px;
}
</style>
