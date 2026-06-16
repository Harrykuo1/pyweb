<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ElAlert,
  ElEmpty,
  ElIcon,
  ElImageViewer,
  ElMessage,
  ElSkeleton,
} from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  Close,
  Document,
  Download,
  Folder,
  FullScreen,
  Picture,
  View,
  ZoomIn,
} from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import {
  attachmentPreviewUrl,
  attachmentUrl,
  jobAttachmentsApi,
} from '../../api/jobAttachments'
import {
  breadcrumbSegments as buildBreadcrumb,
  buildListing,
} from '../../utils/attachmentTree'

const props = defineProps({
  jobId: { type: Number, required: true },
})

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp'])
const OFFICE_EXTS = new Set(['.doc', '.docx', '.ppt', '.pptx'])
const MARKDOWN_EXTS = new Set(['.md', '.markdown'])
// Plain-text extensions we'll render inside a <pre> block. Source-code
// files belong here too, just without syntax highlighting — readable
// monospace is enough to preview a config / log / snippet without
// reaching for a download. md sits in MARKDOWN_EXTS because it has a
// rendered alternative; everything else is source-only.
const TEXT_EXTS = new Set([
  '.txt', '.log', '.json', '.csv', '.xml',
  '.yml', '.yaml', '.ini', '.toml', '.env',
  '.html', '.htm', '.css', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx',
  '.vue', '.svelte',
  '.py', '.rb', '.go', '.rs', '.java', '.kt', '.swift',
  '.c', '.h', '.cc', '.cpp', '.hpp',
  '.sh', '.bash', '.zsh', '.fish',
  '.sql', '.php', '.lua', '.r', '.scala',
  '.dockerfile', '.gitignore', '.editorconfig',
])
// 2 MB hard cap on inline text preview. A 50 MB log file rendered as
// one giant <pre> nukes the page; force a download instead.
const TEXT_PREVIEW_MAX_BYTES = 2 * 1024 * 1024

const attachments = ref([])
const loading = ref(true)
const loadError = ref(false)
// "" = root. Otherwise a forward-slash path matching the prefix of
// the attachment filenames at this level (e.g. "src/components").
const currentPath = ref('')
const selected = ref(null)
const previewSurfaceRef = ref(null)
const isFullscreen = ref(false)

// Text-preview state — populated when a markdown/plain-text file is
// selected, cleared on back/navigate-away. textMode toggles between
// 'rendered' (MdPreview) and 'source' (raw) for markdown files only.
const textContent = ref('')
const textLoading = ref(false)
const textError = ref('')
const textMode = ref('rendered')

// ElImageViewer toggle. When the user clicks the inline image preview
// (or hits the 放大 button), we mount the viewer with the current
// folder's image set so left/right keys cycle through siblings.
const imageViewerOpen = ref(false)

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

function isMarkdown(a) {
  return MARKDOWN_EXTS.has(extOf(a.filename))
}

function isTextFile(a) {
  const ext = extOf(a.filename)
  return MARKDOWN_EXTS.has(ext) || TEXT_EXTS.has(ext)
}

function canPreviewText(a) {
  // Anything over the cap falls back to download — rendering a 50 MB
  // log inline freezes the page and helps no one.
  return isTextFile(a) && a.size_bytes <= TEXT_PREVIEW_MAX_BYTES
}

function canPreview(a) {
  // Native: browser PDF viewer / <img>. Office: only when OnlyOffice
  // successfully produced a companion PDF, which the API surfaces as
  // preview_available. Text/markdown: fetched and rendered inline, but
  // only under the 2 MB guardrail.
  return (
    isPdf(a)
    || isImage(a)
    || (isOffice(a) && a.preview_available)
    || canPreviewText(a)
  )
}

