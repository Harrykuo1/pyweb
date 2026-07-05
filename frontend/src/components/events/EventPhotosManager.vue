<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElIcon, ElInput, ElMessage } from 'element-plus'
import { Delete, Plus, Star } from '@element-plus/icons-vue'

import { eventsApi } from '../../api/events'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'

const props = defineProps({
  eventId: { type: Number, required: true },
})

const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif'
const MAX_PHOTOS = 30
const MAX_MB = 8

const photos = ref([])
const loading = ref(true)
const uploading = ref(false)
const uploadStatus = ref('')
const fileInputRef = ref(null)

const atCapacity = computed(() => photos.value.length >= MAX_PHOTOS)

async function load() {
  loading.value = true
  try {
    photos.value = await eventsApi.listPhotos(props.eventId)
  } catch {
    ElMessage.error('載入照片失敗')
  } finally {
    loading.value = false
  }
}

function thumbUrl(p) {
  return eventsApi.photoUrl(props.eventId, p.id)
}

function pickFiles() {
  fileInputRef.value?.click()
}

async function onFilesChosen(event) {
  const files = Array.from(event.target.files ?? [])
  // Reset the input so re-selecting the same file fires change again.
  event.target.value = ''
  if (files.length === 0) return

  const room = MAX_PHOTOS - photos.value.length
  const queued = files.slice(0, Math.max(0, room))
  if (files.length > queued.length) {
    ElMessage.warning(`最多 ${MAX_PHOTOS} 張，僅上傳前 ${queued.length} 張`)
  }

  uploading.value = true
  let done = 0
  try {
    for (const file of queued) {
      if (file.size > MAX_MB * 1024 * 1024) {
        ElMessage.warning(`「${file.name}」超過 ${MAX_MB} MB，已略過`)
        continue
      }
      uploadStatus.value = `上傳中 ${done + 1}/${queued.length}…`
      try {
        await eventsApi.uploadPhoto(props.eventId, file)
        done += 1
      } catch (err) {
        const status = err?.response?.status
        if (status === 415) ElMessage.error(`「${file.name}」格式不支援`)
        else if (status === 413) ElMessage.error(`「${file.name}」檔案過大`)
        else ElMessage.error(`「${file.name}」上傳失敗`)
      }
    }
    if (done > 0) {
      ElMessage.success(`已上傳 ${done} 張照片`)
      await load()
    }
  } finally {
    uploading.value = false
    uploadStatus.value = ''
  }
}

// Caption is saved on blur — only when it actually changed, to avoid a
// redundant PUT every time the field loses focus.
async function onCaptionBlur(photo) {
  const next = (photo._draftCaption ?? '').trim()
  const current = photo.caption ?? ''
  if (next === current) return
  try {
    const updated = await eventsApi.updatePhotoCaption(
      props.eventId,
      photo.id,
      next,
    )
    photo.caption = updated.caption
    photo._draftCaption = updated.caption ?? ''
  } catch {
    ElMessage.error('說明儲存失敗')
    photo._draftCaption = current
  }
}

const deleteOpen = ref(false)
const deleteTarget = ref(null)
const deleteSubmitting = ref(false)
const deleteError = ref('')

function askDelete(photo) {
  deleteTarget.value = photo
  deleteError.value = ''
  deleteOpen.value = true
}

