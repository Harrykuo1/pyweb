<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  ElButton,
  ElIcon,
  ElInput,
  ElMessage,
  ElMessageBox,
} from 'element-plus'
import { Delete, Link, Plus, Star, VideoCamera } from '@element-plus/icons-vue'

import { eventsApi } from '../../api/events'
import { settingsApi } from '../../api/settings'
import { useMediaReorder } from '../../composables/useMediaReorder'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import { useAuthStore } from '../../stores/auth'

const props = defineProps({
  eventId: { type: Number, required: true },
})

// Admins re-authenticate with their password before deleting a photo; the
// event's author (a non-admin managing their own event) deletes without one.
const auth = useAuthStore()

// HEIC is accepted and converted server-side: iPhones shoot it by default
// and leaving it out meant rejecting a file the user had every reason to
// think was a photo.
const PHOTO_ACCEPT =
  'image/png,image/jpeg,image/webp,image/gif,image/heic,image/heif'
const VIDEO_ACCEPT = 'video/*'

// These used to be constants here, duplicating values the backend also held.
// They are admin-tunable now, so a stale copy would reject client-side what
// the server would have accepted. Defaults only cover the window before the
// config request lands.
const limits = ref({
  max_photos_per_event: 30,
  max_photo_mb: 15,
  max_videos_per_event: 5,
  max_video_mb: 240,
})

const photos = ref([])
const videos = ref([])
const loading = ref(true)
const uploading = ref(false)
const uploadStatus = ref('')
const uploadPercent = ref(0)
const fileInputRef = ref(null)
const videoInputRef = ref(null)

const atCapacity = computed(
  () => photos.value.length >= limits.value.max_photos_per_event,
)
// A failed row holds no video, so it must not count here either — the
// backend excludes it, and a mismatch would block an upload the server
// would have allowed.
const videoCount = computed(
  () => videos.value.filter((v) => v.status !== 'failed').length,
)
const atVideoCapacity = computed(
  () => videoCount.value >= limits.value.max_videos_per_event,
)

// Photos and videos are managed in one grid, matching how the detail page
// shows them. Uploading a video and then not being able to caption or delete
// it — because the manager only ever rendered photos — was the gap this
// closes.
// Drag writes an explicit order here; until then the merged list is the
// server's. Keeping it separate means a failed save can drop back to what
// the server still holds rather than leaving the grid lying.
const localOrder = ref(null)

const serverMedia = computed(() => [
  ...photos.value.map((p) => ({
    type: 'photo',
    key: `photo-${p.id}`,
    row: p,
    thumbUrl: eventsApi.photoUrl(props.eventId, p.id),
    status: 'ready',
  })),
  ...videos.value.map((v) => ({
    type: 'video',
    key: `video-${v.id}`,
    row: v,
    thumbUrl: v.youtube_id
      ? `https://img.youtube.com/vi/${v.youtube_id}/hqdefault.jpg`
      : v.has_poster
        ? eventsApi.videoPosterUrl(props.eventId, v.id)
        : null,
    status: v.status,
    isYoutube: !!v.youtube_id,
  })),
])

const mediaItems = computed(() => localOrder.value ?? serverMedia.value)

const { container: gridRef, saving: reordering } = useMediaReorder({
  getEventId: () => props.eventId,
  getItems: () => mediaItems.value,
  onReordered: (items) => {
    localOrder.value = items
  },
})

async function load() {
  loading.value = true
  try {
    const [p, v] = await Promise.all([
      eventsApi.listPhotos(props.eventId),
      eventsApi.listVideos(props.eventId),
    ])
    photos.value = p
    videos.value = v
    localOrder.value = null
  } catch {
    ElMessage.error('載入媒體失敗')
  } finally {
    loading.value = false
  }
}

