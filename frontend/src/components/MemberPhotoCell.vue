<script setup>
import { ElAvatar, ElButton, ElIcon, ElImage, ElMessage, ElUpload } from 'element-plus'
import { Camera, Delete, Loading, UserFilled } from '@element-plus/icons-vue'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  member: { type: Object, required: true },
  // 'thumb' = 56px circular (table cell). 'card' = fills its parent (1:1
  // aspect) with overlay admin actions in the top-right corner.
  variant: {
    type: String,
    default: 'thumb',
    validator: (v) => ['thumb', 'card'].includes(v),
  },
  // Set by the parent while this member's photo is mid-upload — drives
  // the dim veil + spinner overlay on top of the photo.
  uploading: { type: Boolean, default: false },
})

const emit = defineEmits(['request-upload', 'request-delete'])

const auth = useAuthStore()

function photoSrc() {
  if (!props.member.has_photo) return null
  return membersApi.photoUrl(props.member.id, props.member.photo_updated_at ?? '')
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
  // Hand the validated File up to Members.vue, which owns the single
  // page-level PhotoCropDialog + upload pipeline. (Previously each
  // cell mounted its own dialogs, which made a 50-card grid carry
  // ~100 hidden el-dialogs in the DOM.)
  emit('request-upload', props.member, file)
}

function handleDeleteClick() {
  emit('request-delete', props.member)
}
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

    <div v-if="uploading" class="upload-overlay" data-test="photo-uploading">
      <el-icon class="is-loading" :size="variant === 'card' ? 32 : 18">
        <Loading />
      </el-icon>
      <span v-if="variant === 'card'" class="overlay-text">上傳中…</span>
    </div>

    <div v-if="auth.isAdmin && !uploading" class="photo-actions">
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
      <el-button
        v-if="member.has_photo"
        size="small"
        type="danger"
        plain
        :icon="Delete"
        data-test="delete-photo"
        aria-label="移除照片"
        title="移除照片"
        @click="handleDeleteClick"
      />
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

/* Upload-in-progress veil. Sits over the photo (and the actions are
   hidden while uploading) so users see something is happening even
   while the network request is in flight. */
.upload-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(15, 23, 42, 0.5);
  color: #ffffff;
  border-radius: inherit;
  pointer-events: none;
  z-index: 2;
}

.photo-cell--thumb {
  position: relative;
}

.photo-cell--thumb .upload-overlay {
  border-radius: 50%;
  width: 56px;
  height: 56px;
}

.photo-cell--card .upload-overlay {
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.overlay-text {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
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
