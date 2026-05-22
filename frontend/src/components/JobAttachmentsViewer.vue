<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElAlert, ElEmpty, ElIcon, ElMessage, ElSkeleton } from 'element-plus'
import {
  ArrowLeft,
  Close,
  Document,
  Download,
  FullScreen,
  Picture,
} from '@element-plus/icons-vue'

import {
  attachmentPreviewUrl,
  attachmentUrl,
  jobAttachmentsApi,
} from '../api/jobAttachments'

const props = defineProps({
  jobId: { type: Number, required: true },
})

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg'])
const OFFICE_EXTS = new Set(['.doc', '.docx', '.ppt', '.pptx'])

const attachments = ref([])
const loading = ref(true)
const loadError = ref(false)
const selected = ref(null)
const previewSurfaceRef = ref(null)
const isFullscreen = ref(false)

function extOf(name) {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

function isPdf(a) {
  return a.mime_type === 'application/pdf' || extOf(a.filename) === '.pdf'
}

function isImage(a) {
  return (
    (a.mime_type ?? '').startsWith('image/') ||
    IMAGE_EXTS.has(extOf(a.filename))
  )
}

function isOffice(a) {
  return OFFICE_EXTS.has(extOf(a.filename))
}

function canPreview(a) {
  // Native: browser PDF viewer / <img>. Office: only when LibreOffice
  // successfully produced a companion PDF, which the API surfaces as
  // preview_available.
  return isPdf(a) || isImage(a) || (isOffice(a) && a.preview_available)
}

function iconFor(a) {
  return isImage(a) ? Picture : Document
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function onRowClick(a, event) {
  if (canPreview(a)) {
    // Hijack the native link click so we can render the preview inside
    // the dialog instead of letting the browser navigate away.
    event.preventDefault()
    selected.value = a
    return
  }
  // For non-previewable types the anchor's `download` attribute already
  // tells the browser to save the file; let the default click run.
}

function back() {
  selected.value = null
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    attachments.value = await jobAttachmentsApi.list(props.jobId)
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function toggleFullscreen() {
  const el = previewSurfaceRef.value
  if (!el) return
  // Treat the document-level fullscreen element as the source of truth
  // so we exit no matter which element entered fullscreen.
  if (document.fullscreenElement) {
    try {
      await document.exitFullscreen()
    } catch {
      /* user gesture races etc.; the change listener will re-sync state */
    }
    return
  }
  if (typeof el.requestFullscreen !== 'function') {
    ElMessage.warning('此瀏覽器不支援全螢幕，請改用「下載」按鈕另開檔案。')
    return
  }
  try {
    await el.requestFullscreen()
  } catch {
    ElMessage.warning('無法進入全螢幕模式，請改用「下載」按鈕另開檔案。')
  }
}

function syncFullscreenState() {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  load()
  if (typeof document !== 'undefined') {
    document.addEventListener('fullscreenchange', syncFullscreenState)
  }
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('fullscreenchange', syncFullscreenState)
  }
})
</script>

<template>
  <section class="attachments-viewer" data-test="attachments-viewer">
    <el-skeleton v-if="loading" :rows="2" animated />

    <el-alert
      v-else-if="loadError"
      type="error"
      :closable="false"
      title="載入附件失敗"
      show-icon
    />

    <el-empty
      v-else-if="attachments.length === 0"
      description="尚無附件"
      :image-size="60"
    />

    <div
      v-else-if="selected"
      class="preview-pane"
      data-test="viewer-preview-pane"
    >
      <header class="preview-header">
        <button
          type="button"
          class="back-button"
          data-test="viewer-back"
          @click="back"
        >
          <el-icon :size="14"><ArrowLeft /></el-icon>
          返回列表
        </button>
        <span class="preview-name" :title="selected.filename">
          {{ selected.filename }}
        </span>
        <button
          type="button"
          class="preview-action"
          data-test="viewer-fullscreen"
          :title="isFullscreen ? '退出全螢幕（Esc）' : '全螢幕預覽'"
          @click="toggleFullscreen"
        >
          <el-icon :size="14">
            <component :is="isFullscreen ? Close : FullScreen" />
          </el-icon>
          {{ isFullscreen ? '退出全螢幕' : '全螢幕' }}
        </button>
        <a
          :href="attachmentUrl(jobId, selected.id)"
          :download="selected.filename"
          class="preview-action"
          data-test="viewer-preview-download"
        >
          <el-icon :size="14"><Download /></el-icon>
          下載
        </a>
      </header>

      <div
        ref="previewSurfaceRef"
        class="preview-surface"
        :class="{ 'is-fullscreen': isFullscreen }"
        data-test="viewer-preview-surface"
      >
        <embed
          v-if="isPdf(selected)"
          :src="attachmentUrl(jobId, selected.id)"
          type="application/pdf"
          class="pdf-embed"
          :data-test="`viewer-pdf-${selected.id}`"
        />
        <img
          v-else-if="isImage(selected)"
          :src="attachmentUrl(jobId, selected.id)"
          :alt="selected.filename"
          class="image-preview"
          :data-test="`viewer-image-${selected.id}`"
        />
        <embed
          v-else-if="isOffice(selected) && selected.preview_available"
          :src="attachmentPreviewUrl(jobId, selected.id)"
          type="application/pdf"
          class="pdf-embed"
          :data-test="`viewer-office-${selected.id}`"
        />
      </div>
    </div>

    <ul v-else class="viewer-list">
      <li
        v-for="a in attachments"
        :key="a.id"
        class="viewer-row"
        :data-test="`viewer-item-${a.id}`"
      >
        <a
          :href="attachmentUrl(jobId, a.id)"
          :download="canPreview(a) ? null : a.filename"
          class="row-link"
          :data-test="
            canPreview(a) ? `viewer-open-${a.id}` : `viewer-download-${a.id}`
          "
          @click="onRowClick(a, $event)"
        >
          <el-icon class="row-icon" :size="20">
            <component :is="iconFor(a)" />
          </el-icon>
          <div class="row-meta">
            <span class="row-name" :title="a.filename">{{ a.filename }}</span>
            <span class="row-sub">
              {{ formatSize(a.size_bytes) }}
              <span class="row-hint">
                · {{ canPreview(a) ? '點擊預覽' : '點擊下載' }}
              </span>
            </span>
          </div>
          <el-icon class="row-action" :size="14">
            <component :is="canPreview(a) ? ArrowLeft : Download" />
          </el-icon>
        </a>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.attachments-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---------- List ---------- */
.viewer-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.viewer-row {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: var(--surface-1, #f8fafc);
  transition: background-color var(--dur, 200ms) var(--ease, ease),
    border-color var(--dur, 200ms) var(--ease, ease);
}

.viewer-row:hover {
  background: rgba(99, 102, 241, 0.06);
  border-color: rgba(99, 102, 241, 0.32);
}

.row-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  text-decoration: none;
  color: inherit;
}

.row-icon {
  color: var(--ink-500, #64748b);
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

.row-sub {
  font-size: 12px;
  color: var(--ink-500, #64748b);
}

.row-hint {
  margin-left: 2px;
  color: var(--brand-primary, #6366f1);
}

.row-action {
  color: var(--ink-400, #94a3b8);
  /* Action affordance icon sits flush on the right; rotation makes the
     "preview" arrow point inward (toward content) while the download
     icon stays its natural orientation. */
}

.viewer-row .row-link:hover .row-action {
  color: var(--brand-primary, #6366f1);
}

/* ---------- Preview ---------- */
.preview-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--brand-primary, #6366f1);
  cursor: pointer;
}

.back-button:hover {
  background: rgba(99, 102, 241, 0.08);
}

.preview-name {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  color: var(--ink-900, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--brand-primary, #6366f1);
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(99, 102, 241, 0.32);
  background: transparent;
  cursor: pointer;
  font-family: inherit;
}

.preview-action:hover {
  background: rgba(99, 102, 241, 0.08);
}

.preview-surface {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 6px;
  overflow: hidden;
}

/* Browser-native fullscreen: blow the surface up to fill the viewport so
   embedded PDFs and images render at their true size. The :fullscreen
   pseudo-class only matches while the element is actually fullscreened,
   so the inline (non-fullscreen) state stays compact. */
.preview-surface:fullscreen,
.preview-surface.is-fullscreen {
  width: 100vw;
  height: 100vh;
  background: #000;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pdf-embed {
  width: 100%;
  height: 480px;
  border: 0;
  background: #fff;
}

.preview-surface:fullscreen .pdf-embed,
.preview-surface.is-fullscreen .pdf-embed {
  width: 100vw;
  height: 100vh;
}

.image-preview {
  display: block;
  max-width: 100%;
  max-height: 480px;
  margin: 0 auto;
  border-radius: 6px;
  object-fit: contain;
}

.preview-surface:fullscreen .image-preview,
.preview-surface.is-fullscreen .image-preview {
  max-width: 100vw;
  max-height: 100vh;
  border-radius: 0;
}

@media (max-width: 640px) {
  .pdf-embed {
    height: 360px;
  }
}
</style>
