<script setup>
import { ref } from 'vue'
import { ElAvatar, ElButton, ElIcon, ElImage, ElMessage, ElPopconfirm, ElUpload } from 'element-plus'
import { Camera, Delete, UserFilled } from '@element-plus/icons-vue'

import PhotoCropDialog from './PhotoCropDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  member: { type: Object, required: true },
  // 'thumb' = 48px square (table cell). 'card' = fills its parent (1:1
  // aspect) with overlay admin actions in the top-right corner.
  variant: {
    type: String,
    default: 'thumb',
    validator: (v) => ['thumb', 'card'].includes(v),
  },
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
  <div :class="['photo-cell', `photo-cell--${variant}`]">
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
      :size="variant === 'card' ? 120 : 56"
      :shape="variant === 'card' ? 'square' : 'circle'"
      class="avatar"
    >
      <el-icon :size="variant === 'card' ? 48 : 26"><UserFilled /></el-icon>
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
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #eef2ff, #f3e8ff);
  color: var(--brand-primary);
  overflow: hidden;
  border: 1px solid rgba(99, 102, 241, 0.12);
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.08);
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

/* ---------- card variant: 1:1 photo at the top of a member card with
   admin actions floating in the top-right corner. ---------- */
.photo-cell--card {
  position: relative;
  width: 100%;
  gap: 0;
}

.photo-cell--card .avatar {
  width: 100%;
  height: auto;
  aspect-ratio: 1;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: linear-gradient(135deg, #eef2ff, #f3e8ff);
  color: var(--brand-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.photo-cell--card :deep(.el-avatar) {
  width: 100% !important;
  height: 100% !important;
  font-size: 48px;
}

.photo-cell--card :deep(.el-image) {
  width: 100% !important;
  height: 100% !important;
}

.photo-cell--card .photo-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  gap: 4px;
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.photo-cell--card:hover .photo-actions,
.photo-cell--card:focus-within .photo-actions {
  opacity: 1;
  transform: translateY(0);
}

/* Frosted glass background on the floating buttons so they read against
   any photo color. */
.photo-cell--card .photo-actions :deep(.el-button) {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
}
</style>
