<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton, ElDialog, ElIcon } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  Close,
  Edit,
  Location,
  Picture,
  User,
} from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import 'md-editor-v3/lib/preview.css'

import { eventsApi } from '../../api/events'
import EventComments from './EventComments.vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  event: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'edit'])

// Only non-accepted events get a status pill; the owner / an admin are the
// only ones the backend sends a non-accepted event to.
const STATUS_META = {
  pending: { label: '審核中', cls: 'is-pending' },
  rejected: { label: '已退回', cls: 'is-rejected' },
}

const photos = ref([])
const loadingPhotos = ref(false)
// Declared up here (not in the lightbox section below) because the
// immediate modelValue watcher resets it on close — a forward reference
// from that watcher would hit the temporal dead zone during setup.
const lightboxIndex = ref(-1)

const hasDescription = computed(
  () =>
    !!props.event?.description_md &&
    props.event.description_md.trim().length > 0,
)

async function loadPhotos() {
  if (!props.event) return
  loadingPhotos.value = true
  try {
    photos.value = await eventsApi.listPhotos(props.event.id)
  } catch {
    photos.value = []
  } finally {
    loadingPhotos.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      photos.value = []
      loadPhotos()
    } else {
      lightboxIndex.value = -1
    }
  },
  { immediate: true },
)

function photoUrl(p) {
  return eventsApi.photoUrl(props.event.id, p.id)
}

function close() {
  emit('update:modelValue', false)
}

function onEditClick() {
  emit('edit', props.event)
  close()
}

function formatDate(iso) {
  if (!iso) return '-'
  // event_date is a bare YYYY-MM-DD; append time so it parses in local
  // tz without an off-by-one day shift.
  return new Date(`${iso}T00:00:00`).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  })
}

// ---------- lightbox ----------
const lightboxOpen = computed(() => lightboxIndex.value >= 0)
const lightboxPhoto = computed(() =>
  lightboxIndex.value >= 0 ? photos.value[lightboxIndex.value] : null,
)

function openLightbox(idx) {
  lightboxIndex.value = idx
}
function closeLightbox() {
  lightboxIndex.value = -1
}
function prevPhoto() {
  if (photos.value.length === 0) return
  lightboxIndex.value =
    (lightboxIndex.value - 1 + photos.value.length) % photos.value.length
}
function nextPhoto() {
  if (photos.value.length === 0) return
  lightboxIndex.value = (lightboxIndex.value + 1) % photos.value.length
}

function onKeydown(e) {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  else if (e.key === 'ArrowLeft') prevPhoto()
  else if (e.key === 'ArrowRight') nextPhoto()
}

