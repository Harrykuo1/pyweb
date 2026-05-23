<script setup>
import { computed, markRaw, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElIcon,
  ElMessage,
  ElSegmented,
  ElUpload,
} from 'element-plus'
import {
  Calendar,
  Close,
  Delete,
  Document,
  Loading,
  Reading,
  School,
  Upload,
  User,
} from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'changed'])

const auth = useAuthStore()

const tab = ref('pdf')
const uploadingPdf = ref(false)

const availableFormats = computed(() => {
  if (!props.member) return []
  const list = []
  if (props.member.has_resume_pdf) list.push({ label: 'PDF', value: 'pdf' })
  if (props.member.has_resume_md) list.push({ label: 'Markdown', value: 'md' })
  return list
})

const photoSrc = computed(() => {
  if (!props.member?.has_photo) return ''
  return membersApi.photoUrl(props.member.id, props.member.photo_updated_at ?? '')
})

function formatJoinDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const pdfSrc = computed(() => {
  if (!props.member) return ''
  // Tell the browser's built-in PDF viewer to drop its toolbar and side
  // navigation pane, and fit the page to the iframe width. Chromium-based
  // browsers (Chrome / Edge) respect these fragment parameters; others
  // ignore them and fall back to their defaults.
  const url = membersApi.resumePdfUrl(
    props.member.id,
    props.member.resume_pdf_updated_at ?? '',
  )
  return `${url}#toolbar=0&navpanes=0&view=FitH`
})