async function onDeleteConfirm(password) {
  const target = deleteTarget.value
  if (!target) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    await eventsApi.removePhoto(props.eventId, target.id, password)
    ElMessage.success('已刪除照片')
    deleteOpen.value = false
    deleteTarget.value = null
    await load()
  } catch (err) {
    const status = err?.response?.status
    if (status === 422) deleteError.value = '密碼錯誤'
    else if (status === 403) deleteError.value = '權限不足'
    else deleteError.value = '刪除失敗，請稍後再試'
  } finally {
    deleteSubmitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="photos-manager" data-test="event-photos-manager">
    <div class="manager-head">
      <span class="count-hint">
        {{ photos.length }} / {{ MAX_PHOTOS }} 張
      </span>
      <el-button
        type="primary"
        :icon="Plus"
        :disabled="atCapacity || uploading"
        :loading="uploading"
        data-test="add-photos-button"
        @click="pickFiles"
      >
        {{ uploading ? uploadStatus || '上傳中…' : '加入照片' }}
      </el-button>
      <input
        ref="fileInputRef"
        type="file"
        :accept="ACCEPT"
        multiple
        hidden
        data-test="photo-file-input"
        @change="onFilesChosen"
      />
    </div>

    <p class="manager-tip">
      第一張照片會成為活動封面。支援 PNG / JPG / WebP / GIF，單張上限
      {{ MAX_MB }} MB。
    </p>

    <div v-if="loading" class="photo-grid">
      <div
        v-for="i in 3"
        :key="`skel-${i}`"
        class="photo-cell photo-cell--skel"
      >
        <div class="skel-img shimmer"></div>
      </div>
    </div>

    <div v-else-if="photos.length > 0" class="photo-grid">
      <figure
        v-for="(p, idx) in photos"
        :key="p.id"
        class="photo-cell"
        data-test="photo-cell"
      >
        <div class="photo-thumb">
          <img
            :src="thumbUrl(p)"
            :alt="p.caption || '活動照片'"
            loading="lazy"
          />
          <span v-if="idx === 0" class="cover-flag">
            <el-icon :size="11"><Star /></el-icon>
            封面
          </span>
          <button
            type="button"
            class="del-btn"
            aria-label="刪除照片"
            data-test="delete-photo-button"
            @click="askDelete(p)"
          >
            <el-icon :size="14"><Delete /></el-icon>
          </button>
        </div>
        <el-input
          v-model="p._draftCaption"
          size="small"
          maxlength="200"
          placeholder="加上說明（選填）"
          class="caption-input"
          data-test="caption-input"
          @focus="p._draftCaption = p._draftCaption ?? p.caption ?? ''"
          @blur="onCaptionBlur(p)"
        />
      </figure>
    </div>

    <div v-else class="photos-empty" data-test="photos-empty">
      <el-icon :size="26"><Plus /></el-icon>
      <p>還沒有照片，點「加入照片」開始上傳。</p>
    </div>

    <DeleteWithPasswordDialog
      v-model="deleteOpen"
      title="刪除照片"
      warning="將永久刪除這張照片，此操作無法復原。"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      @confirm="onDeleteConfirm"
    />
  </div>
</template>

<style scoped>
.photos-manager {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manager-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.count-hint {
  font-size: 12px;
  color: var(--ink-500);
  font-variant-numeric: tabular-nums;
}

.manager-tip {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.6;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.photo-cell {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.photo-thumb {
  position: relative;
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface-2);
  border: 1px solid rgba(15, 23, 42, 0.08);
}

.photo-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.cover-flag {
  position: absolute;
  top: 6px;
  left: 6px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(
    135deg,
    var(--accent-warm-from),
    var(--accent-warm-to)
  );
  box-shadow: 0 2px 6px rgba(244, 63, 94, 0.35);
}

.del-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  cursor: pointer;
  opacity: 0;
  transition:
    opacity var(--dur) var(--ease),
    background var(--dur) var(--ease);
}

.photo-thumb:hover .del-btn,
.del-btn:focus-visible {
  opacity: 1;
}

.del-btn:hover {
  background: #ef4444;
}

.caption-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
}

.photo-cell--skel .skel-img {
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-md);
  background: rgba(15, 23, 42, 0.06);
}

.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  to {
    transform: translateX(100%);
  }
}

.photos-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 16px;
  color: var(--ink-500);
  border: 1px dashed rgba(15, 23, 42, 0.14);
  border-radius: var(--radius-md);
  text-align: center;
}

.photos-empty p {
  margin: 0;
  font-size: 13px;
}
</style>