function iconFor(a) {
  return isImage(a) ? Picture : Document
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const currentListing = computed(() =>
  buildListing(attachments.value, currentPath.value),
)
const breadcrumbSegments = computed(() => buildBreadcrumb(currentPath.value))

// All images in the current folder view, in the same order as the
// row listing. Feeds ElImageViewer so its built-in ◀/▶ navigation
// jumps between siblings rather than just showing the one image.
const imageUrlsAtCurrentView = computed(() =>
  currentListing.value.files
    .map((entry) => entry.attachment)
    .filter(isImage)
    .map((a) => attachmentUrl(props.jobId, a.id)),
)

const selectedImageIndex = computed(() => {
  if (!selected.value || !isImage(selected.value)) return 0
  const url = attachmentUrl(props.jobId, selected.value.id)
  const idx = imageUrlsAtCurrentView.value.indexOf(url)
  return idx < 0 ? 0 : idx
})

function enterFolder(folderName) {
  currentPath.value = currentPath.value
    ? `${currentPath.value}/${folderName}`
    : folderName
}

function jumpToPath(path) {
  currentPath.value = path
}

function onFileClick(a, event) {
  if (canPreview(a)) {
    // Hijack the native link click so we can render the preview inside
    // the dialog instead of letting the browser navigate away.
    event.preventDefault()
    selected.value = a
    if (isTextFile(a)) {
      loadTextPreview(a)
    }
    return
  }
  // For non-previewable types the anchor's `download` attribute already
  // tells the browser to save the file; let the default click run.
}

function back() {
  selected.value = null
  textContent.value = ''
  textError.value = ''
  textMode.value = 'rendered'
}

async function loadTextPreview(a) {
  textLoading.value = true
  textError.value = ''
  textContent.value = ''
  textMode.value = isMarkdown(a) ? 'rendered' : 'source'
  try {
    // Fetch via the same /api/jobs/{id}/attachments/{id} endpoint as
    // download — Content-Disposition: attachment doesn't matter for
    // body bytes, so a single download URL serves both flows.
    const response = await fetch(attachmentUrl(props.jobId, a.id), {
      credentials: 'same-origin',
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    textContent.value = await response.text()
  } catch {
    textError.value = '載入文字內容失敗，請改用「下載」按鈕。'
  } finally {
    textLoading.value = false
  }
}

// Reset text mode whenever the user picks a fresh attachment.
watch(selected, (next, prev) => {
  if (!next || next?.id !== prev?.id) {
    textMode.value = next && isMarkdown(next) ? 'rendered' : 'source'
  }
})

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
          v-if="isImage(selected)"
          type="button"
          class="preview-action"
          data-test="viewer-image-zoom"
          title="放大檢視 — 支援縮放、旋轉、左右切換"
          @click="imageViewerOpen = true"
        >
          <el-icon :size="14"><ZoomIn /></el-icon>
          放大
        </button>
        <button
          v-if="isMarkdown(selected)"
          type="button"
          class="preview-action"
          data-test="viewer-text-toggle"
          :title="textMode === 'rendered' ? '查看原始碼' : '回到渲染畫面'"
          @click="textMode = textMode === 'rendered' ? 'source' : 'rendered'"
        >
          <el-icon :size="14">
            <component :is="textMode === 'rendered' ? Document : View" />
          </el-icon>
          {{ textMode === 'rendered' ? '原始碼' : '渲染' }}
        </button>
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
          class="image-preview is-clickable"
          :data-test="`viewer-image-${selected.id}`"
          title="點擊放大檢視（支援縮放、旋轉、左右切換）"
          @click="imageViewerOpen = true"
        />
        <embed
          v-else-if="isOffice(selected) && selected.preview_available"
          :src="attachmentPreviewUrl(jobId, selected.id)"
          type="application/pdf"
          class="pdf-embed"
          :data-test="`viewer-office-${selected.id}`"
        />
        <div
          v-else-if="isTextFile(selected)"
          class="text-preview"
          :data-test="`viewer-text-${selected.id}`"
        >
          <el-skeleton
            v-if="textLoading"
            :rows="6"
            animated
            data-test="viewer-text-loading"
          />
          <el-alert
            v-else-if="textError"
            type="error"
            :closable="false"
            :title="textError"
            show-icon
            data-test="viewer-text-error"
          />
          <MdPreview
            v-else-if="isMarkdown(selected) && textMode === 'rendered'"
            :model-value="textContent"
            theme="light"
            data-test="viewer-text-rendered"
          />
          <pre
            v-else
            class="text-source"
            data-test="viewer-text-source"
          >{{ textContent }}</pre>
        </div>
      </div>
    </div>

    <div v-else class="folder-browser" data-test="folder-browser">
      <nav class="breadcrumb" aria-label="附件路徑" data-test="breadcrumb">
        <template
          v-for="(seg, i) in breadcrumbSegments"
          :key="`bc-${i}-${seg.path}`"
        >
          <span v-if="i > 0" class="breadcrumb-sep" aria-hidden="true">
            <el-icon :size="11"><ArrowRight /></el-icon>
          </span>
          <button
            v-if="i < breadcrumbSegments.length - 1"
            type="button"
            class="breadcrumb-item is-clickable"
            :data-test="`breadcrumb-${i}`"
            @click="jumpToPath(seg.path)"
          >
            {{ seg.name }}
          </button>
          <span
            v-else
            class="breadcrumb-item is-current"
            :data-test="`breadcrumb-current`"
          >
            {{ seg.name }}
          </span>
        </template>
      </nav>

      <ul class="viewer-list">
        <li
          v-for="folder in currentListing.folders"
          :key="`folder:${folder.name}`"
          class="viewer-row folder-row"
          :data-test="`viewer-folder-${folder.name}`"
          @click="enterFolder(folder.name)"
        >
          <el-icon class="row-icon folder-icon" :size="22"><Folder /></el-icon>
          <div class="row-meta">
            <span class="row-name">{{ folder.name }}</span>
            <span class="row-sub">{{ folder.count }} 個檔案</span>
          </div>
          <el-icon class="row-action" :size="14"><ArrowRight /></el-icon>
        </li>

        <li
          v-for="entry in currentListing.files"
          :key="`file:${entry.attachment.id}`"
          class="viewer-row file-row"
          :data-test="`viewer-item-${entry.attachment.id}`"
        >
          <a
            :href="attachmentUrl(jobId, entry.attachment.id)"
            :download="
              canPreview(entry.attachment) ? null : entry.attachment.filename
            "
            class="row-link"
            :data-test="
              canPreview(entry.attachment)
                ? `viewer-open-${entry.attachment.id}`
                : `viewer-download-${entry.attachment.id}`
            "
            @click="onFileClick(entry.attachment, $event)"
          >
            <el-icon class="row-icon" :size="20">
              <component :is="iconFor(entry.attachment)" />
            </el-icon>
            <div class="row-meta">
              <span class="row-name" :title="entry.displayName">
                {{ entry.displayName }}
              </span>
              <span class="row-sub">
                {{ formatSize(entry.attachment.size_bytes) }}
                <span class="row-hint">
                  · {{ canPreview(entry.attachment) ? '點擊預覽' : '點擊下載' }}
                </span>
              </span>
            </div>
            <el-icon class="row-action" :size="14">
              <component
                :is="canPreview(entry.attachment) ? ArrowRight : Download"
              />
            </el-icon>
          </a>
        </li>
      </ul>
    </div>

    <!-- Modal image viewer for the click-to-zoom path. teleported so
         it escapes the parent dialog's overflow/z-index stacking. The
         url-list spans every image at the current folder view, so the
         viewer's built-in left/right arrows (and keyboard nav) flip
         through siblings without re-opening the modal. -->
    <ElImageViewer
      v-if="imageViewerOpen && imageUrlsAtCurrentView.length > 0"
      :url-list="imageUrlsAtCurrentView"
      :initial-index="selectedImageIndex"
      hide-on-click-modal
      teleported
      data-test="viewer-image-modal"
      @close="imageViewerOpen = false"
    />
  </section>
</template>

<style scoped>
.attachments-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---------- Breadcrumb ---------- */
.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 8px;
  font-size: 13px;
}

.breadcrumb-item {
  border: 0;
  background: transparent;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  color: var(--brand-primary, #6366f1);
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.breadcrumb-item.is-clickable:hover {
  background: rgba(99, 102, 241, 0.12);
}

.breadcrumb-item.is-current {
  color: var(--ink-900, #0f172a);
  font-weight: 500;
  cursor: default;
}

.breadcrumb-sep {
  display: inline-flex;
  align-items: center;
  color: var(--ink-400, #94a3b8);
  margin: 0 2px;
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

/* Folder row is a direct <li> click target — no <a> wrapper because
   it's not a download/navigation; it just shifts the current path. */
.folder-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  cursor: pointer;
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

.folder-icon {
  /* Slightly larger and brand-tinted so folders read as containers,
     not "another file row with a different icon". */
  color: var(--brand-primary, #6366f1);
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
}

.viewer-row:hover .row-action,
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

.image-preview.is-clickable {
  cursor: zoom-in;
}

.preview-surface:fullscreen .image-preview,
.preview-surface.is-fullscreen .image-preview {
  max-width: 100vw;
  max-height: 100vh;
  border-radius: 0;
}

/* ---------- Text / Markdown preview ---------- */
.text-preview {
  width: 100%;
  max-height: 480px;
  overflow: auto;
  padding: 14px 16px;
  background: #fff;
}

.text-source {
  margin: 0;
  font-family: var(--font-mono, 'JetBrains Mono', Menlo, Consolas, monospace);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--ink-900, #0f172a);
  white-space: pre-wrap;
  word-break: break-word;
}

/* md-editor-v3's preview container forces its own padding & background.
   Strip them so the surface frame from .text-preview wins, otherwise
   the markdown body has a doubled inner border. */
.text-preview :deep(.md-editor-preview-wrapper) {
  padding: 0;
}

.text-preview :deep(.md-editor-preview) {
  background: transparent;
}

/* Fullscreen treatment for text/markdown: the surface element flips to
   100vw/100vh (per the rules above), and the text panel itself goes
   edge-to-edge inside it. Center the content column on wide screens so
   markdown isn't a single river spanning a 4K monitor. */
.preview-surface:fullscreen .text-preview,
.preview-surface.is-fullscreen .text-preview {
  max-height: none;
  height: 100vh;
  width: 100vw;
  padding: 32px max(48px, calc((100vw - 920px) / 2));
  background: #ffffff;
  overflow: auto;
}

.preview-surface:fullscreen .text-source,
.preview-surface.is-fullscreen .text-source {
  font-size: 14px;
  line-height: 1.7;
}

@media (max-width: 640px) {
  .pdf-embed {
    height: 360px;
  }
  .text-preview {
    max-height: 360px;
  }
}
</style>