watch(
  () => [props.modelValue, props.member?.id, props.member?.has_resume_pdf, props.member?.has_resume_md],
  ([open]) => {
    if (!open || !props.member) return
    if (props.member.has_resume_pdf) tab.value = 'pdf'
    else if (props.member.has_resume_md) tab.value = 'md'
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

async function handleUploadPdf(uploadFile) {
  if (!props.member) return
  // el-upload's on-change passes its UploadFile wrapper; .raw holds the
  // native File needed for FormData.
  const file = uploadFile?.raw ?? uploadFile
  if (!file || typeof file.size !== 'number') return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('PDF 不可超過 10 MB')
    return
  }
  if (file.type !== 'application/pdf') {
    ElMessage.error('檔案必須是 PDF')
    return
  }
  uploadingPdf.value = true
  const toast = ElMessage({
    message: '上傳履歷 PDF 中…',
    icon: markRaw(Loading),
    duration: 0,
    customClass: 'message-uploading',
  })
  try {
    await membersApi.uploadResumePdf(props.member.id, file)
    toast.close()
    ElMessage.success('已上傳履歷 PDF')
    tab.value = 'pdf'
    emit('changed')
  } catch (err) {
    toast.close()
    if (err?.response?.status === 413) ElMessage.error('檔案過大')
    else if (err?.response?.status === 415) ElMessage.error('格式不支援')
    else ElMessage.error('上傳失敗')
  } finally {
    uploadingPdf.value = false
  }
}

// ---------- Delete PDF with admin-password confirmation ----------
const deletePdfDialogOpen = ref(false)
const deletePdfSubmitting = ref(false)
const deletePdfError = ref('')

function askDeletePdf() {
  deletePdfError.value = ''
  deletePdfDialogOpen.value = true
}

async function handleDeletePdf(password) {
  if (!props.member) return
  deletePdfSubmitting.value = true
  deletePdfError.value = ''
  try {
    await membersApi.deleteResumePdf(props.member.id, password)
    ElMessage.success('已刪除履歷 PDF')
    deletePdfDialogOpen.value = false
    emit('changed')
    if (props.member.has_resume_md) {
      tab.value = 'md'
    }
  } catch (err) {
    const status = err?.response?.status
    if (status === 422) deletePdfError.value = '密碼錯誤'
    else if (status === 403) deletePdfError.value = '權限不足'
    else deletePdfError.value = '刪除失敗，請稍後再試'
  } finally {
    deletePdfSubmitting.value = false
  }
}

defineExpose({ handleUploadPdf, handleDeletePdf, askDeletePdf })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title=""
    :fullscreen="true"
    modal-class="resume-overlay"
    :show-close="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <header v-if="member" class="resume-hero">
      <button
        type="button"
        class="hero-close"
        aria-label="關閉"
        @click="close"
      >
        <el-icon :size="18"><Close /></el-icon>
      </button>
      <div class="hero-photo-frame">
        <img v-if="member.has_photo" :src="photoSrc" alt="" />
        <el-icon v-else :size="44"><User /></el-icon>
      </div>
      <div class="hero-text">
        <h2 class="hero-name">{{ member.real_name }}</h2>
        <p v-if="member.institution" class="hero-position">
          {{ member.institution }}<span v-if="member.position"> · {{ member.position }}</span>
        </p>
        <div class="hero-meta">
          <span class="meta-pill">
            <el-icon :size="13"><School /></el-icon>
            {{ member.graduation_year }} 年畢業
          </span>
          <span v-if="member.joined_at" class="meta-pill">
            <el-icon :size="13"><Calendar /></el-icon>
            {{ formatJoinDate(member.joined_at) }} 入群
          </span>
        </div>
      </div>
    </header>

    <div v-if="member" class="resume-viewer">
      <div v-if="availableFormats.length > 1" class="format-cards">
        <button
          v-for="fmt in availableFormats"
          :key="fmt.value"
          type="button"
          :class="['format-card', { 'is-active': tab === fmt.value }]"
          :data-test="`format-card-${fmt.value}`"
          @click="tab = fmt.value"
        >
          <span class="format-card__icon">
            <el-icon :size="20">
              <Document v-if="fmt.value === 'pdf'" />
              <Reading v-else />
            </el-icon>
          </span>
          <span class="format-card__text">
            <span class="format-card__title">{{ fmt.label }}</span>
            <span class="format-card__subtitle">
              {{ fmt.value === 'pdf' ? '原始 PDF 履歷' : '格式化 Markdown 履歷' }}
            </span>
          </span>
        </button>
      </div>

      <div class="viewer-body" :class="{ 'is-pdf': tab === 'pdf' && availableFormats.length }">
        <div v-if="availableFormats.length === 0" class="empty-state">
          <el-empty description="尚未上傳履歷" />
        </div>

        <iframe
          v-else-if="tab === 'pdf'"
          :src="pdfSrc"
          class="pdf-frame"
          data-test="pdf-frame"
        />

        <div v-else-if="tab === 'md'" class="md-frame" data-test="md-preview">
          <MdPreview :model-value="member.resume_md ?? ''" theme="light" />
        </div>
      </div>
    </div>

    <template #footer>
      <div class="footer-row">
        <div class="footer-admin">
          <template v-if="auth.isAdmin && member">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="application/pdf"
              :on-change="handleUploadPdf"
              :disabled="uploadingPdf"
              data-test="upload-pdf"
            >
              <el-button
                :icon="uploadingPdf ? null : Upload"
                size="small"
                plain
                :loading="uploadingPdf"
                :disabled="uploadingPdf"
              >
                {{ uploadingPdf
                  ? '上傳中…'
                  : (member.has_resume_pdf ? '替換 PDF' : '上傳 PDF') }}
              </el-button>
            </el-upload>
            <el-button
              v-if="member.has_resume_pdf"
              :icon="Delete"
              size="small"
              type="danger"
              plain
              :disabled="uploadingPdf"
              data-test="delete-pdf"
              @click="askDeletePdf"
            >
              刪除 PDF
            </el-button>
          </template>
        </div>
        <el-button @click="close">關閉</el-button>
      </div>
    </template>
  </el-dialog>

  <DeleteWithPasswordDialog
    v-model="deletePdfDialogOpen"
    title="刪除履歷 PDF"
    :item-name="member?.real_name ?? ''"
    warning="將永久刪除這位成員的 PDF 履歷檔。此操作無法復原。"
    :loading="deletePdfSubmitting"
    :error-message="deletePdfError"
    @confirm="handleDeletePdf"
  />
</template>

<!-- Unscoped: the rules below target EP's overlay/dialog tree via
     modal-class="resume-overlay" (an explicit prop, applied to .el-overlay).
     A scoped data-v hash wouldn't reach those nested wrappers. -->
<style>
/* Pin the dialog to the viewport directly with position:fixed + top/bottom.
   :fullscreen gives us the .is-fullscreen class hook; we override width and
   chrome to keep the normal dialog look. modal-class lands on .el-overlay
   synchronously so we don't need the class on .el-dialog itself. */
.resume-overlay .el-dialog.is-fullscreen {
  position: fixed !important;
  top: 1vh !important;
  bottom: 1vh !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  margin: 0 !important;
  width: 1100px !important;
  max-width: 95vw !important;
  height: auto !important;
  /* style.css applies max-height: 88vh to every .el-dialog as a global
     viewport cap. That caps this dialog before top/bottom anchoring can
     stretch it, so we lift the cap for this one. */
  max-height: none !important;
  border-radius: 16px !important;
  overflow: hidden !important;
  display: flex;
  flex-direction: column;
}

/* The custom hero replaces the EP title bar entirely. */
.resume-overlay .el-dialog__header {
  display: none;
}

.resume-overlay .el-dialog__body {
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.resume-overlay .el-dialog__footer {
  padding: 16px 24px;
  border-top: 1px solid #f2f3f5;
  flex-shrink: 0;
}
</style>

<style scoped>

.resume-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  padding: 16px 24px 0;
}

/* ---------- Hero banner ---------- */

/* Bleed to the dialog edges (the body now has padding: 0 to allow this).
   Gradient + soft radial highlights echo the brand palette and lift the
   dialog from "blank window with tabs" into "this is so-and-so's resume". */
.resume-hero {
  position: relative;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 32px 36px;
  /* Layered: dot grain on top, then base gradient — gives the panel
     more material depth than a flat candy gradient. */
  background:
    radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px) 0 0 / 22px 22px,
    linear-gradient(135deg, #4f46e5 0%, #7c3aed 45%, #c026d3 100%);
  color: #ffffff;
  overflow: hidden;
}

.resume-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.22), transparent 55%),
    radial-gradient(circle at 82% 100%, rgba(255, 255, 255, 0.12), transparent 55%);
  pointer-events: none;
}