async function loadLimits() {
  try {
    const config = await settingsApi.getConfig()
    for (const field of config.fields ?? []) {
      if (field.key in limits.value) limits.value[field.key] = field.value
    }
  } catch {
    // Keep the defaults; the server rejects anything over its own limit
    // regardless, so the client copy is a courtesy, not the enforcement.
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

  const room = limits.value.max_photos_per_event - photos.value.length
  const queued = files.slice(0, Math.max(0, room))
  if (files.length > queued.length) {
    ElMessage.warning(
      `最多 ${limits.value.max_photos_per_event} 張，僅上傳前 ${queued.length} 張`,
    )
  }

  uploading.value = true
  let done = 0
  try {
    for (const file of queued) {
      if (file.size > limits.value.max_photo_mb * 1024 * 1024) {
        ElMessage.warning(
          `「${file.name}」超過 ${limits.value.max_photo_mb} MB，已略過`,
        )
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
async function onCaptionBlur(item) {
  const row = item.row
  const next = (row._draftCaption ?? '').trim()
  const current = row.caption ?? ''
  if (next === current) return
  const save =
    item.type === 'video'
      ? eventsApi.updateVideoCaption
      : eventsApi.updatePhotoCaption
  try {
    const updated = await save(props.eventId, row.id, next)
    row.caption = updated.caption
    row._draftCaption = updated.caption ?? ''
  } catch {
    ElMessage.error('說明儲存失敗')
    row._draftCaption = current
  }
}

const deleteOpen = ref(false)
const deleteTarget = ref(null)
const deleteSubmitting = ref(false)
const deleteError = ref('')

function askDelete(item) {
  deleteTarget.value = item
  deleteError.value = ''
  deleteOpen.value = true
}

async function onDeleteConfirm(password) {
  const target = deleteTarget.value
  if (!target) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    const remove =
      target.type === 'video' ? eventsApi.removeVideo : eventsApi.removePhoto
    await remove(props.eventId, target.row.id, password)
    ElMessage.success(target.type === 'video' ? '已刪除影片' : '已刪除照片')
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

function pickVideo() {
  videoInputRef.value?.click()
}

async function addYoutubeLink() {
  // The upload cap is about a minute of 4K; anything longer belongs on
  // YouTube, where it costs no storage and no transcoding here.
  let url
  try {
    const { value } = await ElMessageBox.prompt(
      '貼上 YouTube 連結，長影片建議用這個方式。',
      '加入 YouTube 影片',
      {
        confirmButtonText: '加入',
        cancelButtonText: '取消',
        inputPlaceholder: 'https://youtu.be/...',
      },
    )
    url = value
  } catch {
    return // cancelled
  }
  if (!url?.trim()) return

  try {
    await eventsApi.addYoutubeVideo(props.eventId, url.trim(), null)
    ElMessage.success('已加入 YouTube 影片')
    await load()
  } catch (err) {
    const status = err?.response?.status
    if (status === 422) ElMessage.error('請貼上有效的 YouTube 連結')
    else if (status === 409) ElMessage.error('影片數量已達上限')
    else ElMessage.error('加入失敗，請稍後再試')
  }
}

async function onVideoChosen(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  if (file.size > limits.value.max_video_mb * 1024 * 1024) {
    ElMessage.warning(
      `「${file.name}」超過 ${limits.value.max_video_mb} MB，請先裁剪或降低畫質`,
    )
    return
  }

  uploading.value = true
  uploadPercent.value = 0
  uploadStatus.value = '影片上傳中…'
  try {
    await eventsApi.uploadVideo(props.eventId, file, null, (e) => {
      if (e.total) uploadPercent.value = Math.round((e.loaded / e.total) * 100)
    })
    // The row comes back as "processing" — transcoding runs server-side and
    // the grid polls for it, so the message says queued rather than done.
    ElMessage.success('影片已上傳，轉檔完成後就能播放')
    await load()
  } catch (err) {
    const status = err?.response?.status
    if (status === 413) ElMessage.error('影片檔案過大')
    else if (status === 415) ElMessage.error('不支援的影片格式')
    else if (status === 409) ElMessage.error('影片數量已達上限')
    else ElMessage.error('影片上傳失敗')
  } finally {
    uploading.value = false
    uploadPercent.value = 0
    uploadStatus.value = ''
  }
}

onMounted(() => {
  loadLimits()
  load()
})
</script>

<template>
  <div class="photos-manager" data-test="event-photos-manager">
    <div class="manager-head">
      <span class="count-hint">
        {{ photos.length }} / {{ limits.max_photos_per_event }} 張 ·
        {{ videoCount }} / {{ limits.max_videos_per_event }} 支影片
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
      <el-button
        :icon="VideoCamera"
        :disabled="atVideoCapacity || uploading"
        data-test="add-video-button"
        @click="pickVideo"
      >
        加入影片
      </el-button>
      <el-button
        :icon="Link"
        :disabled="atVideoCapacity || uploading"
        data-test="add-youtube-button"
        @click="addYoutubeLink"
      >
        YouTube 連結
      </el-button>
      <input
        ref="fileInputRef"
        type="file"
        :accept="PHOTO_ACCEPT"
        multiple
        hidden
        data-test="photo-file-input"
        @change="onFilesChosen"
      />
      <input
        ref="videoInputRef"
        type="file"
        :accept="VIDEO_ACCEPT"
        hidden
        data-test="video-file-input"
        @change="onVideoChosen"
      />
    </div>

    <ul class="manager-tip">
      <li>拖曳縮圖可調整順序，第一張照片會成為活動封面</li>
      <li>
        照片 PNG / JPG / WebP / GIF / HEIC，單張上限
        {{ limits.max_photo_mb }} MB
      </li>
      <li>影片單支上限 {{ limits.max_video_mb }} MB，上傳後需轉檔才能播放</li>
    </ul>

    <p
      v-if="uploading && uploadPercent > 0"
      class="manager-tip"
      data-test="video-upload-progress"
    >
      影片上傳中 {{ uploadPercent }}%
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

    <div v-else-if="mediaItems.length > 0" ref="gridRef" class="photo-grid">
      <figure
        v-for="(m, idx) in mediaItems"
        :key="m.key"
        class="photo-cell"
        data-test="photo-cell"
        :data-media-type="m.type"
      >
        <div
          class="photo-thumb"
          :class="{ 'is-blank': !m.thumbUrl }"
          data-drag-handle
        >
          <img
            v-if="m.thumbUrl"
            :src="m.thumbUrl"
            :alt="
              m.row.caption || (m.type === 'video' ? '活動影片' : '活動照片')
            "
            loading="lazy"
          />
          <span
            v-if="m.status === 'processing'"
            class="media-state"
            data-test="manager-processing"
          >
            轉檔中…
          </span>
          <span
            v-else-if="m.status === 'failed'"
            class="media-state is-failed"
            data-test="manager-failed"
          >
            轉檔失敗
          </span>
          <span
            v-else-if="m.type === 'video'"
            class="video-flag"
            data-test="manager-video-flag"
          >
            <el-icon :size="11"><VideoCamera /></el-icon>
            {{ m.isYoutube ? 'YouTube' : '影片' }}
          </span>

          <span v-if="idx === 0" class="cover-flag">
            <el-icon :size="11"><Star /></el-icon>
            封面
          </span>
          <button
            type="button"
            class="del-btn"
            :aria-label="m.type === 'video' ? '刪除影片' : '刪除照片'"
            data-test="delete-photo-button"
            @click="askDelete(m)"
          >
            <el-icon :size="14"><Delete /></el-icon>
          </button>
        </div>
        <el-input
          v-model="m.row._draftCaption"
          size="small"
          maxlength="200"
          placeholder="加上說明（選填）"
          class="caption-input"
          data-test="caption-input"
          @focus="
            m.row._draftCaption = m.row._draftCaption ?? m.row.caption ?? ''
          "
          @blur="onCaptionBlur(m)"
        />
      </figure>
    </div>

    <div v-else class="photos-empty" data-test="photos-empty">
      <el-icon :size="26"><Plus /></el-icon>
      <p>還沒有內容，點上方按鈕加入照片或影片。</p>
    </div>

    <DeleteWithPasswordDialog
      v-model="deleteOpen"
      title="刪除照片"
      warning="將永久刪除這張照片，此操作無法復原。"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      :require-password="auth.isActuallyAdmin"
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
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
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

/* A video tile with nothing to show yet still has to hold its shape. */
.photo-thumb {
  cursor: grab;
}

.photo-thumb:active {
  cursor: grabbing;
}

/* The placeholder Sortable leaves where the dragged cell will land. */
.media-drag-ghost {
  opacity: 0.4;
}

.photo-thumb.is-blank {
  display: grid;
  place-items: center;
  background: var(--surface-2);
}

.media-state {
  font-size: 12px;
  color: var(--ink-500);
}

.media-state.is-failed {
  color: var(--el-color-danger, #c45656);
}

.video-flag {
  position: absolute;
  left: 6px;
  bottom: 6px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 11px;
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
