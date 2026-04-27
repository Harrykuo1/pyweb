<script setup>
import { ref } from 'vue'
import { ElAvatar, ElButton, ElIcon, ElImage, ElMessage, ElPopconfirm, ElUpload } from 'element-plus'
import { Camera, Delete, UserFilled } from '@element-plus/icons-vue'

import PhotoCropDialog from './PhotoCropDialog.vue'
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

const cropOpen = ref(false)
const pendingFile = ref(null)

function photoSrc() {
  if (!props.member.has_photo) return null
  return membersApi.photoUrl(props.member.id, cacheBuster.value)
}

function handlePicked(uploadFile) {
  // el-upload hands us its UploadFile wrapper; native File lives at .raw.
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
  // Defer the actual upload to PhotoCropDialog so the user can frame the
  // 1:1 area locally first.
  pendingFile.value = file
  cropOpen.value = true
}

async function handleCropped(croppedFile) {
  try {
    await membersApi.uploadPhoto(props.member.id, croppedFile)
    cacheBuster.value = Date.now()
    ElMessage.success('已上傳照片')
    emit('changed')
  } catch (err) {
    if (err?.response?.status === 413) ElMessage.error('檔案過大')
    else if (err?.response?.status === 415) ElMessage.error('格式不支援')
    else ElMessage.error('上傳失敗')
  } finally {
    pendingFile.value = null
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

defineExpose({ handleDelete, handlePicked, handleCropped })
</script>

<template>
  <div class="photo-cell">
    <el-image
      v-if="member.has_photo"
      :src="photoSrc()"
      :preview-src-list="[photoSrc()]"
      :preview-teleported="true"
      :z-index="9000"
      hide-on-click-modal
      fit="cover"
      class="avatar avatar-clickable"
      :alt="`${member.real_name} 的照片`"
      data-test="photo-thumb"
    />
    <el-avatar
      v-else
      :size="48"
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
        :on-change="handlePicked"
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

    <PhotoCropDialog
      v-model="cropOpen"
      :source-file="pendingFile"
      @cropped="handleCropped"
    />
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
  width: 48px;
  height: 48px;
  border-radius: 4px;
  background: #f0f2f5;
  color: #c0c4cc;
  overflow: hidden;
}

/* el-image renders an inner <img>; cover ensures the 1:1 crop is filled
   even if the upload was a hair off. */
.avatar.avatar-clickable {
  cursor: zoom-in;
}

.avatar.avatar-clickable :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