/* Right-side decorative wordmark. Sits behind the text (z-index 0) and
   stretches across the empty area to balance the photo+text on the left.
   Letterspacing pulled tight so it reads as a graphic, not a label. */
.resume-hero::after {
  content: 'RESUME';
  position: absolute;
  top: 50%;
  right: 32px;
  transform: translateY(-50%);
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 108px;
  font-weight: 900;
  letter-spacing: -5px;
  color: rgba(255, 255, 255, 0.09);
  line-height: 1;
  pointer-events: none;
  z-index: 0;
  white-space: nowrap;
}

.hero-photo-frame {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  border: 3px solid rgba(255, 255, 255, 0.7);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.25);
  flex-shrink: 0;
  z-index: 1;
}

.hero-photo-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-photo-frame :deep(.el-icon) {
  color: rgba(255, 255, 255, 0.8);
}

.hero-text {
  position: relative;
  flex: 1;
  min-width: 0;
  z-index: 1;
}

.hero-name {
  margin: 0 0 6px;
  font-size: 34px;
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.5px;
  /* Force white over the gradient — EP's global h2 rule otherwise wins
     against the inherited #ffffff from .resume-hero. */
  color: #ffffff;
}

.hero-position {
  margin: 0 0 12px;
  font-size: 15px;
  opacity: 0.92;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
}

.hero-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 34px;
  height: 34px;
  border: 0;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 50%;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
  z-index: 2;
}

.hero-close:hover {
  background: rgba(255, 255, 255, 0.32);
}

/* ---------- Format chooser cards ---------- */
.format-cards {
  display: flex;
  gap: 12px;
}

.format-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  background: #ffffff;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s,
    transform 0.2s;
}

.format-card:hover:not(.is-active) {
  border-color: #c4b5fd;
  background: #faf8ff;
  transform: translateY(-1px);
}

.format-card.is-active {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 8px 22px rgba(99, 102, 241, 0.32);
}

.format-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #f0eaff;
  color: #6366f1;
  flex-shrink: 0;
  transition: background 0.2s, color 0.2s;
}

.format-card.is-active .format-card__icon {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
}

.format-card__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.format-card__title {
  font-weight: 600;
  font-size: 15px;
}

.format-card__subtitle {
  font-size: 12px;
  opacity: 0.72;
}


.viewer-body {
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
  flex: 1;
  min-height: 0;
  display: flex;
}

.viewer-body.is-pdf {
  background: #525659;
  border-color: #525659;
}

.pdf-frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}

.md-frame {
  flex: 1;
  padding: 24px 32px;
  overflow: auto;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.footer-admin {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---------- Mobile ---------- */
@media (max-width: 640px) {
  .resume-hero {
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
    padding: 24px 20px 22px;
    gap: 14px;
  }

  .resume-hero::after {
    font-size: 72px;
    right: 16px;
    bottom: 12px;
    top: auto;
    transform: none;
  }

  .hero-photo-frame {
    width: 72px;
    height: 72px;
  }

  .hero-name {
    font-size: 26px;
  }

  .resume-viewer {
    padding: 14px 16px 0;
  }
}
</style>