watch(lightboxOpen, (open) => {
  if (open) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    width="780"
    top="6vh"
    :teleported="false"
    :show-close="true"
    class="event-detail-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div v-if="event" class="detail-header">
        <div v-if="event.tags?.length" class="tag-row" data-test="detail-tags">
          <span v-for="t in event.tags" :key="t" class="tag-chip"
            >#{{ t }}</span
          >
        </div>
        <div class="title-row">
          <h2 class="detail-title" data-test="detail-title">
            {{ event.title }}
          </h2>
          <span
            v-if="STATUS_META[event.status]"
            class="status-pill"
            :class="STATUS_META[event.status].cls"
            :data-test="`detail-status-${event.status}`"
          >
            {{ STATUS_META[event.status].label }}
          </span>
        </div>
        <div class="detail-meta">
          <span
            v-if="event.author_display_name"
            class="meta-item"
            data-test="detail-author"
          >
            <el-icon :size="14"><User /></el-icon>
            {{ event.author_display_name }}
          </span>
          <span class="meta-item meta-date">
            <el-icon :size="14"><Calendar /></el-icon>
            {{ formatDate(event.event_date) }}
          </span>
          <span
            v-if="event.location"
            class="meta-item"
            data-test="detail-location"
          >
            <el-icon :size="14"><Location /></el-icon>
            {{ event.location }}
          </span>
          <span v-if="event.photo_count" class="meta-item">
            <el-icon :size="14"><Picture /></el-icon>
            {{ event.photo_count }} 張照片
          </span>
        </div>
      </div>
    </template>

    <div v-if="event" class="detail-body">
      <p
        v-if="event.status === 'rejected' && event.review_reason"
        class="reject-banner"
        data-test="detail-reject-reason"
      >
        退回原因：{{ event.review_reason }}
      </p>

      <!-- Photo gallery -->
      <div v-if="loadingPhotos" class="gallery">
        <div
          v-for="i in 3"
          :key="`skel-${i}`"
          class="gallery-cell shimmer"
        ></div>
      </div>
      <div
        v-else-if="photos.length > 0"
        class="gallery"
        data-test="detail-gallery"
      >
        <button
          v-for="(p, idx) in photos"
          :key="p.id"
          type="button"
          class="gallery-cell"
          :aria-label="p.caption || `查看第 ${idx + 1} 張照片`"
          data-test="gallery-thumb"
          @click="openLightbox(idx)"
        >
          <img
            :src="photoUrl(p)"
            :alt="p.caption || '活動照片'"
            loading="lazy"
          />
          <span v-if="p.caption" class="cell-caption">{{ p.caption }}</span>
        </button>
      </div>

      <!-- Description -->
      <div
        v-if="hasDescription"
        class="md-frame"
        data-test="detail-description"
      >
        <MdPreview
          :model-value="event.description_md"
          theme="light"
          preview-theme="default"
          language="zh-TW"
          :sanitize="sanitizeHtml"
        />
      </div>

      <div
        v-else-if="!loadingPhotos && photos.length === 0"
        class="detail-empty"
        data-test="detail-empty"
      >
        <el-icon :size="28"><Picture /></el-icon>
        <p>這個活動還沒有照片或記錄。</p>
      </div>

      <EventComments :event-id="event.id" :active="modelValue" />
    </div>

    <template #footer>
      <div class="footer-row">
        <slot name="footer-extra" />
        <div class="footer-spacer" />
        <el-button
          v-if="event?.can_edit"
          :icon="Edit"
          plain
          data-test="detail-edit-button"
          @click="onEditClick"
        >
          編輯
        </el-button>
        <el-button @click="close">關閉</el-button>
      </div>
    </template>
  </el-dialog>

  <!-- Lightbox overlay (teleported to body so it sits above the dialog) -->
  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="lightboxOpen"
        class="lightbox"
        data-test="lightbox"
        @click.self="closeLightbox"
      >
        <button
          type="button"
          class="lb-btn lb-close"
          aria-label="關閉"
          @click="closeLightbox"
        >
          <el-icon :size="22"><Close /></el-icon>
        </button>
        <button
          v-if="photos.length > 1"
          type="button"
          class="lb-btn lb-prev"
          aria-label="上一張"
          @click="prevPhoto"
        >
          <el-icon :size="26"><ArrowLeft /></el-icon>
        </button>
        <figure class="lb-figure">
          <img
            v-if="lightboxPhoto"
            :src="photoUrl(lightboxPhoto)"
            :alt="lightboxPhoto.caption || '活動照片'"
          />
          <figcaption v-if="lightboxPhoto?.caption" class="lb-caption">
            {{ lightboxPhoto.caption }}
          </figcaption>
          <span class="lb-counter"
            >{{ lightboxIndex + 1 }} / {{ photos.length }}</span
          >
        </figure>
        <button
          v-if="photos.length > 1"
          type="button"
          class="lb-btn lb-next"
          aria-label="下一張"
          @click="nextPhoto"
        >
          <el-icon :size="26"><ArrowRight /></el-icon>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ---------- Header ---------- */
.detail-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 4px 8px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 3px 10px;
  border-radius: 999px;
  color: var(--accent-warm-ink);
  background: var(--accent-warm-soft);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-title {
  margin: 0;
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.015em;
  color: var(--ink-900);
}

.status-pill {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 3px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.status-pill.is-pending {
  background: var(--accent-warm-soft, #fef3c7);
  color: var(--accent-warm-ink, #b45309);
}

.status-pill.is-rejected {
  background: #fee2e2;
  color: #b91c1c;
}

.reject-banner {
  margin: 0 0 16px;
  padding: 10px 14px;
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  border-radius: 4px;
  font-size: 13px;
  color: #b91c1c;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--ink-500);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.meta-date {
  color: var(--accent-warm-ink);
  font-weight: 600;
}

/* ---------- Body ---------- */
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 4px 0;
}

.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.gallery-cell {
  position: relative;
  padding: 0;
  border: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  aspect-ratio: 4 / 3;
  background: var(--surface-2);
  cursor: zoom-in;
  isolation: isolate;
}

.gallery-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform var(--dur) var(--ease);
}

.gallery-cell:hover img {
  transform: scale(1.06);
}

.cell-caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 14px 8px 6px;
  font-size: 11px;
  color: #fff;
  text-align: left;
  background: linear-gradient(180deg, transparent, rgba(15, 23, 42, 0.72));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.md-frame {
  padding: 0 2px;
}

.md-frame :deep(.md-editor-preview) {
  background: transparent;
  padding: 0;
}

.md-frame :deep(.md-editor-preview h1),
.md-frame :deep(.md-editor-preview h2),
.md-frame :deep(.md-editor-preview h3) {
  margin: 0.7em 0 0.35em;
}

.md-frame :deep(.md-editor-preview > :first-child) {
  margin-top: 0;
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 36px 0;
  color: var(--ink-500);
}

.detail-empty p {
  margin: 0;
  font-size: 13px;
}

.footer-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-spacer {
  flex: 1;
}

.shimmer {
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-md);
  background: rgba(15, 23, 42, 0.06);
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.5),
    transparent
  );
  transform: translateX(-100%);
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  to {
    transform: translateX(100%);
  }
}

/* ---------- Lightbox ---------- */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8, 11, 22, 0.92);
  backdrop-filter: blur(6px);
  padding: 24px;
}

.lb-figure {
  margin: 0;
  max-width: min(92vw, 1100px);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  position: relative;
}

.lb-figure img {
  max-width: 100%;
  max-height: 82vh;
  object-fit: contain;
  border-radius: var(--radius-md);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
}

.lb-caption {
  color: rgba(255, 255, 255, 0.92);
  font-size: 13.5px;
  text-align: center;
  max-width: 80ch;
}

.lb-counter {
  position: absolute;
  top: -28px;
  right: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  font-variant-numeric: tabular-nums;
}

.lb-btn {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
  cursor: pointer;
  transition:
    background var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.lb-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}

.lb-close {
  top: 20px;
  right: 20px;
}

.lb-prev {
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
}

.lb-next {
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
}

.lb-prev:hover {
  transform: translateY(-50%) scale(1.08);
}

.lb-next:hover {
  transform: translateY(-50%) scale(1.08);
}

.lightbox-enter-active,
.lightbox-leave-active {
  transition: opacity 0.2s ease;
}

.lightbox-enter-from,
.lightbox-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .detail-title {
    font-size: 19px;
  }
  .gallery {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  }
  .lb-btn {
    width: 38px;
    height: 38px;
  }
}
</style>
